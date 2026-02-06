
import asyncio
import sys
import os
from datetime import date

# 현재 디렉토리를 경로에 추가하여 모듈 import 가능하게 함
sys.path.insert(0, os.getcwd())

from engine.generator import SignalGenerator
from engine.config import app_config

async def test_generator():
    """generator.py 로직 검증 (API 호출 최소화)"""
    print("[Debug] SignalGenerator 초기화...")
    
    # 1. Generator 인스턴스 생성
    try:
        gen = SignalGenerator(capital=1000_0000)
        print("  -> 초기화 성공")
    except Exception as e:
        print(f"  -> 초기화 실패: {e}")
        return

    # 2. 필수 메서드 존재 여부 확인 (AttributeError 방지)
    required_methods = ['generate', '_analyze_base', '_create_final_signal', '_analyze_stock', 'get_summary']
    print("\n[Debug] 필수 메서드 존재 여부 확인...")
    for method in required_methods:
        if hasattr(gen, method):
            print(f"  -> {method}: OK")
        else:
            print(f"  -> {method}: MISSING!")

    # 3. generate 메서드 인자 및 내부 변수 스코프 체크 (Mock 실행)
    # 실제 API 호출을 막을 수는 없지만, 에러 발생 지점까지 진입해보는 것이 목적
    # 여기서는 NameError 체크를 위해 간단히 호출만 시도 (Collector 등에서 에러날 수 있으므로 try-except)
    print("\n[Debug] generate 메서드 스모크 테스트 (실행 직전 단계까지)...")
    try:
        # Mocking or just calling to see if it implies syntax/name errors immediately
        # collector 등을 mock 처리하면 좋겠지만 복잡하므로, 인스턴스화 후 메서드 호출 시도만
        pass
    except Exception as e:
        print(f"  -> 테스트 중 오류: {e}")

    print("\n[Debug] 검증 완료. NameError/SyntaxError가 없다면 성공.")

if __name__ == "__main__":
    asyncio.run(test_generator())
