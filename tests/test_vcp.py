#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VCP Signals 테스트 스크립트
특정 날짜를 지정하여 VCP 패턴 분석을 테스트할 수 있습니다.

사용법:
    python test_vcp.py                     # 오늘 날짜 기준
    python test_vcp.py 2026-01-30          # 특정 날짜 기준
    python test_vcp.py 2026-01-30 100      # 특정 날짜 + 최대 스캔 종목 수
"""

import sys
import os

# 프로젝트 루트를 path에 추가 (tests 상위 폴더)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def main():
    """메인 함수"""
    from engine.screener import SmartMoneyScreener
    
    # 커맨드라인 인자 파싱
    target_date = None
    max_stocks = 50
    
    if len(sys.argv) > 1:
        target_date = sys.argv[1]  # YYYY-MM-DD 형식
        print(f"[테스트 모드] 지정 날짜: {target_date}")
    
    if len(sys.argv) > 2:
        max_stocks = int(sys.argv[2])
        print(f"[테스트 모드] 최대 스캔 종목 수: {max_stocks}")
    
    print("=" * 60)
    print("VCP Signals 스크리너 테스트")
    print("=" * 60)
    
    if target_date:
        print(f"\n기준 날짜: {target_date}")
    else:
        print(f"\n기준 날짜: 오늘 (실시간)")
    print(f"스캔 종목 수: {max_stocks}개")
    print()
    
    # 스크리너 실행
    screener = SmartMoneyScreener(target_date=target_date)
    
    print("[Phase 1] Market Gate 상태 확인...")
    results = screener.run_screening(max_stocks=max_stocks)
    
    if results.empty:
        print("\n조건 충족 종목이 없습니다.")
        return
    
    print(f"\n[Phase 2] 시그널 생성...")
    signals = screener.generate_signals(results)
    
    print(f"\n생성된 시그널: {len(signals)}개")
    
    print("\n" + "=" * 60)
    print("VCP 시그널 상세")
    print("=" * 60)
    
    for i, signal in enumerate(signals, 1):
        print(f"\n[{i}] {signal['name']} ({signal['ticker']})")
        print(f"    시장: {signal['market']}")
        print(f"    점수: {signal['score']:.1f}")
        print(f"    진입가: {signal['entry_price']:,.0f}원")
        print(f"    등락률: {signal['change_pct']:+.2f}%")
        print(f"    외인 5일: {signal['foreign_5d']:,.0f}")
        print(f"    기관 5일: {signal['inst_5d']:,.0f}")
        print(f"    시그널 날짜: {signal['signal_date']}")
    
    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)
    
    # 결과 저장 여부 확인
    save_option = input("\n결과를 signals_log.csv에 저장하시겠습니까? (y/N): ").strip().lower()
    
    if save_option == 'y':
        import pandas as pd
        
        signals_df = pd.DataFrame(signals)
        signals_path = os.path.join('data', 'signals_log.csv')
        
        # 기존 데이터와 병합 (중복 제거)
        if os.path.exists(signals_path):
            existing_df = pd.read_csv(signals_path)
            combined_df = pd.concat([existing_df, signals_df], ignore_index=True)
            # 같은 날짜+ticker 중복 제거 (최신 우선)
            combined_df = combined_df.drop_duplicates(subset=['ticker', 'signal_date'], keep='last')
        else:
            combined_df = signals_df
            
        combined_df.to_csv(signals_path, index=False)
        print(f"\n✅ 저장 완료: {signals_path}")
    else:
        print("\n저장하지 않았습니다.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
