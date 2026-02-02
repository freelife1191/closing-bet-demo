import requests
import os
import sys

# Load env
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("PERPLEXITY_API_KEY")

if not api_key:
    print("No API Key")
    sys.exit(1)

url = "https://api.perplexity.ai/chat/completions"

payload = {
    "model": "sonar-pro",
    "messages": [
        {
            "role": "system",
            "content": "Be precise."
        },
        {
            "role": "user",
            "content": "Hello."
        }
    ]
}

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

try:
    print("Sending request via requests...")
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status: {response.status_code}")
    print(response.text[:500])
except Exception as e:
    print(f"Error: {e}")
