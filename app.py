from flask import Flask, render_template, request, jsonify
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from src.prompt import system_prompt
from pinecone import Pinecone
import os

app = Flask(__name__)

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

# Create prompt template
print("Creating prompt template...")
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

# Create the document chain
print("Creating chains...")
question_answer_chain = create_stuff_documents_chain(llm, prompt)

# Create the RAG chain
rag_chain = create_retrieval_chain(retriever, question_answer_chain)

print("Setup complete! Ready to answer questions.")


@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/get', methods=['POST'])
def get_response():
    try:
        user_message = request.json.get('msg')
        
        if not user_message:
            return jsonify({'response': 'Please provide a message'})
        
        print(f"User question: {user_message}")
        
        # Get response from RAG chain
        result = rag_chain.invoke({"input": user_message})
        response = result["answer"]
        
        print(f"Bot response: {response}")
        
        return jsonify({'response': response})
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'response': f'Error: {str(e)}'})


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)