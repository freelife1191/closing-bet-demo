import asyncio
import logging
import sys
import os

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from engine.collectors import EnhancedNewsCollector
from engine.config import app_config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_news_collector():
    collector = EnhancedNewsCollector(app_config)
    
    ticker = '005930' # 삼성전자
    name = '삼성전자'
    limit = 10
    
    print(f"=== {name}({ticker}) 뉴스 수집 테스트 (Limit: {limit}) ===")
    
    news_list = await collector.get_stock_news(ticker, limit, name)
    
    print(f"\n수집된 뉴스 개수: {len(news_list)}")
    print("-" * 60)
    print(f"{'순위':<4} | {'언론사(가중치)':<15} | {'제목'}")
    print("-" * 60)
    
    for i, news in enumerate(news_list, 1):
        source_info = f"{news.source}({news.weight})"
        print(f"{i:<4} | {source_info:<15} | {news.title[:40]}...")

if __name__ == "__main__":
    asyncio.run(test_news_collector())
