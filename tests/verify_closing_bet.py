
import asyncio
import os
import sys
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.generator import run_screener
from engine.config import app_config

async def verify_closing_bet():
    print("🚀 Verifying Closing Bet V2 Pipeline...")
    
    # 1. Setup - Use last Friday to ensure full market data
    # Today is 2026-02-02 (Mon). Last Friday is 2026-01-30.
    target_date = "2026-01-30" 
    print(f"📅 Target Date: {target_date}")
    
    # 2. Run Screener
    print("running screener...")
    try:
        # Lower capital to 10M for test, use restricted market list if possible (generator takes list of markets)
        result = await run_screener(
            capital=10_000_000,
            markets=["KOSPI"], # Test with KOSPI only for speed
            target_date=target_date,
            top_n=5
        )
        
        print("\n✅ Screener Execution Compelted")
        print(f"   - Total Candidates: {result.total_candidates}")
        print(f"   - Filtered Signals: {result.filtered_count}")
        print(f"   - Processing Time: {result.processing_time_ms:.2f}ms")
        
        if result.filtered_count == 0:
            print("⚠️ No signals found. This might be due to strict filtering or data issues.")
            # Check if we can relax filters or if data is missing?
            # For verification, we just want to see if it runs without crashing.
        else:
            print(f"   - AI Analysis Enabled: {result.signals[0].score_details.get('ai_evaluation') is not None}")
            
            # Check AI Content
            first_signal = result.signals[0]
            if first_signal.score_details.get('ai_evaluation'):
                ai_data = first_signal.score_details['ai_evaluation']
                print(f"   - AI Action: {ai_data.get('action')}")
                print(f"   - AI Reason: {ai_data.get('reason')[:50]}...")
            else:
                print("❌ AI Analysis Missing in signals")

        # 3. Check Output Files
        date_str = datetime.strptime(target_date, "%Y-%m-%d").strftime("%Y%m%d")
        expected_file = f"data/jongga_v2_results_{date_str}.json"
        if os.path.exists(expected_file):
             print(f"✅ Output file created: {expected_file}")
             with open(expected_file, 'r') as f:
                 data = json.load(f)
                 print(f"   - File contains {len(data['signals'])} signals")
        else:
             print(f"❌ Output file NOT found: {expected_file}")

    except Exception as e:
        print(f"❌ Execution Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_closing_bet())
