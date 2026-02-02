
import sys
import os
import json
# 프로젝트 루트 경로 추가 (scripts 상위 폴더)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.market_gate import MarketGate

def debug_market_gate():
    print(">>> Debugging Market Gate Logic")

    # 1. Check JSON file
    try:
        with open('data/market_gate.json', 'r') as f:
            data = json.load(f)
            print(f"JSON File Content - Label: {data.get('label')}, Score: {data.get('score')}")
    except Exception as e:
        print(f"Failed to read JSON: {e}")

    # 2. Run Engine
    try:
        mg = MarketGate()
        engine_result = mg.analyze()
        print(f"Engine Result - Status: {engine_result.get('status')}, Color: {engine_result.get('color')}, Score: {engine_result.get('total_score')}")
        
        # 3. Simulate API Logic
        color = engine_result.get('color', 'GRAY')
        label_map = {'GREEN': 'Bullish', 'YELLOW': 'Neutral', 'RED': 'Bearish', 'GRAY': 'Neutral'}
        
        gate_data = {
            'score': engine_result.get('total_score', 50),
            'label': label_map.get(color, 'Neutral'),
            'status': color,
        }
        print(f"Simulated API Response - Label: {gate_data['label']}, Score: {gate_data['score']}")

    except Exception as e:
        print(f"Engine Failed: {e}")

if __name__ == "__main__":
    debug_market_gate()
