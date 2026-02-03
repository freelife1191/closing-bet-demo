import asyncio
import logging
import sys
import os

# Ensure the current directory is in sys.path
sys.path.append(os.getcwd())

from engine.generator import SignalGenerator
from engine.config import config

# Configure valid logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def run_debug():
    print("=== Debugging Closing Bet ===")
    
    capital = 50_000_000
    
    print("1. Initializing SignalGenerator...")
    try:
        async with SignalGenerator(capital=capital) as generator:
            print("   -> Generator initialized.")
            
            # 2. Test Get Latest Date
            print("2. Testing Date Calculation...")
            latest_date = generator._collector._get_latest_market_date()
            print(f"   -> Latest Market Date: {latest_date}")
            
            # 3. Test Top Gainers (Limit to 10 for speed)
            print("3. Testing Top Gainers Fetch (Limit 10)...")
            # Try KOSDAQ as it usually has more volatility
            candidates = await generator._collector.get_top_gainers("KOSDAQ", 10, latest_date)
            print(f"   -> Fetched {len(candidates)} candidates.")
            
            if not candidates:
                print("   [ERROR] No candidates found! Check pykrx connection.")
                # Force fallback check logic here if needed
            else:
                for i, c in enumerate(candidates):
                    print(f"     [{i}] {c.name} ({c.code}): {c.change_pct}% / {c.trading_value/100000000:.1f}억")

                # 4. Test Base Analysis for first candidate
                first_stock = candidates[0]
                print(f"\n4. Analyzing first stock: {first_stock.name} ({first_stock.code})...")
                base_data = await generator._analyze_base(first_stock)
                
                if base_data:
                    print("   -> Base Analysis Successful.")
                    print(f"   -> Pre-Score: {base_data['pre_score'].total}")
                    print(f"   -> Trading Value: {base_data['stock'].trading_value}")
                    print(f"   -> Score Details: {base_data['score_details']}")
                else:
                    print("   [ERROR] Base Analysis Failed (returned None).")

                # 5. Check if it passes Filter
                print("\n5. Checking Filter Criteria...")
                PRE_SCORE_THRESHOLD = 2
                MIN_TRADING_VALUE = 50_000_000_000
                
                stock_obj = base_data['stock']
                pre_score = base_data['pre_score'].total
                trading_value = getattr(stock_obj, 'trading_value', 0)
                score_details = base_data.get('score_details', {})
                volume_ratio = score_details.get('volume_ratio', 0)
                
                print(f"   Pre-Score: {pre_score} (Threshold: {PRE_SCORE_THRESHOLD})")
                print(f"   Trading Value: {trading_value} (Threshold: {MIN_TRADING_VALUE})")
                print(f"   Volume Ratio: {volume_ratio} (Threshold: 2.0)")
                
                if (pre_score >= PRE_SCORE_THRESHOLD and 
                    trading_value >= MIN_TRADING_VALUE and
                    volume_ratio >= 2.0):
                    print("   [PASS] This stock would pass the 1st filter.")
                else:
                    print("   [FAIL] This stock would be filtered out.")

    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("=== Debugging Complete ===")

if __name__ == "__main__":
    asyncio.run(run_debug())
