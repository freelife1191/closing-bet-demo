
import sys
import os
import json
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.market_gate import MarketGate

# Configure basic logging
logging.basicConfig(level=logging.INFO)

def verify_market_gate():
    print(">>> Initializing MarketGate...")
    mg = MarketGate()
    
    print(">>> Running analysis...")
    result = mg.analyze()
    
    print(">>> Analysis Result (Commodities):")
    commodities = result.get('commodities', {})
    print(json.dumps(commodities, indent=2, ensure_ascii=False))
    
    # Save the result
    mg.save_analysis(result)
    print(">>> Saved analysis to market_gate.json")

    # Validation
    krx_gold = commodities.get('krx_gold', {})
    krx_silver = commodities.get('krx_silver', {})
    
    if not krx_gold or not krx_silver:
        print("FAIL: KRX Gold/Silver data missing")
        return

    print(f"KRX Gold: {krx_gold.get('value')} (Expected approx 13000+)")
    print(f"KRX Silver: {krx_silver.get('value')} (Expected approx 4000+)")

if __name__ == "__main__":
    verify_market_gate()
