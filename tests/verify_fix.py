
import asyncio
import sys
import os

# Set up path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.generator import run_screener
from engine.config import config

async def verify():
    print("Starting verification of Closing Bet fixes...")
    
    # Run screener with minimal setup for speed if possible, or just default
    # Note: top_n=50 for speed
    try:
        result = await run_screener(top_n=50)
        
        print(f"\nVerification Results:")
        print(f"Total Candidates: {result.total_candidates}")
        print(f"Filtered Count: {result.filtered_count}")
        print(f"Scanned Count: {result.scanned_count}")
        print(f"Signals Generated: {len(result.signals)}")
        
        if result.signals:
            print("\nSample Signals:")
            for s in result.signals[:3]:
                print(f" - {s.stock_name} ({s.grade}): Score {s.score.total}")
                
            # Check for non-D grades
            grades = [getattr(s.grade, 'value', s.grade) for s in result.signals]
            print(f"\nGrade Distribution: {result.by_grade}")
            
            if 'S' in grades or 'A' in grades or 'B' in grades or 'C' in grades:
                print("SUCCESS: Found grades other than D.")
            else:
                print("WARNING: Only D grades found (might be market conditions or logic strictness).")
                
        else:
            print("WARNING: No signals generated.")
            
    except Exception as e:
        print(f"ERROR during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify())
