"""
Flask Medical Chatbot with PHI De-identification
Integrates with Pinecone RAG and Google Gemini LLM
"""

from flask import Flask, render_template, request, jsonify, session
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from dotenv import load_dotenv
from src.prompt import system_prompt
from pinecone import Pinecone
import os
import secrets
import logging

# Import PHI Handler
from phi_handler import PHIDeidentifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Required for session management

# Store conversation histories for each session
store = {}

# Store PHI handlers for each session
phi_store = {}


def get_session_history(session_id: str):
    """Retrieve or create chat history for a session"""
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]


def get_phi_handler(session_id: str) -> PHIDeidentifier:
    """Retrieve or create PHI handler for a session"""
    if session_id not in phi_store:
        phi_store[session_id] = PHIDeidentifier(
            session_id=session_id,
            use_secure_tokens=True  # Use secure tokens for production
        )
        logger.info(f"Created new PHI handler for session: {session_id}")
    return phi_store[session_id]


# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Initialize embeddings
print("Loading embeddings...")
embeddings = download_hugging_face_embeddings()

# Initialize Pinecone
print("Connecting to Pinecone...")
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "medical-chatbot"

# Load the existing index
print(f"Loading index: {index_name}")
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)

# Create retriever
print("Creating retriever...")
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})

# Initialize LLM
print("Initializing LLM...")
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.4,
    convert_system_message_to_human=True
)

# Create prompt template with memory placeholder
print("Creating prompt template...")
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

# Create the document chain
print("Creating chains...")
question_answer_chain = create_stuff_documents_chain(llm, prompt)

# Create the RAG chain
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

# Wrap RAG chain with message history for memory
conversational_rag_chain = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",
)

print("Setup complete! Ready to answer questions with memory and PHI protection.")


@app.route('/')
def index():
    """Render main chat page"""
    # Create unique session ID for each user
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)
        logger.info(f"New session created: {session['session_id']}")
    return render_template('chat.html')


@app.route('/get', methods=['POST'])
def get_response():
    """
    Process user message with PHI de-identification
    
    Flow:
    1. Receive user message
    2. De-identify PHI (remove sensitive data)
    3. Send sanitized message to LLM via RAG chain
    4. Re-identify PHI in response (restore sensitive data)
    5. Return response to user
    """
    try:
        user_message = request.json.get('msg')
        
        if not user_message:
            return jsonify({'response': 'Please provide a message'})
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = secrets.token_hex(8)
        
        session_id = session['session_id']
        
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Original user message: {user_message}")
        
        # ========== PHI DE-IDENTIFICATION ==========
        phi_handler = get_phi_handler(session_id)
        
        # De-identify the user message (remove PHI before sending to LLM)
        deidentified_message, found_phi, context_hints = phi_handler.deidentify_with_context(
            user_message
        )
        
        logger.info(f"De-identified message: {deidentified_message}")
        if found_phi:
            logger.info(f"Found PHI categories: {list(found_phi.keys())}")
            for category, items in found_phi.items():
                logger.info(f"  - {category}: {len(items)} item(s) de-identified")
        
        # ========== SEND TO RAG CHAIN (LLM only sees de-identified data) ==========
        result = conversational_rag_chain.invoke(
            {"input": deidentified_message},
            config={"configurable": {"session_id": session_id}}
        )
        
        llm_response = result["answer"]
        
        logger.info(f"LLM response (before re-identification): {llm_response}")
        
        # ========== PHI RE-IDENTIFICATION ==========
        # Restore PHI tokens in the response with original values
        final_response = phi_handler.reidentify(llm_response)
        
        logger.info(f"Final response (after re-identification): {final_response}")
        
        # Get statistics for monitoring
        stats = phi_handler.get_statistics()
        logger.info(f"PHI Statistics - Total de-identified: {stats['total_deidentified']}, "
                   f"Total re-identified: {stats['total_reidentified']}")
        
        return jsonify({
            'response': final_response,
            'phi_detected': bool(found_phi),
            'phi_categories': list(found_phi.keys()) if found_phi else []
        })
    
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'response': 'I apologize, but I encountered an error processing your message. Please try again.',
            'error': True
        })


@app.route('/clear', methods=['POST'])
def clear_history():
    """Clear conversation history and PHI mappings for current session"""
    try:
        if 'session_id' in session:
            session_id = session['session_id']
            
            # Clear conversation history
            if session_id in store:
                store[session_id].clear()
                logger.info(f"Cleared conversation history for session: {session_id}")
            
            # Clear PHI mappings
            if session_id in phi_store:
                phi_store[session_id].clear_session()
                del phi_store[session_id]
                logger.info(f"Cleared PHI mappings for session: {session_id}")
        
        return jsonify({
            'response': 'Conversation history and personal data cleared!',
            'success': True
        })
    except Exception as e:
        logger.error(f"Error clearing history: {str(e)}")
        return jsonify({
            'response': f'Error clearing history: {str(e)}',
            'success': False
        })


@app.route('/phi-stats', methods=['GET'])
def get_phi_stats():
    """Get PHI de-identification statistics for current session (for monitoring)"""
    try:
        if 'session_id' not in session:
            return jsonify({
                'success': False,
                'error': 'No active session'
            })
        
        session_id = session['session_id']
        
        if session_id in phi_store:
            stats = phi_store[session_id].get_statistics()
            return jsonify({
                'success': True,
                'session_id': session_id,
                'statistics': stats
            })
        else:
            return jsonify({
                'success': True,
                'session_id': session_id,
                'statistics': {
                    'total_deidentified': 0,
                    'total_reidentified': 0,
                    'by_category': {},
                    'message': 'No PHI processing done yet'
                }
            })
    except Exception as e:
        logger.error(f"Error getting PHI stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'service': 'Medical Chatbot with PHI Protection',
        'version': '1.0.0',
        'active_sessions': len(store),
        'active_phi_handlers': len(phi_store)
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port, debug=False)