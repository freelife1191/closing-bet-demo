
import sys
import os
import json
from unittest.mock import MagicMock

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.core import KRStockChatbot
from chatbot import build_system_prompt

def test_full_capabilities():
    print("🚀 Starting Full Capabilities Verification...")
    
    # Initialize Chatbot
    bot = KRStockChatbot("test_user")
    watchlist = ["삼성전자", "카카오", "없는종목"]
    bot.client = MagicMock()
    bot.client.models.generate_content.return_value.text = "Mock Response"
    
    # Mock stock map to ensure '삼성전자' -> '005930' resolution works even if csv load failed
    bot.stock_map = {"삼성전자": "005930", "카카오": "035720"}
    bot.ticker_map = {"005930": "삼성전자", "035720": "카카오"}
    
    # Mock data fetchers to return strings so we don't need pandas
    bot._fetch_stock_history = MagicMock(return_value="[Price Data Present]")
    bot._fetch_institutional_trend = MagicMock(return_value="[Trend Data Present]")
    bot._fetch_signal_history = MagicMock(return_value="[Signal Data Present]")
    
    print("\n[Test 1] Watchlist Analysis Request")
    
    # 1. Ask about watchlist
    res = bot.chat("내 관심종목 분석해줘", watchlist=watchlist)
    print(f"DEBUG: Chat Result: {res}")
    
    # Extract the prompt sent to Gemini
    # Core.py uses:
    # chat_session = self.client.chats.create(...)
    # response = chat_session.send_message(content_parts)
    
    chat_session_mock = bot.client.chats.create.return_value
    call_args = chat_session_mock.send_message.call_args
    
    if not call_args:
        print("❌ Gemini Connect Failed (send_message not called)")
        # Debug: check if chats.create called
        if bot.client.chats.create.called:
             print("   chats.create WAS called, but send_message was not.")
        return
        
    # content_parts is the first arg
    content_parts = call_args.args[0]
    # content_parts is a list. The last element is the text string.
    prompt_sent = str(content_parts[-1])
    
    # Logic Verification
    if "[Price Data Present]" in prompt_sent:
         # This means _fetch_stock_history was called for watchlist items
         print("✅ Watchlist Data Injected")
    else:
         print("❌ Watchlist Data MISSING")
         print("   The bot did NOT look up detailed data for watchlist items.")

    print("\n[Test 2] Persona Suggestions")
    sug_vcp = bot.get_daily_suggestions(watchlist, persona="vcp")
    sug_gen = bot.get_daily_suggestions(watchlist, persona="general")
    
    # We can't easily verify the *content* without actual LLM, 
    # but we can verify code execution path if we mock generate_content to return different JSONs 
    # based on input prompt.
    # For now, just ensure it runs without error.
    print("✅ Suggestions generated")

if __name__ == "__main__":
    test_full_capabilities()
