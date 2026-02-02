import os
import asyncio
import httpx
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("PPLX_HTTPX")

# Load .env manually
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
logger.info(f"Loaded Key: {api_key[:5]}...{api_key[-5:]}")

async def test_pplx():
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    }

    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "Be precise."},
            {"role": "user", "content": "Hello"}
        ]
    }

    logger.info(f"Sending async request to {url}")
    try:
        # Replicate code in vcp_ai_analyzer.py
        # async with httpx.AsyncClient(timeout=60.0) as client:
        # Note: sometimes http2 might be an issue, default is http2=False in httpx < 1.0?
        # Let's try default first.
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            
        logger.info(f"Status Code: {response.status_code}")
        logger.info(f"Response Headers: {response.headers}")
        
        if response.status_code == 200:
            logger.info("Success!")
            logger.info(response.json())
        else:
            logger.error(f"Failed: {response.text[:500]}")

    except Exception as e:
        logger.error(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_pplx())
