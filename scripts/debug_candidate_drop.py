
import sys
import os
import asyncio
import logging
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.generator import SignalGenerator
from engine.config import config as signal_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_candidate_drops():
    print(f"--- Debugging Candidate Drops ---")
    
    # Initialize Generator with Context Manager
    generator = SignalGenerator()
    async with generator:
        # Mimic generator.py logic
        all_candidates = []
        for market in ["KOSPI", "KOSDAQ"]:
            print(f"Fetching {market} candidates...")
            candidates = await generator._collector.get_top_gainers(market, 300, None)
            all_candidates.extend(candidates)
            
        print(f"Total Candidates: {len(all_candidates)}")
        
        candidates_phase1 = []
        drop_reasons = {
            'trading_value': 0,
            'volume_ratio': 0,
            'grade_fail': 0,
            'error': 0
        }
        
        print("Running Phase 1 Analysis...")
        count = 0 
        for i, stock in enumerate(all_candidates):
            try:
                # 1. Basic Filters
                if stock.trading_value < signal_config.trading_value_min: 
                    drop_reasons['trading_value'] += 1
                    continue
                    
                # 2. Analyze Base
                try:
                    result = await generator._analyze_base(stock)
                    if not result:
                        drop_reasons['error'] += 1
                        continue
                except Exception as e:
                    # print(f"Analyze Base Error ({stock.name}): {e}")
                    drop_reasons['error'] += 1
                    continue
                
                score_details = result.get('score_details', {})
                volume_ratio = score_details.get('volume_ratio', 0)
                
                if volume_ratio < 2.0:
                    drop_reasons['volume_ratio'] += 1
                    continue

                # 3. Check Grade (Phase 1)
                grade = generator.scorer.determine_grade(
                    stock, 
                    result['pre_score'], 
                    score_details, 
                    result['supply'], 
                    result['charts'], 
                    allow_no_news=True
                )
                
                if getattr(grade, 'value', grade) is None:
                    drop_reasons['grade_fail'] += 1
                    continue
                    
                candidates_phase1.append(result)
                
            except Exception as e:
                # print(f"Error {stock.name}: {e}")
                drop_reasons['error'] += 1
                
            count += 1
            if count % 100 == 0: print(f"  Processed {count}...")

        print("\n--- Phase 1 Results ---")
        print(f"Survivors: {len(candidates_phase1)}")
        print(f"Drops: Value={drop_reasons['trading_value']}, VolumeRatio={drop_reasons['volume_ratio']}, Grade={drop_reasons['grade_fail']}")
        
        if len(candidates_phase1) == 0:
            print("No candidates passed Phase 1. Exiting.")
            return

        # Phase 2: News Check
        print("\nRunning Phase 2 (News Check)...")
        candidates_phase2 = []
        news_drops = 0
        
        for i, item in enumerate(candidates_phase1):
            stock = item['stock']
            news_list = await generator._news.get_stock_news(stock.code, 3, stock.name)
            
            if news_list:
                candidates_phase2.append(item)
                # print(f"  [Pass] {stock.name}: {len(news_list)} news")
            else:
                news_drops += 1
                print(f"  [Drop News] {stock.name}")
                
            if i % 10 == 0: print(f"  News Checked {i}...")
            
        print("\n--- Phase 2 Results ---")
        print(f"Survivors: {len(candidates_phase2)}")
        print(f"Dropped (No News): {news_drops}")

if __name__ == "__main__":
    asyncio.run(debug_candidate_drops())
