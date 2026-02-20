import asyncio
import logging
from engine.llm_analyzer import LLMAnalyzer
from engine.config import app_config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def main():
    analyzer = LLMAnalyzer()
    
    # Mock data for 2 stocks
    mock_items = [
        {
            "stock": {"name": "삼성전자", "code": "005930", "current_price": 70000, "change_pct": 1.5, "trading_value": 1000000000000},
            "news": [{"title": "삼성전자 새로운 AI 칩셋 발표", "summary": "삼성전자가 성능이 2배 향상된 새로운 AI 칩셋을 발표했습니다."}],
            "supply": None
        },
        {
            "stock": {"name": "SK하이닉스", "code": "000660", "current_price": 130000, "change_pct": 2.1, "trading_value": 800000000000},
            "news": [{"title": "SK하이닉스 HBM3E 양산 시작", "summary": "SK하이닉스가 엔비디아 향 HBM3E 양산을 본격적으로 시작했습니다."}],
            "supply": None
        }
    ]
    
    # Test batch size 2 with gemini-3-flash-preview
    print(f"Testing with model: {app_config.ANALYSIS_GEMINI_MODEL}, chunk size: {len(mock_items)}")
    
    result = await analyzer.analyze_news_batch(mock_items)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
