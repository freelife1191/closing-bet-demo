
import json
import random
from datetime import datetime, timedelta

def main():
    print("Generating mock Jongga V2 data...")
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Mock Signals
    signals = [
        {
            "stock_code": "005930",
            "stock_name": "삼성전자",
            "market": "KOSPI",
            "grade": "S",
            "total_score": 11,
            "current_price": 75000,
            "trading_value": 500000000000,
            "change_pct": 2.5,
            "volume_ratio": 2.5,
            "score": {
                "total": 11,
                "news": 3,
                "volume": 3,
                "chart": 2,
                "supply": 2,
                "timing": 0,
                "candle": 1,
                "llm_reason": "전일 대비 거래량 250% 급증 및 외국인 대량 순매수 포착. 반도체 업황 개선 기대감 반영된 장대양봉 출현."
            },
            "checklist": {
                "has_news": True,
                "is_new_high": False,
                "supply_positive": True
            },
            "buy_price": 74500,
            "target_price_1": 76800,
            "target_price_2": 78000,
            "stop_price": 73000,
            "themes": ["반도체", "HBM", "AI"],
            "news_items": [
                {"title": "삼성전자, HBM3E 공급 임박설에 강세", "source": "한국경제", "url": "#", "published_at": today},
                {"title": "외국인 5일 연속 삼성전자 순매수", "source": "매일경제", "url": "#", "published_at": today}
            ],
            "ai_evaluation": {
                "action": "BUY",
                "confidence": 92,
                "model": "Gemini 2.0 Flash",
                "reason": "강력한 수급과 모멘텀 확인됨."
            },
            "mini_chart": [] # Empty for now
        },
        {
            "stock_code": "000660",
            "stock_name": "SK하이닉스",
            "market": "KOSPI",
            "grade": "A",
            "total_score": 9,
            "current_price": 142000,
            "trading_value": 300000000000,
            "change_pct": 1.8,
            "volume_ratio": 1.8,
            "score": {
                "total": 9,
                "news": 2,
                "volume": 2,
                "chart": 2,
                "supply": 2,
                "timing": 0,
                "candle": 1,
                "llm_reason": "AI 반도체 수요 지속으로 견조한 흐름. 신고가 영역에서의 매물 소화 과정."
            },
            "checklist": {
                "has_news": True,
                "is_new_high": True,
                "supply_positive": True
            },
            "buy_price": 141000,
            "target_price_1": 145000,
            "target_price_2": 148000,
            "stop_price": 138000,
            "themes": ["반도체", "HBM", "CXL"],
            "news_items": [
                {"title": "SK하이닉스 목표가 상향 줄이어", "source": "인포맥스", "url": "#", "published_at": today}
            ],
            "ai_evaluation": {
                "action": "BUY",
                "confidence": 85,
                "model": "Gemini 2.0 Flash",
                "reason": "추세 지속형 패턴, 분할 매수 유효."
            },
            "mini_chart": []
        }
    ]

    data = {
        "date": today,
        "total_candidates": 600, # Realistic value (e.g. 500~700 in typical market)
        "filtered_count": len(signals),
        "signals": signals,
        "updated_at": datetime.now().isoformat()
    }
    
    with open('data/jongga_v2_latest.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Mock data generated with {len(signals)} signals.")

if __name__ == "__main__":
    main()
