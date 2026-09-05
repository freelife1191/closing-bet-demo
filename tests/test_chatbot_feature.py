import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chatbot.core as chatbot_core
from chatbot.core import KRStockChatbot
from app import create_app

class TestChatbotFeature(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.user_id = 'test_user'

        # 실제 data/ 에 쓰지 않는다. KRStockChatbot 이 DATA_DIR 로 저장소 경로를
        # 잡으므로 여기서 임시 디렉터리로 돌려놓는다. 그렇게 하지 않으면
        # /memory 와 /clear 검사가 운영 중인 chatbot_storage.db 를 건드린다.
        self._data_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._data_dir.cleanup)
        data_patch = patch.object(chatbot_core, "DATA_DIR", Path(self._data_dir.name))
        data_patch.start()
        self.addCleanup(data_patch.stop)

    @patch('chatbot.core.genai.GenerativeModel')
    def test_chatbot_initialization_and_model_loading(self, mock_model_cls):
        """Vertex 전환 후: configure() 호출 없이 환경변수의 모델 목록만 정상 로드되는지 확인."""
        # Vertex 전환 후 사용자별 API Key 입력은 무시되며 서비스 계정 인증만 사용된다.
        with patch.dict(os.environ, {
            'CHATBOT_AVAILABLE_MODELS': 'gemini-pro, gemini-flash',
        }):
            bot = KRStockChatbot(self.user_id)

            # Vertex 전환 후 사용자 API Key는 빈 문자열로 무시된다.
            self.assertEqual(bot.api_key, "")

            # 환경변수에서 사용 가능한 모델 목록이 로드되는지 확인.
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
        
        # 1. Status — 경량 명령이므로 히스토리에 남지 않는다.
        status_msg = bot.chat("/status")
        self.assertIn("📊 **현재 상태**", status_msg)
        self.assertIn(self.user_id, status_msg)
        self.assertEqual(bot.history.count(), 0)
        
        # 2. Help — 마찬가지로 남지 않는다.
        help_msg = bot.chat("/help")
        self.assertIn("🤖 **스마트머니봇 도움말**", help_msg)
        self.assertIn("/memory", help_msg)
        self.assertEqual(bot.history.count(), 0)
        
        # 3. Memory — [CHAT-017] 이후 소유자를 밝히지 않은 요청은 거부된다.
        owner_id = "owner-slash-commands"
        refused = bot.chat("/memory add topic TestValue")
        self.assertIn("사용자를 식별할 수 없어", refused)

        # Add
        bot.chat("/memory add topic TestValue", owner_id=owner_id)
        self.assertEqual(bot.memory.view(owner_id)["topic"]["value"], "TestValue")

        # View — 남의 메모리는 보이지 않는다.
        view_msg = bot.chat("/memory view", owner_id=owner_id)
        self.assertIn("TestValue", view_msg)
        other_view_msg = bot.chat("/memory view", owner_id="owner-other")
        self.assertNotIn("TestValue", other_view_msg)

        # Remove
        bot.chat("/memory remove topic", owner_id=owner_id)
        self.assertNotIn("topic", bot.memory.view(owner_id))
        
        # 4. Clear — /clear 는 세션을 비운 뒤 그 명령 자체를 기록으로 남긴다.
        before_add = bot.history.count()
        bot.history.add("user", "test")
        self.assertEqual(bot.history.count(), before_add + 1)
        bot.chat("/clear")
        self.assertEqual(bot.history.count(), 2)

if __name__ == '__main__':
    unittest.main()
