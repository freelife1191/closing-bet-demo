#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP Pipeline Validation Script
검증 항목:
1. SignalTracker가 로컬 데이터(daily_prices.csv)를 사용하여 VCP 패턴을 감지하는지
2. 감지된 시그널을 AI(Gemini)가 분석하여 매수/매도 의견을 제시하는지
3. 결과가 정상적으로 DataFrame으로 반환되는지
"""
import sys
import os
import asyncio
import pandas as pd
import logging

# 프로젝트 루트를 path에 추가 (tests 상위 폴더)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.signal_tracker import create_tracker
from engine.config import app_config

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VCP_Unittest")

async def verify_pipeline():
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║             VCP Pipeline & AI Verification                   ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. SignalTracker 초기화
    logger.info("1. SignalTracker 초기화 중...")
    tracker = create_tracker()
    
    if tracker.price_df.empty:
        logger.error("❌ 가격 데이터가 없습니다. data/daily_prices.csv 파일을 확인하세요.")
        return
    else:
        logger.info(f"✅ 가격 데이터 로드 완료: {len(tracker.price_df)} rows")

    # 2. VCP 시그널 스캔
    logger.info("2. VCP 시그널 스캔 중 (Real Data)...")
    signals_df = tracker.scan_today_signals()
    
    if signals_df.empty:
        logger.warning("⚠️ 오늘 감지된 VCP 시그널이 없습니다. 테스트를 위해 임의 데이터를 생성합니다.")
        # 테스트용 더미 데이터 생성 (삼성전자)
        signals_df = pd.DataFrame([{
            'ticker': '005930',
            'name': '삼성전자',
            'entry_price': 75000,
            'score': 85,
            'contraction_ratio': 0.15,
            'foreign_5d': 1500000,
            'inst_5d': 500000,
            'signal_date': '2024-02-01',
            'status': 'OPEN'
        }])
        logger.info(f"   [Test Mode] 임의 데이터 생성: {len(signals_df)}개")
    else:
        logger.info(f"✅ VCP 시그널 감지: {len(signals_df)}개 종목")

    # 3. AI 분석 실행
    logger.info("3. AI (Gemini/GPT) 분석 요청 중...")
    
    # API 키 확인
    if not app_config.GOOGLE_API_KEY and not app_config.OPENAI_API_KEY:
         logger.error("❌ API Key가 설정되지 않았습니다 (.env 확인 필요)")
         return

    # 상위 3개만 테스트
    test_signals = signals_df.head(3)
    analyzed_df = await tracker.analyze_signals_with_ai(test_signals)
    
    # 4. 결과 검증
    logger.info("4. 검증 결과 확인")
    print("\n" + "="*60)
    print("AI Analysis Result Sample")
    print("="*60)
    
    success_count = 0
    for idx, row in analyzed_df.iterrows():
        print(f"\n[{idx+1}] {row['name']} ({row['ticker']})")
        print(f"   - VCP Score: {row.get('vcp_score', 'N/A')}")
        print(f"   - AI Action: {row.get('ai_action')}")
        print(f"   - Confidence: {row.get('ai_confidence')}%")
        print(f"   - Reason: {row.get('ai_reason')}")
        
        if row.get('ai_action') in ['BUY', 'SELL', 'HOLD'] and row.get('ai_reason') != '분석 실패':
            success_count += 1
            
    print("\n" + "-"*60)
    if success_count > 0:
        logger.info(f"✅ AI 분석 성공: {success_count}/{len(analyzed_df)}")
    else:
        logger.error("❌ AI 분석 실패 또는 응답 없음")

if __name__ == "__main__":
    try:
        asyncio.run(verify_pipeline())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        logger.error(f"테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
