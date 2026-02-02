from chatbot.core import KRStockChatbot
import os
from dotenv import load_dotenv

load_dotenv()

def test_chatbot():
    print("Testing KRStockChatbot with google.genai...")
    
    # 1. Initialize
    try:
        bot = KRStockChatbot(user_id="test_user")
        print("✅ Initialization successful")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return

    # 2. Check models
    models = bot.get_available_models()
    print(f"✅ Available models: {models}")
    if not models:
        print("❌ No models found")
        return

    # 3. Test Chat
    try:
        response = bot.chat("안녕, 너는 누구니?")
        print(f"✅ Chat response: {response}")
    except Exception as e:
        print(f"❌ Chat failed: {e}")

if __name__ == "__main__":
    test_chatbot()
