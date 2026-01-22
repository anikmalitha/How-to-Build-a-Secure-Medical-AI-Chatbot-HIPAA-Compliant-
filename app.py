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

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Required for session management

# Store conversation histories for each session
store = {}

def get_session_history(session_id: str):
    """Retrieve or create chat history for a session"""
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

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
    model="gemini-2.5-flash",
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

print("Setup complete! Ready to answer questions with memory.")


@app.route('/')
def index():
    # Create unique session ID for each user
    if 'session_id' not in session:
        session['session_id'] = secrets.token_hex(8)
    return render_template('chat.html')


@app.route('/get', methods=['POST'])
def get_response():
    try:
        user_message = request.json.get('msg')
        
        if not user_message:
            return jsonify({'response': 'Please provide a message'})
        
        # Get or create session ID
        if 'session_id' not in session:
            session['session_id'] = secrets.token_hex(8)
        
        session_id = session['session_id']
        
        print(f"Session ID: {session_id}")
        print(f"User question: {user_message}")
        
        # Get response from conversational RAG chain with memory
        result = conversational_rag_chain.invoke(
            {"input": user_message},
            config={"configurable": {"session_id": session_id}}
        )
        
        response = result["answer"]
        
        print(f"Bot response: {response}")
        
        return jsonify({'response': response})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'response': f'Error: {str(e)}'})


@app.route('/clear', methods=['POST'])
def clear_history():
    """Clear conversation history for current session"""
    try:
        if 'session_id' in session:
            session_id = session['session_id']
            if session_id in store:
                store[session_id].clear()
            print(f"Cleared history for session: {session_id}")
        return jsonify({'response': 'Conversation history cleared!'})
    except Exception as e:
        return jsonify({'response': f'Error: {str(e)}'})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)