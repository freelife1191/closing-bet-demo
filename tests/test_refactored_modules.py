#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for Refactored Modules (Standalone Version)

테스트를 단순화하여 외부 의존성 최소화
"""
import unittest
import sys
import os
from unittest.mock import Mock

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# Mock Tests (No external dependencies)
# =============================================================================
class TestConstantsImmutability(unittest.TestCase):
    """Constants 불변성 테스트 (모만 사용)"""

    def test_trading_values_frozen(self):
        """TradingValueThresholds는 frozen dataclass"""
        from engine.constants import TRADING_VALUES

        # 불변성 확인
        with self.assertRaises(AttributeError):
            TRADING_VALUES.S_GRADE = 999

    def test_vcp_thresholds_frozen(self):
        """VCPThresholds는 frozen dataclass"""
        from engine.constants import VCP_THRESHOLDS

        with self.assertRaises(AttributeError):
            VCP_THRESHOLDS.CONTRACTION_RATIO = 0.5

    def test_constants_values(self):
        """Constants 값 확인"""
        from engine.constants import (
            TRADING_VALUES,
            VCP_THRESHOLDS,
            SCORING,
            VOLUME,
            PRICE_CHANGE,
            FX,
            TICKERS
        )

        # 거래대금
        self.assertEqual(TRADING_VALUES.S_GRADE, 1_000_000_000_000)
        self.assertEqual(TRADING_VALUES.A_GRADE, 500_000_000_000)
        self.assertEqual(TRADING_VALUES.B_GRADE, 100_000_000_000)

        # VCP
        self.assertEqual(VCP_THRESHOLDS.CONTRACTION_RATIO, 0.7)
        self.assertEqual(VCP_THRESHOLDS.MIN_SCORE, 50)

        # 스코어링
        self.assertEqual(SCORING.MIN_C_GRADE, 8)
        self.assertEqual(SCORING.MIN_B_GRADE, 10)
        self.assertEqual(SCORING.MIN_A_GRADE, 12)
        self.assertEqual(SCORING.MIN_S_GRADE, 15)

        # 거래량
        self.assertEqual(VOLUME.RATIO_MIN, 2.0)
        self.assertEqual(VOLUME.RATIO_3X, 3.0)

        # 등락률
        self.assertEqual(PRICE_CHANGE.MIN, 5.0)
        self.assertEqual(PRICE_CHANGE.MAX, 20.0)

        # 환율
        self.assertEqual(FX.SAFE, 1420.0)
        self.assertEqual(FX.WARNING, 1450.0)
        self.assertEqual(FX.DANGER, 1480.0)

        # 티커
        self.assertEqual(TICKERS.KODEX_200, "069500")
        self.assertEqual(TICKERS.KOSPI_INDEX, "^KS11")


class TestPandasUtilsStandalone(unittest.TestCase):
    """pandas_utils 독립 테스트"""

    def test_safe_value_extractors(self):
        """안전한 값 추출기 테스트"""
        from engine.pandas_utils import (
            safe_value,
            safe_int,
            safe_float,
            safe_str
        )

        # NaN 처리
        self.assertEqual(safe_value(float('nan'), 0), 0)
        self.assertEqual(safe_value(None, 'default'), 'default')
        self.assertIsNone(safe_value(float('nan'), None))

        # 정수 변환
        self.assertEqual(safe_int(123), 123)
        self.assertEqual(safe_int(float('nan'), 0), 0)
        self.assertEqual(safe_int('abc', 0), 0)

        # 실수 변환
        self.assertEqual(safe_float(123.45), 123.45)
        self.assertEqual(safe_float(float('nan'), 0.0), 0.0)

        # 문자열
        self.assertEqual(safe_str(float('nan')), '')
        self.assertEqual(safe_str(None, 'N/A'), 'N/A')

    def test_calculation_helpers(self):
        """계산 헬퍼 테스트"""
        from engine.pandas_utils import (
            calculate_return_pct,
            calculate_volume_ratio,
            format_ticker
        )

        # 수익률 계산
        self.assertEqual(calculate_return_pct(110000, 100000), 10.0)
        self.assertEqual(calculate_return_pct(90000, 100000), -10.0)
        self.assertIsNone(calculate_return_pct(100000, 0))
        self.assertIsNone(calculate_return_pct(100000, -100))

        # 거래량 배수
        self.assertEqual(calculate_volume_ratio(200, [100, 150, 100, 150, 100]), 2.0)
        self.assertEqual(calculate_volume_ratio(0, [100, 100]), 1.0)
        self.assertEqual(calculate_volume_ratio(100, []), 1.0)

        # 티커 포맷
        self.assertEqual(format_ticker('5930'), '005930')
        self.assertEqual(format_ticker('5930', width=4), '5930')

    def test_sanitize_for_json(self):
        """JSON 직렬화 처리 테스트"""
        from engine.pandas_utils import sanitize_for_json

        # NaN 처리
        result = sanitize_for_json({'value': float('nan')})
        self.assertEqual(result, {'value': None})

        # Infinity 처리
        result = sanitize_for_json({'value': float('inf')})
        self.assertEqual(result, {'value': None})

        # 중첩 구조
        result = sanitize_for_json({
            'data': {'nested': float('nan')},
            'list': [1, float('nan'), 3]
        })
        self.assertEqual(result, {
            'data': {'nested': None},
            'list': [1, None, 3]
        })

        # 유효한 값 보존
        result = sanitize_for_json({'value': 123, 'text': 'test'})
        self.assertEqual(result, {'value': 123, 'text': 'test'})

    def test_signal_sorting(self):
        """시그널 정렬 테스트"""
        from engine.pandas_utils import sort_signals_by_grade_and_score

        signals = [
            {'grade': 'B', 'score': {'total': 10}},
            {'grade': 'S', 'score': {'total': 15}},
            {'grade': 'A', 'score': {'total': 12}},
            {'grade': 'C', 'score': {'total': 8}},
        ]

        result = sort_signals_by_grade_and_score(signals)

        self.assertEqual(result[0]['grade'], 'S')
        self.assertEqual(result[1]['grade'], 'A')
        self.assertEqual(result[2]['grade'], 'B')
        self.assertEqual(result[3]['grade'], 'C')


class TestExceptions(unittest.TestCase):
    """예외 클래스 테스트"""

    def test_engine_error(self):
        """기본 예외"""
        from engine.exceptions import EngineError

        error = EngineError("Test error", {"key": "value"})
        self.assertIn("Test error", str(error))
        self.assertIn("key=value", str(error))
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.context, {"key": "value"})

    def test_market_data_error_inheritance(self):
        """상속 관계 확인"""
        from engine.exceptions import MarketDataError, EngineError

        error = MarketDataError("Test")
        self.assertIsInstance(error, EngineError)

    def test_data_file_not_found_error(self):
        """파일 없음 예외"""
        from engine.exceptions import DataFileNotFoundError

        error = DataFileNotFoundError("/path/to/file.csv")
        self.assertEqual(error.filepath, "/path/to/file.csv")
        self.assertIn("Data file not found", str(error))

    def test_insufficient_data_error(self):
        """데이터 부족 예외"""
        from engine.exceptions import InsufficientDataError

        error = InsufficientDataError("price", 20, 10)
        self.assertEqual(error.data_type, "price")
        self.assertEqual(error.required, 20)
        self.assertEqual(error.actual, 10)

    def test_llm_api_error(self):
        """LLM API 예외"""
        from engine.exceptions import LLMAPIError

        error = LLMAPIError("Gemini", "Rate limit exceeded")
        self.assertEqual(error.provider, "Gemini")
        self.assertIn("Gemini", str(error))

    def test_llm_timeout_error(self):
        """LLM 타임아웃 예외"""
        from engine.exceptions import LLMTimeoutError

        error = LLMTimeoutError("Z.ai", 120)
        self.assertEqual(error.provider, "Z.ai")
        self.assertEqual(error.timeout_seconds, 120)

    def test_error_categorization(self):
        """에러 분류 테스트"""
        from engine.exceptions import (
            MarketDataError,
            LLMAnalysisError,
            get_error_category,
            is_retryable_error,
            is_critical_error
        )

        # DATA 카테고리
        error = MarketDataError("Test")
        self.assertEqual(get_error_category(error), "DATA")

        # LLM 카테고리
        error = LLMAnalysisError("Test")
        self.assertEqual(get_error_category(error), "LLM")

        # UNKNOWN 카테고리
        error = ValueError("Test")
        self.assertEqual(get_error_category(error), "UNKNOWN")

        # 재시도 가능 여부
        from engine.exceptions import LLMTimeoutError
        self.assertTrue(is_retryable_error(LLMTimeoutError("Test", 60)))
        self.assertFalse(is_retryable_error(ValueError("Test")))

        # 치명적 여부
        from engine.exceptions import DataFileNotFoundError
        self.assertTrue(is_critical_error(DataFileNotFoundError("test")))
        self.assertFalse(is_critical_error(ValueError("Test")))


class TestErrorHandler(unittest.TestCase):
    """에러 핸들러 테스트"""

    def test_build_error_response(self):
        """에러 응답 빌더 테스트"""
        from engine.error_handler import build_error_response

        error = ValueError("Test error")
        response = build_error_response(error, status_code=500)

        self.assertTrue(response['error'])
        self.assertEqual(response['message'], "Test error")
        self.assertEqual(response['type'], "ValueError")
        self.assertEqual(response['category'], "UNKNOWN")

    def test_build_error_response_with_details(self):
        """상세 에러 응답 테스트"""
        from engine.error_handler import build_error_response
        from engine.exceptions import LLMTimeoutError

        error = LLMTimeoutError("Test", 60)
        response = build_error_response(error, include_details=True)

        self.assertTrue(response['details']['retryable'])
        self.assertFalse(response['details']['critical'])

    def test_build_success_response(self):
        """성공 응답 빌더 테스트"""
        from engine.error_handler import build_success_response

        response = build_success_response({"data": "test"}, "Success!")

        self.assertFalse(response['error'])
        self.assertEqual(response['data'], {"data": "test"})
        self.assertEqual(response['message'], "Success!")

    def test_validate_required(self):
        """필수값 검증 테스트"""
        from engine.error_handler import validate_required

        # 정상 켍우
        validate_required("test", "field_name")

        # None
        with self.assertRaises(ValueError, msg="is required"):
            validate_required(None, "field_name")

        # 빈 문자열
        with self.assertRaises(ValueError, msg="is required"):
            validate_required("", "field_name")

    def test_validate_range(self):
        """범위 검증 테스트"""
        from engine.error_handler import validate_range

        # 정상 범위
        validate_range(50, "value", min_val=0, max_val=100)

        # 최소값 미달
        with self.assertRaises(ValueError, msg="below minimum"):
            validate_range(-10, "value", min_val=0)

        # 최대값 초과
        with self.assertRaises(ValueError, msg="above maximum"):
            validate_range(150, "value", max_val=100)

    def test_validate_positive(self):
        """양수 검증 테스트"""
        from engine.error_handler import validate_positive

        # 양수
        validate_positive(100, "amount")

        # 0
        with self.assertRaises(ValueError, msg="must be positive"):
            validate_positive(0, "amount")

        # 음수
        with self.assertRaises(ValueError, msg="must be positive"):
            validate_positive(-50, "amount")


class TestDataSourceManager(unittest.TestCase):
    """데이터 소스 매니저 테스트 (모크만 사용)"""

    def test_manager_initialization(self):
        """매니저 초기화 테스트"""
        from engine.data_sources import DataSourceManager

        manager = DataSourceManager()
        self.assertEqual(len(manager.sources), 3)

    def test_manager_with_custom_sources(self):
        """사용자 정의 소스 테스트"""
        from engine.data_sources import DataSourceManager, DataSourceStrategy

        mock_source = Mock(spec=DataSourceStrategy)
        mock_source.is_available.return_value = False

        manager = DataSourceManager([mock_source])
        self.assertEqual(len(manager.sources), 1)


class TestRetryConfig(unittest.TestCase):
    """재시도 설정 테스트"""

    def test_retry_config_values(self):
        """재시도 설정 값 확인"""
        from engine.llm_utils import RetryConfig

        self.assertEqual(RetryConfig.MAX_RETRIES, 5)
        self.assertEqual(RetryConfig.BASE_DELAY, 2.0)
        self.assertEqual(RetryConfig.MAX_DELAY, 60.0)

        # 재시도 키워드
        self.assertIn("429", RetryConfig.RETRY_ON)
        self.assertIn("RESOURCE_EXHAUSTED", RetryConfig.RETRY_ON)


# =============================================================================
# Test Summary
# =============================================================================
def create_test_suite():
    """테스트 스위트 생성"""
    suite = unittest.TestSuite()

    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestConstantsImmutability))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestPandasUtilsStandalone))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestExceptions))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestErrorHandler))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestDataSourceManager))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestRetryConfig))

    return suite


if __name__ == "__main__":
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    suite = create_test_suite()
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        print(f"Success rate: {success_rate:.1f}%")

    if result.wasSuccessful():
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
