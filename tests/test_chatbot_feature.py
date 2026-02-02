import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.core import KRStockChatbot
from app import create_app

class TestChatbotFeature(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.user_id = 'test_user'

    @patch('chatbot.core.genai.GenerativeModel')
    @patch('chatbot.core.genai.configure')
    def test_chatbot_initialization_and_model_loading(self, mock_configure, mock_model_cls):
        """Test if chatbot initializes and loads models from env correctly"""
        # Mock env vars
        with patch.dict(os.environ, {
            'CHATBOT_AVAILABLE_MODELS': 'gemini-pro, gemini-flash',
            'GEMINI_API_KEY': 'fake_key'
        }):
            bot = KRStockChatbot(self.user_id)
            
            # Check if configure was called
            mock_configure.assert_called_with(api_key='fake_key')
            
            # Check available models
            models = bot.get_available_models()
            self.assertIn('gemini-pro', models)
            self.assertIn('gemini-flash', models)
            self.assertEqual(len(models), 2)

    @patch('chatbot.core.genai.GenerativeModel')
    def test_chat_uses_specified_model(self, mock_model_cls):
        """Test if chat() method uses the requested model"""
        # Setup mock models
        mock_pro = MagicMock()
        mock_flash = MagicMock()
        
        # When GenerativeModel is instantiated, return different mocks based on arg
        def side_effect(model_name):
            if model_name == 'gemini-pro':
                return mock_pro
            elif model_name == 'gemini-flash':
                return mock_flash
            return MagicMock()
            
        mock_model_cls.side_effect = side_effect

        with patch.dict(os.environ, {
            'CHATBOT_AVAILABLE_MODELS': 'gemini-pro, gemini-flash', 
            'GEMINI_API_KEY': 'fake_key'
        }):
            bot = KRStockChatbot(self.user_id)
            
            # 1. Test sending message with 'gemini-pro'
            mock_chat_session = mock_pro.start_chat.return_value
            mock_chat_session.send_message.return_value.text = "Response from Pro"
            
            response = bot.chat("Hello", model_name='gemini-pro')
            
            self.assertEqual(response, "Response from Pro")
            mock_pro.start_chat.assert_called()
            mock_flash.start_chat.assert_not_called()
            
            # Reset mocks
            mock_pro.reset_mock()
            mock_flash.reset_mock()
            
            # 2. Test sending message with 'gemini-flash'
            mock_chat_session_flash = mock_flash.start_chat.return_value
            mock_chat_session_flash.send_message.return_value.text = "Response from Flash"
            
            response = bot.chat("Hi", model_name='gemini-flash')
            
            self.assertEqual(response, "Response from Flash")
            mock_flash.start_chat.assert_called()
            mock_pro.start_chat.assert_not_called()

    def test_api_models_endpoint(self):
        """Test GET /api/kr/chatbot/models"""
        with patch.dict(os.environ, {
            'CHATBOT_AVAILABLE_MODELS': 'model-A, model-B'
        }):
            # Patch where it is imported from
            with patch('chatbot.get_chatbot') as mock_get_bot:
                mock_bot_instance = MagicMock()
                mock_bot_instance.get_available_models.return_value = ['model-A', 'model-B']
                mock_bot_instance.current_model_name = 'model-A'
                mock_get_bot.return_value = mock_bot_instance
                
                response = self.client.get('/api/kr/chatbot/models')
                data = json.loads(response.data)
                
                self.assertEqual(response.status_code, 200)
                self.assertEqual(data['models'], ['model-A', 'model-B'])
                self.assertEqual(data['current'], 'model-A')

    def test_api_chat_endpoint(self):
        """Test POST /api/kr/chatbot"""
        with patch('chatbot.get_chatbot') as mock_get_bot:
            mock_bot_instance = MagicMock()
            mock_bot_instance.chat.return_value = "AI Response"
            mock_get_bot.return_value = mock_bot_instance
            
            payload = {
                'message': 'Test Message',
                'model': 'test-model'
            }
            
            response = self.client.post('/api/kr/chatbot', 
                                      data=json.dumps(payload),
                                      content_type='application/json')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['response'], "AI Response")
            
            # Verify verify model name was passed to chat method
            mock_bot_instance.chat.assert_called_with('Test Message', model_name='test-model')

    def test_slash_commands(self):
        """Test slash commands logic"""
        bot = KRStockChatbot(self.user_id)
        
        # 1. Status
        status_msg = bot.chat("/status")
        self.assertIn("📊 **현재 상태**", status_msg)
        self.assertIn(self.user_id, status_msg)
        
        # 2. Help
        help_msg = bot.chat("/help")
        self.assertIn("🤖 **스마트머니봇 도움말**", help_msg)
        self.assertIn("/memory", help_msg)
        
        # 3. Memory
        # Add
        bot.chat("/memory add topic TestValue")
        memories = bot.get_memory()
        self.assertIn("topic", memories)
        self.assertEqual(memories["topic"]["value"], "TestValue")
        
        # View
        view_msg = bot.chat("/memory view")
        self.assertIn("TestValue", view_msg)
        
        # Remove
        bot.chat("/memory remove topic")
        self.assertNotIn("topic", bot.get_memory())
        
        # 4. Clear
        bot.history.add("user", "test")
        self.assertEqual(bot.history.count(), 1)
        bot.chat("/clear")
        self.assertEqual(bot.history.count(), 0)

if __name__ == '__main__':
    unittest.main()
