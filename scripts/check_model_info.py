
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("API Key not found")
    exit(1)

genai.configure(api_key=api_key)

model_name = "gemini-flash-latest" 
# Try with 'models/' prefix as well
try:
    model_info = genai.get_model(f"models/{model_name}")
    print(f"Model: {model_name}")
    print(f"Display Name: {model_info.display_name}")
    print(f"Version: {model_info.version}")
    print(f"Base Model ID: {getattr(model_info, 'base_model_id', 'N/A')}")
    print(f"Description: {model_info.description}")

    # Generate content to check response metadata
    print("\nGenerating content to check response metadata...")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Hello")
    print(f"Response Attributes: {dir(response)}")
    if hasattr(response, 'model_version'):
        print(f"Model Version from Response: {response.model_version}")
    # Check for usage_metadata which might have model info
    if hasattr(response, 'usage_metadata'):
        print(f"Usage Metadata: {response.usage_metadata}")
    
except Exception as e:
    print(f"Error fetching {model_name}: {e}")

model_name = "gemini-2.0-flash" 
try:
    model_info = genai.get_model(f"models/{model_name}")
    print(f"\nModel: {model_name}")
    print(f"Display Name: {model_info.display_name}")
    print(f"Version: {model_info.version}")
except Exception as e:
    print(f"Error fetching {model_name}: {e}")
