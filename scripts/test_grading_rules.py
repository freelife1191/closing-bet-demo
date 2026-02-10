
import sys
import os
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.scorer import Scorer
from engine.models import StockData, ScoreDetail, SupplyData, ChartData, Grade
from engine.config import config

def test_grading():
    scorer = Scorer(config)
    
    print("=== Testing Grade Rules (Vol Ratio: S>=5, A>=3, B>=2) ===")
    
    scenarios = [
        {
            "name": "Scenario S (Perfect)",
            "value": 1_200_000_000_000, # 1.2T
            "score": 16,
            "vol_ratio": 6.0,
            "expect": Grade.S
        },
        {
            "name": "Scenario S Fail (Vol Ratio 4.0 -> Grade A)",
            "value": 1_200_000_000_000,
            "score": 16,
            "vol_ratio": 4.0,
            "expect": Grade.A # Value S-tier, Score S-tier, but Vol A-tier
        },
        {
            "name": "Scenario A (Perfect)",
            "value": 600_000_000_000, # 600B
            "score": 13,
            "vol_ratio": 3.5,
            "expect": Grade.A
        },
        {
            "name": "Scenario A Fail (Vol Ratio 2.5 -> Grade B)",
            "value": 600_000_000_000,
            "score": 13,
            "vol_ratio": 2.5,
            "expect": Grade.B
        },
        {
            "name": "Scenario B (Perfect)",
            "value": 200_000_000_000, # 200B
            "score": 11,
            "vol_ratio": 2.2,
            "expect": Grade.B
        },
        {
            "name": "Scenario Drop (Vol Ratio 1.5)",
            "value": 200_000_000_000,
            "score": 11,
            "vol_ratio": 1.5,
            "expect": None
        },
        {
            "name": "Scenario Yujin Robot (Toss Data)",
            "value": 964_150_064_100, # 964B
            "score": 14, # Assume High Score
            "vol_ratio": 4.36,
            "expect": Grade.A # Value < 1T, so Grade A. Vol check (4.36 >= 3.0) OK.
        }
    ]
    
    for case in scenarios:
        # Mock Objects
        stock = StockData(
            code="000000", 
            name="Test", 
            market="KOSPI",
            close=10000,
            change_pct=15.0, # Valid range
            trading_value=case['value'],
            volume=1000000
        )
        
        score_detail = ScoreDetail()
        score_detail.total = case['score']
        score_detail.news = 3 # Avoid "No News" drop
        
        details_dict = {'volume_ratio': case['vol_ratio']}
        supply = SupplyData()
        chart = ChartData() # Empty chart
        
        # Determine Grade
        result = scorer.determine_grade(stock, score_detail, details_dict, supply, chart, allow_no_news=True)
        
        status = "PASS" if result == case['expect'] else f"FAIL (Got {result})"
        print(f"[{case['name']:<40}] Expect: {str(case['expect']):<8} | Result: {str(result):<8} -> {status}")

if __name__ == "__main__":
    test_grading()
