import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Adjust path to import engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.llm_analyzer import LLMAnalyzer

# Mock config
import engine.config
engine.config.app_config = MagicMock()
engine.config.app_config.GEMINI_MODEL = "gemini-mock"
engine.config.app_config.LLM_PROVIDER = "gemini"
engine.config.app_config.LLM_API_TIMEOUT = 10
engine.config.app_config.ANALYSIS_LLM_API_TIMEOUT = 10

class TestRateLimit(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_news_sentiment_retry(self):
        analyzer = LLMAnalyzer()
        # Mock client
        analyzer._client = MagicMock()
        
        # Simulate 429 error twice, then success
        mock_response = MagicMock()
        mock_response.text = '{"score": 1, "reason": "success"}'
        
        error_429 = Exception("429 Resource Exhausted")
        
        # Side effect: raise error twice, then return response
        analyzer._client.models.generate_content.side_effect = [error_429, error_429, mock_response]
        
        # Patch asyncio.sleep to speed up test
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await analyzer.analyze_news_sentiment("TestStock", [{"title": "t", "summary": "s"}])
            
            # Check if retry happened
            self.assertEqual(analyzer._client.models.generate_content.call_count, 3)
            self.assertEqual(mock_sleep.call_count, 2)
            self.assertIsNotNone(result)
            print(f"Sentiment Analysis: Retried {mock_sleep.call_count} times and succeeded.")

    async def test_generate_market_summary_retry(self):
        analyzer = LLMAnalyzer()
        analyzer._client = MagicMock()
        
        mock_response = MagicMock()
        mock_response.text = "Market Summary"
        
        error_429 = Exception("429 Resource Exhausted")
        
        # Fail 4 times, succeed on 5th
        analyzer._client.models.generate_content.side_effect = [error_429] * 4 + [mock_response]
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            result = await analyzer.generate_market_summary([{"name": "StockA"}])
            
            self.assertEqual(analyzer._client.models.generate_content.call_count, 5)
            self.assertEqual(mock_sleep.call_count, 4)
            self.assertEqual(result, "Market Summary")
            print(f"Market Summary: Retried {mock_sleep.call_count} times and succeeded.")

if __name__ == '__main__':
    unittest.main()
