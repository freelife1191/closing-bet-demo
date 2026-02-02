from .core import KRStockChatbot
from .prompts import build_system_prompt

__all__ = ['KRStockChatbot', 'build_system_prompt']

_chatbot_instance = None

def get_chatbot():
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = KRStockChatbot("default_user")
        
        # Register cleanup on exit
        import atexit
        def cleanup_chatbot():
            global _chatbot_instance
            if _chatbot_instance:
                _chatbot_instance.close()
        atexit.register(cleanup_chatbot)
        
    return _chatbot_instance
