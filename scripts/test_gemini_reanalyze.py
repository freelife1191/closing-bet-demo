import json
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
import re

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.llm_analyzer import LLMAnalyzer
from engine.config import app_config

async def run_test():
    print(">>> 1. LLMAnalyzer Init")
    analyzer = LLMAnalyzer()
    
    latest_file = Path("data/jongga_v2_latest.json")
    if not latest_file.exists():
        print("data/jongga_v2_latest.json not found")
        return
        
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    all_signals = data.get("signals", [])
    if not all_signals:
        print("No signals to analyze")
        return
        
    test_signals = all_signals[:1]
    items_to_analyze = []
    
    for signal in test_signals:
        items_to_analyze.append({
            'stock': signal,
            'news': signal.get('news_items', []),
            'supply': None
        })
        
    print(f">>> 2. Testing analyze_news_batch with 1 stock: {test_signals[0].get('stock_name')}")
    try:
        results_map = await analyzer.analyze_news_batch(items_to_analyze, market_status={"status": "Test"})
        print(f"\n>>> 3. Result Map Generation Success")
        
        # ====== Replicate the mapping & save logic in kr_market.py ======
        updated_count = 0
        normalized_results = {}
        for key, value in results_map.items():
            clean_name = re.sub(r'\s*\([0-9A-Za-z]+\)\s*$', '', key).strip()
            normalized_results[clean_name] = value
            normalized_results[key] = value

        for signal in all_signals:
            name = signal.get('stock_name')
            stock_code = signal.get('stock_code', '')
            
            matched_result = None
            if name in normalized_results:
                matched_result = normalized_results[name]
            elif f"{name} ({stock_code})" in results_map:
                matched_result = results_map[f"{name} ({stock_code})"]
            elif stock_code in normalized_results:
                matched_result = normalized_results[stock_code]
                
            if matched_result:
                if 'score' not in signal:
                    signal['score'] = {}
                
                signal['score']['llm_reason'] = matched_result.get('reason', '')
                signal['score']['news'] = matched_result.get('score', 0)
                signal['ai_evaluation'] = {
                    'action': matched_result.get('action', 'HOLD'),
                    'confidence': matched_result.get('confidence', 0),
                    'model': matched_result.get('model', 'gemini-2.0-flash')
                }
                updated_count += 1
                
        print(f">>> 4. Matched & Updated count: {updated_count}")
        
    except Exception as e:
        print(f"\n>>> [EXCEPTION] in analyze_news_batch or Mapping: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
