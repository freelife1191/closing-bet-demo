#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종가베팅 테스트 스크립트
특정 날짜를 지정하여 종가베팅 분석을 테스트할 수 있습니다.

사용법:
    python test_jongga.py                    # 오늘 날짜 기준 (주말은 금요일)
    python test_jongga.py 2026-01-30         # 특정 날짜 기준
    python test_jongga.py 2026-01-30 KOSPI   # 특정 날짜 + 특정 시장
"""

import asyncio
import sys
import os

# 프로젝트 루트를 path에 추가 (tests 상위 폴더)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def main():
    """메인 함수"""
    from engine.generator import run_screener
    
    # 커맨드라인 인자 파싱
    target_date = None
    markets = ['KOSPI', 'KOSDAQ']
    
    if len(sys.argv) > 1:
        target_date = sys.argv[1]  # YYYY-MM-DD 형식
        print(f"[테스트 모드] 지정 날짜: {target_date}")
    
    if len(sys.argv) > 2:
        markets = sys.argv[2].split(',')  # "KOSPI,KOSDAQ" 또는 "KOSPI"
        print(f"[테스트 모드] 지정 시장: {markets}")
    
    print("=" * 60)
    print("종가베팅 시그널 생성기 테스트")
    print("=" * 60)
    
    capital = 50_000_000
    print(f"\n자본금: {capital:,}원")
    print(f"R값: {capital * 0.005:,.0f}원 (0.5%)")
    
    if target_date:
        print(f"기준 날짜: {target_date}")
    print(f"대상 시장: {', '.join(markets)}")
    print()
    
    # 스크리너 실행
    result = await run_screener(
        capital=capital,
        markets=markets,
        target_date=target_date
    )
    
    print(f"\n처리 시간: {result.processing_time_ms:.0f}ms")
    print(f"생성된 시그널: {len(result.signals)}개")
    print(f"등급별: {result.by_grade}")
    
    print("\n" + "=" * 60)
    print("시그널 상세")
    print("=" * 60)
    
    for i, signal in enumerate(result.signals, 1):
        print(f"\n[{i}] {signal.stock_name} ({signal.stock_code})")
        print(f"    등급: {getattr(signal.grade, 'value', signal.grade)}")
        print(f"    점수: {signal.score.total}/12")
        print(f"    등락률: {signal.change_pct:+.2f}%")
        print(f"    진입가: {signal.entry_price:,}원")
        print(f"    손절가: {signal.stop_price:,}원")
        print(f"    목표가: {signal.target_price:,}원")
        
        # 뉴스 정보 출력
        if signal.news_items:
            print(f"    뉴스: {len(signal.news_items)}개")
            for j, news in enumerate(signal.news_items[:2], 1):
                title = news.get('title', '') if isinstance(news, dict) else getattr(news, 'title', '')
                print(f"      [{j}] {title[:50]}...")
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)
    
    return result


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
