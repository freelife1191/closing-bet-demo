
import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# Load .env
env_path = Path('.env').resolve()
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)

api_key = os.getenv("GOOGLE_API_KEY")
print(f"GOOGLE_API_KEY from env: {api_key[:5] + '...' if api_key else 'None'}")

try:
    from google import genai
    print("google.genai imported successfully.")
except ImportError as e:
    print(f"Failed to import google.genai: {e}")

try:
    import google.generativeai
    print("google.generativeai imported successfully.")
except ImportError as e:
    print(f"Failed to import google.generativeai: {e}")
