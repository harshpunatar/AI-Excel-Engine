import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Setup Groq Client
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

try:
    print("Checking available Groq models...")
    models = client.models.list()
    
    print("\nAVAILABLE MODELS:")
    for model in models.data:
        print(f"- {model.id}")
        
except Exception as e:
    print(f"\nERROR: {e}")