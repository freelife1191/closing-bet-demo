#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market - Quick Start Entry Point
바로 실행 가능한 메인 스크립트
"""

import os
import sys

# 현재 디렉토리를 패키지 루트로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║               KR Market - Smart Money Screener               ║
║                   외인/기관 수급 분석 시스템                   ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("사용 가능한 기능:")
    print("-" * 60)
    print("1. 수급 스크리닝      - 외인/기관 매집 종목 탐지")
    print("2. VCP 시그널 생성    - 변동성 수축 패턴 종목 발굴")
    print("3. 종가베팅 V2        - 고급 시그널 생성")
    print("4. AI 분석            - Gemini 기반 종목 분석")
    print("5. 백테스트           - 전략 성과 검증")
    print("6. Flask 서버 시작    - API 서버 실행")
    print("-" * 60)

    choice = input("\n실행할 기능 번호를 입력하세요 (1-6): ").strip()

    if choice == "1":
        print("\n🔍 수급 스크리닝 시작...")
        from engine.screener import SmartMoneyScreener
        screener = SmartMoneyScreener()
        results = screener.run_screening(max_stocks=50)
        print(f"\n✅ 스크리닝 완료! {len(results)}개 종목 분석됨")
        print(results.head(10).to_string())

    elif choice == "2":
        print("\n📊 VCP 시그널 생성 (Real Data + AI Analysis)...")
        from engine.signal_tracker import create_tracker
        import asyncio
        import pandas as pd
        
        tracker = create_tracker()
        signals_df = tracker.scan_today_signals()
        
        if not signals_df.empty:
            print(f"\n🤖 {len(signals_df)}개 VCP 후보 감지. AI 정밀 분석 시작...")
            analyzed_df = asyncio.run(tracker.analyze_signals_with_ai(signals_df))
            
            print(f"\n[AI 분석 결과]")
            # 출력 컬럼 선택
            cols = ['name', 'ticker', 'score', 'ai_action', 'ai_confidence', 'ai_reason']
            # ai_reason은 너무 길 수 있으니 요약
            analyzed_df['ai_reason'] = analyzed_df['ai_reason'].astype(str).str.slice(0, 50) + "..."
            
            print(analyzed_df[cols].to_string())
            
            # 저장 질문
            save = input("\n결과를 저장하시겠습니까? (y/N): ").lower()
            if save == 'y':
                tracker._append_to_log(analyzed_df)
                print("✅ signals_log.csv 저장 완료")
        else:
            print("⚠️ 감지된 시그널이 없습니다.")

    elif choice == "3":
        print("\n🎯 종가베팅 V2 실행...")
        from engine.generator import run_screener
        import asyncio
        result = asyncio.run(run_screener())
        print(f"\n✅ 완료! {result.filtered_count}개 시그널 생성됨")

    elif choice == "4":
        print("\n🤖 AI 분석 시작...")
        from engine.kr_ai_analyzer import KrAiAnalyzer
        analyzer = KrAiAnalyzer()
        result = analyzer.analyze_stock("005930")  # 삼성전자
        print(result)

    elif choice == "5":
        print("\n📈 백테스트 실행...")
        print("백테스트 기능 구현 준비 중...")

    elif choice == "6":
        print("\n🌐 Flask 서버 시작...")
        from flask_app import app
        app.run()

    else:
        print("잘못된 선택입니다.")

    input("\n아무 키나 눌러 종료...")


if __name__ == "__main__":
    main()
