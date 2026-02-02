
import os
import google.generativeai as genai
from engine.config import app_config

def list_models():
    api_key = app_config.GOOGLE_API_KEY
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment or config.")
        return

    try:
        genai.configure(api_key=api_key)
        print("Fetching available models...")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
