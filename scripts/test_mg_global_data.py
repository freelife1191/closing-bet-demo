import sys
import os
sys.path.append(os.getcwd())

from engine.market_gate import MarketGate
import json

def test_global_data():
    mg = MarketGate()
    data = mg._get_global_data()
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    test_global_data()
