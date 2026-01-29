"""
Flask Medical Chatbot with PHI De-identification
Using Groq LLM (Free & Fast)
"""

from flask import Flask, render_template, request, jsonify, session
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_groq import ChatGroq
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
from datetime import datetime, timedelta

# Import PHI Handler
from phi_handler import PHIDeidentifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Storage
store = {}  # Conversation history
phi_store = {}  # PHI handlers
rate_limit_store = {}  # Rate limiting

# Load environment
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Validate API keys
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY not found in .env file!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file! Get free key at https://console.groq.com/keys")

os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY
os.environ["GROQ_API_KEY"] = GROQ_API_KEY


# ========== RATE LIMITER ==========
class RateLimiter:
    def __init__(self, rpm=10, rpd=500):
        self.rpm = rpm
        self.rpd = rpd
    
    def check(self, sid):
        now = datetime.now()
        if sid not in rate_limit_store:
            rate_limit_store[sid] = {'m': [], 'd': []}
        
        data = rate_limit_store[sid]
        data['m'] = [t for t in data['m'] if t > now - timedelta(minutes=1)]
        data['d'] = [t for t in data['d'] if t > now - timedelta(days=1)]
        
        if len(data['m']) >= self.rpm:
            return False, f"Too fast! Wait {60 - (now - data['m'][0]).seconds}s"
        if len(data['d']) >= self.rpd:
            return False, "Daily limit reached"
        
        data['m'].append(now)
        data['d'].append(now)
        return True, None

rate_limiter = RateLimiter()


# ========== HELPERS ==========
def get_session_history(session_id: str):
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

def get_phi_handler(session_id: str):
    if session_id not in phi_store:
        phi_store[session_id] = PHIDeidentifier(session_id=session_id, use_secure_tokens=True)
    return phi_store[session_id]


# ========== INITIALIZE COMPONENTS ==========
print("\n" + "="*60)
print("🏥 GLORY DIAGNOSTIC - MEDICAL AI CHATBOT")
print("="*60)

# 1. Load Embeddings
print("\n📥 Loading embeddings...")
embeddings = download_hugging_face_embeddings()
print("✅ Embeddings loaded")

# 2. Connect to Pinecone
print("\n🔌 Connecting to Pinecone...")
pc = Pinecone(api_key=PINECONE_API_KEY)
index_name = "medical-chatbot"
docsearch = PineconeVectorStore.from_existing_index(
    index_name=index_name,
    embedding=embeddings
)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 3})
print(f"✅ Connected to Pinecone index: {index_name}")

# 3. Initialize Groq LLM
print("\n🤖 Initializing Groq LLM...")
llm = ChatGroq(
    model="llama-3.1-8b-instant",  # Fast & reliable
    groq_api_key=GROQ_API_KEY,
    temperature=0.4,
    max_tokens=1024,
)
print("✅ Groq LLM initialized (llama-3.1-8b-instant)")

# 4. Create Prompt Template
print("\n📝 Creating prompt template...")
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

# 5. Create Chains
print("\n⛓️ Building RAG chain...")
question_answer_chain = create_stuff_documents_chain(llm, prompt)
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

conversational_rag_chain = RunnableWithMessageHistory(
    rag_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
    output_messages_key="answer",
)
print("✅ RAG chain with memory created")

print("\n" + "="*60)
print("🚀 CHATBOT READY! Using Groq LLM")
print("="*60 + "\n")


# ========== ROUTES ==========
@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)
        logger.info(f"New session: {session['session_id']}")
    return render_template('chat.html')


@app.route('/get', methods=['POST'])
def get_response():
    """Main chat endpoint with PHI protection"""
    try:
        # Get message
        data = request.get_json()
        user_message = data.get('msg', '').strip() if data else ''
        
        if not user_message:
            return jsonify({'response': 'Please enter a message.', 'error': True})
        
        # Get/create session
        if 'session_id' not in session:
            session['session_id'] = secrets.token_hex(8)
        session_id = session['session_id']
        
        logger.info(f"[{session_id}] User: {user_message[:100]}...")
        
        # Rate limiting
        allowed, msg = rate_limiter.check(session_id)
        if not allowed:
            return jsonify({
                'response': f"⏳ {msg}\n\n📞 Call **10650** for immediate help.",
                'rate_limited': True
            })
        
        # PHI De-identification
        phi_handler = get_phi_handler(session_id)
        deidentified_msg, found_phi, _ = phi_handler.deidentify_with_context(user_message)
        
        if found_phi:
            logger.info(f"[{session_id}] PHI detected: {list(found_phi.keys())}")
        
        # Get AI Response
        try:
            result = conversational_rag_chain.invoke(
                {"input": deidentified_msg},
                config={"configurable": {"session_id": session_id}}
            )
            
            ai_response = result["answer"]
            
            # Re-identify PHI in response
            final_response = phi_handler.reidentify(ai_response)
            
            logger.info(f"[{session_id}] AI response generated successfully")
            
            return jsonify({
                'response': final_response,
                'phi_detected': bool(found_phi),
                'phi_categories': list(found_phi.keys()) if found_phi else [],
                'success': True
            })
            
        except Exception as llm_error:
            logger.error(f"[{session_id}] LLM Error: {str(llm_error)}")
            
            # Return helpful error message
            return jsonify({
                'response': f"""⚠️ **Service temporarily unavailable**

I'm having trouble processing your request right now. Please try again in a moment.

**Your question:** "{user_message[:100]}..."

**In the meantime:**
📞 Call our hotline: **10650**
📧 Email: info@glorydiagnostic.com
🏥 Visit any of our 50+ branches

*Error: {str(llm_error)[:100]}*""",
                'error': True,
                'error_details': str(llm_error)[:200]
            })
    
    except Exception as e:
        logger.error(f"Server Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'response': "❌ Server error. Please try again or call **10650**.",
            'error': True
        })


@app.route('/clear', methods=['POST'])
def clear_history():
    """Clear chat history and PHI data"""
    try:
        if 'session_id' in session:
            sid = session['session_id']
            if sid in store:
                store[sid].clear()
            if sid in phi_store:
                phi_store[sid].clear_session()
                del phi_store[sid]
            if sid in rate_limit_store:
                del rate_limit_store[sid]
            logger.info(f"Cleared session: {sid}")
        
        return jsonify({'success': True, 'response': 'Chat history cleared!'})
    except Exception as e:
        return jsonify({'success': False, 'response': str(e)})


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'llm': 'Groq (llama-3.1-8b-instant)',
        'sessions': len(store)
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host="0.0.0.0", port=port, debug=False)