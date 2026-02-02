import os
import requests
import json
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("PPLX_DEBUG")

# Load .env manually to be sure
def load_env():
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    if key == 'PERPLEXITY_API_KEY':
                        return val.strip()
    return None

api_key = load_env()
if not api_key:
    logger.error("PERPLEXITY_API_KEY not found in .env")
    exit(1)

logger.info(f"Loaded Key: {api_key[:5]}...{api_key[-5:]} (Length: {len(api_key)})")

url = "https://api.perplexity.ai/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json" # Add explicit Accept
}

payload = {
    "model": "sonar-pro", # Try a standard model, check if config matches
    "messages": [
        {"role": "system", "content": "Be precise."},
        {"role": "user", "content": "Hello"}
    ]
}

logger.info(f"Sending request to {url}")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    
    logger.info(f"Status Code: {response.status_code}")
    logger.info(f"Response Headers: {response.headers}")
    logger.info(f"Response Content: {response.text}")

    if response.status_code == 401:
        logger.error("401 Unauthorized - Check Key or Credit Balance.")
    elif response.status_code == 200:
        logger.info("Success!")
    else:
        logger.warning(f"Unexpected status: {response.status_code}")

except Exception as e:
    logger.error(f"Request failed: {e}")
