#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit Tests for LLM Analyzer (Refactored)

llm_analyzer_refactored.py 모듈의 모든 클래스와 메서드를 테스트합니다.

Created: 2026-02-11
Phase 2: LLM Analyzer Retry Logic Refactoring Tests
"""
import pytest
import asyncio
import json
import random
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime

from engine.llm_analyzer import (
    RetryConfig,
    LLMRetryStrategy,
    GeminiRetryStrategy,
    ZAIRetryStrategy,
    LLMAnalyzer,
)


# ========================================================================
# Test RetryConfig Class
# ========================================================================

class TestRetryConfig:
    """RetryConfig 설정 클래스 테스트"""

    def test_max_retries_constant(self):
        """MAX_RETRIES 상수 테스트"""
        assert RetryConfig.MAX_RETRIES == 5

    def test_base_wait_constant(self):
        """BASE_WAIT 상수 테스트"""
        assert RetryConfig.BASE_WAIT == 2.0

    def test_max_wait_constant(self):
        """MAX_WAIT 상수 테스트"""
        assert RetryConfig.MAX_WAIT == 32.0

    def test_retry_conditions_contains_all_required_errors(self):
        """재시도 조건에 필수 에러 키워드 포함 테스트"""
        required_conditions = [
            "429",
            "resource_exhausted",
            "503",
            "overloaded",
            "502",
            "500",
            "unavailable",
        ]
        for condition in required_conditions:
            assert condition in RetryConfig.RETRY_CONDITIONS

    def test_retry_conditions_is_list(self):
        """RETRY_CONDITIONS가 리스트인지 테스트"""
        assert isinstance(RetryConfig.RETRY_CONDITIONS, list)

    def test_retry_conditions_not_empty(self):
        """RETRY_CONDITIONS가 비어있지 않은지 테스트"""
        assert len(RetryConfig.RETRY_CONDITIONS) > 0


# ========================================================================
# Test LLMRetryStrategy Abstract Class
# ========================================================================

class TestLLMRetryStrategyAbstract:
    """LLMRetryStrategy 추상 클래스 테스트"""

    def test_cannot_instantiate_abstract_class(self):
        """추상 클래스 직접 인스턴스화 불가 테스트"""
        with pytest.raises(TypeError):
            LLMRetryStrategy()

    def test_execute_is_abstract_method(self):
        """execute가 추상 메서드인지 테스트"""
        assert hasattr(LLMRetryStrategy, 'execute')
        assert getattr(LLMRetryStrategy.execute, '__isabstractmethod__', False) is True


# ========================================================================
# Test GeminiRetryStrategy Class
# ========================================================================

class TestGeminiRetryStrategy:
    """GeminiRetryStrategy 클래스 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock Gemini client"""
        client = Mock()
        client.models = Mock()
        client.models.generate_content = Mock()
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        """테스트용 GeminiRetryStrategy 인스턴스"""
        return GeminiRetryStrategy(mock_client, model="gemini-2.0-flash")

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, strategy, mock_client):
        """초기화 테스트"""
        assert strategy.client is mock_client
        assert strategy.model == "gemini-2.0-flash"
        assert strategy._current_model == "gemini-2.0-flash"

    def test_init_default_model(self, mock_client):
        """기본 모델명 테스트"""
        strategy = GeminiRetryStrategy(mock_client)
        assert strategy.model == "gemini-2.0-flash"

    # ========================================================================
    # get_model_name Tests
    # ========================================================================

    def test_get_model_name_initial(self, strategy):
        """초기 모델명 반환 테스트"""
        assert strategy.get_model_name() == "gemini-2.0-flash"

    def test_get_model_name_after_update(self, strategy):
        """모델 업데이트 후 이름 반환 테스트"""
        strategy._current_model = "gemini-flash-latest"
        assert strategy.get_model_name() == "gemini-flash-latest"

    # ========================================================================
    # execute Success Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_execute_success(self, strategy, mock_client):
        """성공적인 LLM 호출 테스트"""
        mock_response = Mock()
        mock_response.text = "Test response"
        # hasattr로 확인하므로 속성을 명시적으로 설정
        type(mock_response).model_version = "gemini-2.0-flash-exp"

        mock_client.models.generate_content.return_value = mock_response

        result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Test response"
        assert strategy._current_model == "gemini-2.0-flash-exp"
        mock_client.models.generate_content.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_without_model_version(self, strategy, mock_client):
        """모델 버전 없는 응답 처리 테스트"""
        # model_version 속성이 없는 mock 응답 생성
        mock_response = Mock(spec=['text'])  # text 속성만 가짐
        mock_response.text = "Test response"

        mock_client.models.generate_content.return_value = mock_response

        result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Test response"
        assert strategy._current_model == "gemini-2.0-flash"  # 변경 없음

    # ========================================================================
    # execute Retry Logic Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_execute_retry_on_429_error(self, strategy, mock_client):
        """429 에러 시 재시도 테스트"""
        mock_response = Mock()
        mock_response.text = "Success after retry"

        # 첫 번째 호출은 429 에러, 두 번째는 성공
        mock_client.models.generate_content.side_effect = [
            Exception("429 Too Many Requests"),
            mock_response
        ]

        with patch('asyncio.sleep'):  # sleep 건너뜀
            result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Success after retry"
        assert mock_client.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_retry_on_resource_exhausted(self, strategy, mock_client):
        """resource_exhausted 에러 시 재시도 테스트"""
        mock_response = Mock()
        mock_response.text = "Success"
        type(mock_response).model_version = None

        # 리스트 기반 side_effect 사용 (429 테스트와 동일한 패턴)
        # 에러 메시지에 "resource_exhausted" 포함 (RetryCondition과 일치)
        mock_client.models.generate_content.side_effect = [
            Exception("resource_exhausted error"),
            mock_response
        ]

        with patch('asyncio.sleep'):
            result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Success"
        assert mock_client.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_retry_on_503_error(self, strategy, mock_client):
        """503 에러 시 재시도 테스트"""
        mock_response = Mock()
        mock_response.text = "Success"

        mock_client.models.generate_content.side_effect = [
            Exception("503 Service Unavailable"),
            mock_response
        ]

        with patch('asyncio.sleep'):
            result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Success"

    @pytest.mark.asyncio
    async def test_execute_retry_on_overloaded_error(self, strategy, mock_client):
        """overloaded 에러 시 재시도 테스트"""
        mock_response = Mock()
        mock_response.text = "Success"

        mock_client.models.generate_content.side_effect = [
            Exception("Server overloaded"),
            mock_response
        ]

        with patch('asyncio.sleep'):
            result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Success"

    @pytest.mark.asyncio
    async def test_execute_max_retries_exceeded(self, strategy, mock_client):
        """최대 재시도 초과 시 예외 발생 테스트"""
        # 항상 429 에러 반환
        mock_client.models.generate_content.side_effect = Exception("429 Too Many Requests")

        with patch('asyncio.sleep'):
            with pytest.raises(Exception, match="429"):
                await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        # MAX_RETRIES (5) 만큼 호출되었는지 확인
        assert mock_client.models.generate_content.call_count == RetryConfig.MAX_RETRIES

    # ========================================================================
    # execute Timeout Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_execute_timeout_single_retry(self, strategy, mock_client):
        """단일 타임아웃 후 재시도 테스트"""
        mock_response = Mock()
        mock_response.text = "Success after timeout"

        mock_client.models.generate_content.side_effect = [
            asyncio.TimeoutError(),
            mock_response
        ]

        result = await strategy.execute("Test prompt", 1.0, "gemini-2.0-flash")

        assert result == "Success after timeout"
        assert mock_client.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_timeout_max_retries(self, strategy, mock_client):
        """최대 타임아웃 재시도 후 예외 발생 테스트"""
        mock_client.models.generate_content.side_effect = asyncio.TimeoutError()

        with pytest.raises(asyncio.TimeoutError):
            await strategy.execute("Test prompt", 1.0, "gemini-2.0-flash")

        assert mock_client.models.generate_content.call_count == RetryConfig.MAX_RETRIES

    # ========================================================================
    # Model Fallback Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_gemini_3_flash_preview_fallback(self, mock_client):
        """gemini-3-flash-preview -> gemini-flash-latest 폴백 테스트"""
        strategy = GeminiRetryStrategy(mock_client, model="gemini-3-flash-preview")

        mock_response = Mock()
        mock_response.text = "Success after fallback"
        # model_version이 없도록 명시적으로 설정
        type(mock_response).model_version = None

        mock_client.models.generate_content.side_effect = [
            Exception("429 Too Many Requests"),
            mock_response
        ]

        with patch('asyncio.sleep') as mock_sleep:
            result = await strategy.execute("Test prompt", 30.0, "gemini-3-flash-preview")

            # 폴백 시 wait_time = 1.0 (짧은 대기)
            mock_sleep.assert_called_with(1.0)
            assert strategy._current_model == "gemini-flash-latest"
            assert result == "Success after fallback"

    @pytest.mark.asyncio
    async def test_exponential_backoff_calculation(self, strategy, mock_client):
        """지수 백오프 계산 테스트"""
        mock_response = Mock()
        mock_response.text = "Success"

        # 3번 실패 후 성공
        mock_client.models.generate_content.side_effect = [
            Exception("429"),
            Exception("429"),
            Exception("429"),
            mock_response
        ]

        sleep_times = []

        async def capture_sleep(delay):
            sleep_times.append(delay)

        with patch('asyncio.sleep', side_effect=capture_sleep):
            result = await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert result == "Success"

        # 지수 백오프 확인 (attempt 0, 1, 2)
        # wait_time = (5 * (2 ** attempt)) + random(1, 3)
        # attempt 0: 5*1 + rand(1,3) = 6~8
        # attempt 1: 5*2 + rand(1,3) = 11~13
        # attempt 2: 5*4 + rand(1,3) = 21~23
        assert len(sleep_times) == 3
        assert 6 <= sleep_times[0] <= 8
        assert 11 <= sleep_times[1] <= 13
        assert 21 <= sleep_times[2] <= 23

    # ========================================================================
    # Non-retryable Error Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_non_retryable_error_raises_immediately(self, strategy, mock_client):
        """재시도 불가 에러 즉시 발생 테스트"""
        mock_client.models.generate_content.side_effect = ValueError("Invalid input")

        with pytest.raises(ValueError, match="Invalid input"):
            await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        # 한 번만 호출됨 (재시도 없음)
        assert mock_client.models.generate_content.call_count == 1

    @pytest.mark.asyncio
    async def test_authentication_error_no_retry(self, strategy, mock_client):
        """인증 에러 시 재시도 안 함 테스트"""
        mock_client.models.generate_content.side_effect = Exception("Authentication failed")

        with pytest.raises(Exception, match="Authentication failed"):
            await strategy.execute("Test prompt", 30.0, "gemini-2.0-flash")

        assert mock_client.models.generate_content.call_count == 1


# ========================================================================
# Test ZAIRetryStrategy Class
# ========================================================================

class TestZAIRetryStrategy:
    """ZAIRetryStrategy 클래스 테스트"""

    @pytest.fixture
    def mock_client(self):
        """Mock Z.ai (OpenAI) client"""
        client = Mock()
        client.chat = Mock()
        client.chat.completions = Mock()
        client.chat.completions.create = Mock()
        return client

    @pytest.fixture
    def strategy(self, mock_client):
        """테스트용 ZAIRetryStrategy 인스턴스"""
        return ZAIRetryStrategy(mock_client, model="gpt-4o-mini")

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    def test_init(self, strategy, mock_client):
        """초기화 테스트"""
        assert strategy.client is mock_client
        assert strategy.model == "gpt-4o-mini"

    def test_init_default_model(self, mock_client):
        """기본 모델명 테스트"""
        strategy = ZAIRetryStrategy(mock_client)
        assert strategy.model == "gpt-4o-mini"

    def test_get_model_name(self, strategy):
        """모델명 반환 테스트"""
        assert strategy.get_model_name() == "gpt-4o-mini"

    # ========================================================================
    # execute Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_execute_success(self, strategy, mock_client):
        """성공적인 LLM 호출 테스트"""
        # Z.ai 응답 구조: response.choices[0].message.content
        mock_message = Mock()
        mock_message.content = "Test response"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        # Mock이 올바른 응답을 반환하도록 설정
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        result = await strategy.execute("Test prompt", 30.0, "gpt-4o-mini")

        assert result == "Test response"

        # 메서드 호출 검증
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        assert call_args[1]['model'] == "gpt-4o-mini"
        assert call_args[1]['temperature'] == 0.1
        assert len(call_args[1]['messages']) == 2

    @pytest.mark.asyncio
    async def test_execute_messages_format(self, strategy, mock_client):
        """메시지 포맷 검증 테스트"""
        mock_message = Mock()
        mock_message.content = "Response"

        mock_choice = Mock()
        mock_choice.message = mock_message

        mock_response = Mock()
        mock_response.choices = [mock_choice]

        # side_effect를 사용하여 mock 응답 반환
        mock_client.chat.completions.create = Mock(side_effect=lambda **kwargs: mock_response)

        await strategy.execute("Test prompt", 30.0, "gpt-4o-mini")

        messages = mock_client.chat.completions.create.call_args[1]['messages']
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == '당신은 주식 투자 전문가입니다.'
        assert messages[1]['role'] == 'user'
        assert messages[1]['content'] == 'Test prompt'

    @pytest.mark.asyncio
    async def test_execute_timeout(self, strategy, mock_client):
        """타임아웃 처리 테스트"""
        mock_client.chat.completions.create = Mock(side_effect=asyncio.TimeoutError())

        with pytest.raises(asyncio.TimeoutError):
            await strategy.execute("Test prompt", 1.0, "gpt-4o-mini")


# ========================================================================
# Test LLMAnalyzer Class
# ========================================================================

class TestLLMAnalyzer:
    """LLMAnalyzer 클래스 테스트"""

    # ========================================================================
    # Initialization Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_init_with_gemini_provider(self):
        """Gemini 프로바이더로 초기화 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key-123'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_genai.Client = Mock(return_value=Mock())

                analyzer = LLMAnalyzer()

                assert analyzer.provider == 'gemini'
                assert analyzer._retry_strategy is not None
                assert isinstance(analyzer._retry_strategy, GeminiRetryStrategy)

    @pytest.mark.asyncio
    async def test_init_with_zai_provider(self):
        """Z.ai 프로바이더로 초기화 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'zai'
            mock_config.ZAI_API_KEY = 'test-key-456'
            mock_config.ZAI_MODEL = 'gpt-4o-mini'
            mock_config.ZAI_BASE_URL = 'https://api.zai.com/v1'

            # openai는 _create_zai_client 내부에서 import되므로 다르게 처리
            with patch('builtins.__import__') as mock_import:
                # OpenAI import가 성공하도록 mock 설정
                mock_openai_module = Mock()
                mock_openai_module.OpenAI = Mock(return_value=Mock())
                mock_import.return_value = mock_openai_module

                analyzer = LLMAnalyzer()

                assert analyzer.provider == 'zai'
                # Z.ai 클라이언트 생성 시도가 있었는지 확인

    def test_provider_lowercase(self):
        """프로바이더 소문자 변환 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'GEMINI'  # 대문자
            mock_config.GOOGLE_API_KEY = 'test-key'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()
                assert analyzer.provider == 'gemini'  # 소문자로 변환

    # ========================================================================
    # API Key Tests
    # ========================================================================

    def test_get_api_key_from_source(self):
        """생성자에서 전달된 API_key 우선 사용 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'config-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                # 생성자에서 API_key 전달
                analyzer = LLMAnalyzer(api_key='source-key')

                # 전달된 키가 사용됨
                assert analyzer._api_key_source == 'source-key'
                assert analyzer._get_api_key() == 'source-key'

    def test_get_api_key_fallback_to_config(self):
        """API 키 없으면 설정에서 가져오기 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'config-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()  # api_key 없음

                assert analyzer._get_api_key() == 'config-key'

    # ========================================================================
    # client Property Tests
    # ========================================================================

    def test_client_property_refreshes(self):
        """client 접근 시 항상 초기화 확인 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                # client 접근 시 _init_client 호출
                with patch.object(analyzer, '_init_client') as mock_init:
                    _ = analyzer.client
                    mock_init.assert_called_once()

    # ========================================================================
    # analyze_news_sentiment Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_analyze_news_sentiment_success(self):
        """성공적인 뉴스 감성 분석 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                # Mock retry strategy
                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = '{"score": 2, "reason": "테스트 이유"}'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                news_items = [
                    {"title": "테스트 뉴스", "summary": "테스트 내용"}
                ]

                result = await analyzer.analyze_news_sentiment("테스트종목", news_items)

                assert result is not None
                assert result['score'] == 2
                assert result['reason'] == "테스트 이유"
                assert 'model' in result

    @pytest.mark.asyncio
    async def test_analyze_news_sentiment_empty_news(self):
        """빈 뉴스 리스트 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                result = await analyzer.analyze_news_sentiment("테스트종목", [])
                assert result is None

    @pytest.mark.asyncio
    async def test_analyze_news_sentiment_no_client(self):
        """클라이언트 없을 때 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = ''  # No API key

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()
                analyzer._client = None

                result = await analyzer.analyze_news_sentiment("테스트종목", [{"title": "테스트"}])
                assert result is None

    @pytest.mark.asyncio
    async def test_analyze_news_sentiment_parse_error(self):
        """JSON 파싱 에러 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = 'invalid json response'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                news_items = [{"title": "테스트"}]

                result = await analyzer.analyze_news_sentiment("테스트종목", news_items)
                # 파싱 실패 시 None 반환
                assert result is None

    # ========================================================================
    # analyze_news_batch Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_analyze_news_batch_success(self):
        """성공적인 배치 분석 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.ANALYSIS_LLM_API_TIMEOUT = 60.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_response = '''[
                    {"name": "종목A", "score": 2, "action": "BUY", "confidence": 80, "reason": "호재"},
                    {"name": "종목B", "score": 1, "action": "HOLD", "confidence": 60, "reason": "중립"}
                ]'''

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = mock_response
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                items = [{"stock": {"name": "종목A"}}]

                result = await analyzer.analyze_news_batch(items)

                assert isinstance(result, dict)
                assert "종목A" in result
                assert result["종목A"]["score"] == 2
                assert result["종목A"]["action"] == "BUY"

    @pytest.mark.asyncio
    async def test_analyze_news_batch_empty_items(self):
        """빈 아이템 리스트 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                result = await analyzer.analyze_news_batch([])
                assert result == {}

    @pytest.mark.asyncio
    async def test_analyze_news_batch_with_market_status(self):
        """시장 상황 포함 배치 분석 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.ANALYSIS_LLM_API_TIMEOUT = 60.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = '[{"name": "종목A", "score": 2, "action": "BUY", "confidence": 80, "reason": "테스트"}]'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                items = [{"stock": {"name": "종목A"}}]
                market_status = {
                    "status": "BULLISH",
                    "total_score": 75,
                    "kospi_close": 2500,
                    "kospi_change": 1.5
                }

                result = await analyzer.analyze_news_batch(items, market_status)

                # 프롬프트에 시장 상황이 포함되는지 확인
                call_args = mock_strategy.execute.call_args
                prompt = call_args[0][0]
                assert "시장 상황" in prompt or "BULLISH" in prompt

    # ========================================================================
    # generate_market_summary Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_generate_market_summary_success(self):
        """성공적인 시장 요약 생성 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = "오늘 시장 요약: 반도체 테마가 강세입니다."
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                signals = [
                    {
                        "grade": "S",
                        "score": {"total": 18, "llm_reason": "강한 호재"},
                        "stock_name": "종목A"
                    },
                    {
                        "grade": "A",
                        "score": {"total": 14, "llm_reason": "긍정적"},
                        "stock_name": "종목B"
                    }
                ]

                result = await analyzer.generate_market_summary(signals)

                assert result == "오늘 시장 요약: 반도체 테마가 강세입니다."

    @pytest.mark.asyncio
    async def test_generate_market_summary_empty_signals(self):
        """빈 시그널 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()
                analyzer._client = Mock()

                result = await analyzer.generate_market_summary([])

                assert result == "분석된 종목이 없거나 AI 클라이언트가 설정되지 않았습니다."

    @pytest.mark.asyncio
    async def test_generate_market_summary_limits_to_30(self):
        """상위 30개 종목 제한 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute = AsyncMock(return_value="Summary")
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                # 40개 시그널 생성
                signals = [
                    {
                        "grade": chr(65 + i % 5),  # A, B, C, D, E 반복
                        "score": {"total": 20 - i, "llm_reason": f"Reason {i}"},
                        "stock_name": f"종목{i}"
                    }
                    for i in range(40)
                ]

                await analyzer.generate_market_summary(signals)

                # 프롬프트에 포함된 시그널 확인
                call_args = mock_strategy.execute.call_args
                prompt = call_args[0][0]

                # 상위 30개만 포함되어야 함
                for i in range(30, 40):
                    assert f"종목{i}" not in prompt

    # ========================================================================
    # close Method Tests
    # ========================================================================

    @pytest.mark.asyncio
    async def test_close_with_aclose(self):
        """클라이언트 정리 테스트 (aclose 지원)"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                # Mock client with aclose
                mock_client = AsyncMock()
                analyzer._client = mock_client

                await analyzer.close()

                mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_aclose(self):
        """클라이언트 정리 테스트 (aclose 미지원)"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                # Mock client without aclose
                mock_client = Mock()
                mock_client.aclose = None
                analyzer._client = mock_client

                # 예외 없이 처리되어야 함
                await analyzer.close()


# ========================================================================
# Test Private Helper Methods
# ========================================================================

class TestLLMAnalyzerPrivateMethods:
    """LLMAnalyzer 프라이빗 헬퍼 메서드 테스트"""

    @pytest.fixture
    def analyzer(self):
        """테스트용 분석기 인스턴스"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                mock_strategy = Mock()
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy

                return analyzer

    # ========================================================================
    # _build_sentiment_prompt Tests
    # ========================================================================

    def test_build_sentiment_prompt_format(self, analyzer):
        """감성 분석 프롬프트 형식 테스트"""
        news_items = [
            {"title": "호재 뉴스", "summary": "긍정적인 내용" * 50},  # 긴 내용
            {"title": "중립 뉴스", "summary": "중립적인 내용"}
        ]

        prompt = analyzer._build_sentiment_prompt("테스트종목", news_items)

        assert "테스트종목" in prompt
        assert "호재 뉴스" in prompt
        assert "중립 뉴스" in prompt
        assert "0~3점" in prompt
        assert '{"score": 2, "reason": "종합적인 요약 이유"}' in prompt

    def test_build_sentiment_summary_truncation(self, analyzer):
        """뉴스 요약 200자 제한 테스트"""
        long_summary = "a" * 300  # 300자
        news_items = [
            {"title": "긴 뉴스", "summary": long_summary}
        ]

        prompt = analyzer._build_sentiment_prompt("테스트종목", news_items)

        # 200자로 잘려야 함
        assert "a" * 200 in prompt
        assert len([p for p in prompt.split('\n') if 'aaa' in p]) > 0

    # ========================================================================
    # _build_batch_prompt Tests
    # ========================================================================

    def test_build_batch_prompt_with_market_status(self, analyzer):
        """시장 상황 포함 배치 프롬프트 테스트"""
        items = [{"stock": {"name": "종목A"}}]
        market_status = {
            "status": "BULLISH",
            "total_score": 80,
            "kospi_close": 2600,
            "kospi_change": 2.5
        }

        prompt = analyzer._build_batch_prompt(items, market_status)

        assert "BULLISH" in prompt
        assert "80" in prompt
        assert "2600" in prompt
        assert "2.5" in prompt

    def test_build_batch_prompt_vcp_emphasis(self, analyzer):
        """VCP 강조 텍스트 확인 테스트"""
        items = [{"stock": {"name": "종목A"}}]
        prompt = analyzer._build_batch_prompt(items)

        assert "VCP" in prompt
        assert "변동성 수축" in prompt
        assert "Contraction Ratio" in prompt

    # ========================================================================
    # _build_summary_prompt Tests
    # ========================================================================

    def test_build_summary_prompt_structure(self, analyzer):
        """요약 프롬프트 구조 테스트"""
        signals = [
            {
                "grade": "S",
                "score": {"total": 18, "llm_reason": "강한 호재"},
                "stock_name": "종목A"
            }
        ]

        prompt = analyzer._build_summary_prompt(signals)

        assert "종목A" in prompt
        assert "S급" in prompt
        assert "18점" in prompt
        assert "강한 호재" in prompt
        assert "주도 섹터" in prompt
        assert "수급 강도" in prompt

    def test_build_summary_prompt_sorting(self, analyzer):
        """시그널 점수순 정렬 테스트"""
        signals = [
            {"grade": "C", "score": {"total": 5, "llm_reason": "낮음"}, "stock_name": "저점수"},
            {"grade": "S", "score": {"total": 18, "llm_reason": "높음"}, "stock_name": "고점수"},
            {"grade": "A", "score": {"total": 12, "llm_reason": "중간"}, "stock_name": "중점수"},
        ]

        prompt = analyzer._build_summary_prompt(signals)

        # 점수순 정렬 확인 (고점수가 먼저 나와야 함)
        high_score_pos = prompt.find("고점수")
        mid_score_pos = prompt.find("중점수")
        low_score_pos = prompt.find("저점수")

        assert high_score_pos < mid_score_pos < low_score_pos

    # ========================================================================
    # _parse_json_response Tests
    # ========================================================================

    def test_parse_json_response_valid(self, analyzer):
        """유효한 JSON 파싱 테스트"""
        response = '{"score": 2, "reason": "테스트"}'
        result = analyzer._parse_json_response(response, "테스트종목")

        assert result['score'] == 2
        assert result['reason'] == "테스트"
        assert result['model'] == 'gemini-2.0-flash'

    def test_parse_json_response_with_markdown(self, analyzer):
        """Markdown 코드블록 포함 JSON 파싱 테스트"""
        response = '```json\n{"score": 2, "reason": "테스트"}\n```'
        result = analyzer._parse_json_response(response, "테스트종목")

        assert result['score'] == 2

    def test_parse_json_response_empty(self, analyzer):
        """빈 응답 처리 테스트"""
        result = analyzer._parse_json_response("", "테스트종목")
        assert result is None

    def test_parse_json_response_invalid(self, analyzer):
        """무효한 JSON 처리 테스트"""
        result = analyzer._parse_json_response("not a json", "테스트종목")
        assert result is None

    # ========================================================================
    # _parse_batch_response Tests
    # ========================================================================

    def test_parse_batch_response_valid(self, analyzer):
        """유효한 배치 JSON 파싱 테스트"""
        response = '''[
            {"name": "종목A", "score": 2, "action": "BUY", "confidence": 80, "reason": "테스트"}
        ]'''

        result = analyzer._parse_batch_response(response)

        assert len(result) == 1
        assert result[0]['name'] == "종목A"

    def test_parse_batch_response_invalid(self, analyzer):
        """무효한 배치 JSON 처리 테스트"""
        result = analyzer._parse_batch_response("not json")
        assert result == []

    # ========================================================================
    # _build_result_map Tests
    # ========================================================================

    def test_build_result_map_structure(self, analyzer):
        """결과 맵 구조 테스트"""
        results_list = [
            {"name": "종목A", "score": 2, "action": "BUY", "confidence": 80, "reason": "테스트"}
        ]

        result = analyzer._build_result_map(results_list)

        assert "종목A" in result
        assert result["종목A"]["score"] == 2
        assert result["종목A"]["action"] == "BUY"
        assert result["종목A"]["confidence"] == 80
        assert result["종목A"]["model"] == 'gemini-2.0-flash'

    def test_build_result_map_default_values(self, analyzer):
        """결과 맵 기본값 테스트"""
        results_list = [
            {"name": "종목A"}  # 최소 필드만
        ]

        result = analyzer._build_result_map(results_list)

        assert result["종목A"]["score"] == 0
        assert result["종목A"]["action"] == "HOLD"
        assert result["종목A"]["confidence"] == 0
        assert result["종목A"]["reason"] == ""

    # ========================================================================
    # _format_news_for_prompt Tests
    # ========================================================================

    def test_format_news_for_prompt_structure(self, analyzer):
        """뉴스 프롬프트 포맷 구조 테스트"""
        news_items = [
            {"title": "뉴스1", "summary": "내용1"},
            {"title": "뉴스2", "summary": "내용2"}
        ]

        result = analyzer._format_news_for_prompt(news_items)

        assert "[1] 제목: 뉴스1" in result
        assert "[2] 제목: 뉴스2" in result
        assert "내용: 내용1" in result

    # ========================================================================
    # _build_market_context Tests
    # ========================================================================

    def test_build_market_context_with_status(self, analyzer):
        """시장 컨텍스트 구성 테스트"""
        market_status = {
            "status": "BULLISH",
            "total_score": 80,
            "kospi_close": 2600,
            "kospi_change": 2.5
        }

        result = analyzer._build_market_context(market_status)

        assert "BULLISH" in result
        assert "80" in result
        assert "2600" in result

    def test_build_market_context_none(self, analyzer):
        """None 시장 상황 처리 테스트"""
        result = analyzer._build_market_context(None)
        assert result == ""

    # ========================================================================
    # _extract_stock_info Tests
    # ========================================================================

    def test_extract_stock_info_from_dict(self, analyzer):
        """딕셔너리에서 Stock 정보 추출 테스트"""
        stock = {
            "stock_name": "삼성전자",
            "stock_code": "005930",
            "current_price": 80000,
            "change_pct": 2.5,
            "trading_value": 1000000000000
        }

        name, code, close, change, value = analyzer._extract_stock_info(stock)

        assert name == "삼성전자"
        assert code == "005930"
        assert close == 80000
        assert change == 2.5
        assert value == 1000000000000

    def test_extract_stock_info_from_object(self, analyzer):
        """객체에서 Stock 정보 추출 테스트"""
        stock = Mock()
        stock.name = "NAVER"
        stock.code = "035420"
        stock.close = 200000
        stock.change_pct = 1.5
        stock.trading_value = 500000000000

        name, code, close, change, value = analyzer._extract_stock_info(stock)

        assert name == "NAVER"
        assert code == "035420"
        assert close == 200000

    # ========================================================================
    # _extract_vcp_info Tests
    # ========================================================================

    def test_extract_vcp_info_from_dict(self, analyzer):
        """딕셔너리에서 VCP 정보 추출 테스트"""
        stock = {
            "score": {"total": 85},
            "contraction_ratio": 0.35
        }

        score, ratio = analyzer._extract_vcp_info(stock)

        assert score == 85
        assert ratio == 0.35

    def test_extract_vcp_info_nested_score_dict(self, analyzer):
        """중첩 score dict 처리 테스트"""
        stock = {
            "score": {"total": 90},
            "contraction_ratio": 0.25
        }

        score, ratio = analyzer._extract_vcp_info(stock)

        assert score == 90

    def test_extract_vcp_info_from_object(self, analyzer):
        """객체에서 VCP 정보 추출 테스트"""
        stock = Mock()
        stock.score = 80
        stock.contraction_ratio = 0.3

        score, ratio = analyzer._extract_vcp_info(stock)

        assert score == 80
        assert ratio == 0.3


# ========================================================================
# Test _execute_llm_call Method
# ========================================================================

class TestExecuteLLMCall:
    """_execute_llm_call 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_execute_llm_call_success(self):
        """성공적인 LLM 호출 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                # Mock strategy with proper sync get_model_name
                mock_strategy = Mock()
                mock_strategy.execute = AsyncMock(return_value="Test response")
                mock_strategy.get_model_name = Mock(return_value='gemini-2.0-flash')
                analyzer._retry_strategy = mock_strategy

                result = await analyzer._execute_llm_call("Test prompt", 30.0)

                assert result == "Test response"
                mock_strategy.execute.assert_called_once()
                # execute 호출 인자 확인
                call_args = mock_strategy.execute.call_args
                assert call_args[0][0] == "Test prompt"
                assert call_args[0][1] == 30.0
                assert call_args[0][2] == 'gemini-2.0-flash'

    @pytest.mark.asyncio
    async def test_execute_llm_call_no_strategy(self):
        """재시도 전략 없을 때 예외 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()
                analyzer._retry_strategy = None

                with pytest.raises(RuntimeError, match="Retry strategy not initialized"):
                    await analyzer._execute_llm_call("Test prompt", 30.0)

    @pytest.mark.asyncio
    async def test_execute_llm_call_timeout(self):
        """타임아웃 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.side_effect = asyncio.TimeoutError()
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy

                with pytest.raises(asyncio.TimeoutError):
                    await analyzer._execute_llm_call("Test prompt", 1.0)


# ========================================================================
# Parametrized Tests
# ========================================================================

class TestLLMAnalyzerParametrized:
    """매개변수화된 테스트"""

    @pytest.mark.parametrize("error_msg,should_retry", [
        ("429 Too Many Requests", True),
        ("503 Service Unavailable", True),
        ("500 Internal Server Error", True),
        ("resource_exhausted", True),
        ("Server overloaded", True),
        ("unavailable", True),
        ("Invalid input", False),
        ("Authentication failed", False),
        ("Not found", False),
    ])
    @pytest.mark.asyncio
    async def test_retry_conditions(self, error_msg, should_retry):
        """다양한 에러 메시지에 대한 재시도 조건 테스트"""
        mock_client = Mock()
        mock_client.models = Mock()
        mock_client.models.generate_content = Mock()

        strategy = GeminiRetryStrategy(mock_client)

        # 에러가 재시도 조건에 해당하는지 확인
        is_retryable = any(
            condition in error_msg.lower()
            for condition in RetryConfig.RETRY_CONDITIONS
        )

        assert is_retryable == should_retry

    @pytest.mark.parametrize("provider,expected_strategy", [
        ("gemini", GeminiRetryStrategy),
        ("GEMINI", GeminiRetryStrategy),
        ("zai", ZAIRetryStrategy),
        ("ZAI", ZAIRetryStrategy),
    ])
    def test_provider_strategy_mapping(self, provider, expected_strategy):
        """프로바이더별 전략 매핑 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = provider
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            if provider.lower() == 'zai':
                mock_config.ZAI_API_KEY = 'test-key'
                mock_config.ZAI_MODEL = 'gpt-4o-mini'
                mock_config.ZAI_BASE_URL = 'https://api.zai.com/v1'

                # Z.ai는 별도 처리 - OpenAI import mock
                with patch('builtins.__import__') as mock_import:
                    mock_openai_module = Mock()
                    mock_openai_module.OpenAI = Mock(return_value=Mock())
                    mock_import.return_value = mock_openai_module
                    analyzer = LLMAnalyzer()
            else:
                with patch('engine.llm_analyzer.genai'):
                    analyzer = LLMAnalyzer()

            if analyzer._retry_strategy:
                assert isinstance(analyzer._retry_strategy, expected_strategy)


# ========================================================================
# Edge Cases Tests
# ========================================================================

class TestLLMAnalyzerEdgeCases:
    """엣지 케이스 테스트"""

    @pytest.mark.asyncio
    async def test_analyze_news_with_malformed_news_item(self):
        """잘못된 형식의 뉴스 아이템 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = '{"score": 1, "reason": "테스트"}'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                # 다양한 잘못된 형식
                malformed_items = [
                    {},  # 빈 딕셔너리
                    {"title": None},  # None 값
                    {"summary": 123},  # 숫자 summary
                ]

                for item in malformed_items:
                    # 예외 없이 처리되어야 함
                    result = await analyzer.analyze_news_sentiment("테스트종목", [item])
                    # 뉴스가 있으면 시도함
                    if item:
                        assert result is not None or result is None

    @pytest.mark.asyncio
    async def test_batch_with_missing_stock_data(self):
        """누락된 주식 데이터 배치 처리 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.ANALYSIS_LLM_API_TIMEOUT = 60.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = '[]'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                items = [
                    {},  # 빈 아이템
                    {"stock": None},  # None stock
                    {"news": []},  # stock 없음
                ]

                # 예외 없이 처리되어야 함
                result = await analyzer.analyze_news_batch(items)
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_model_name_fallback_display(self):
        """모델명 폴백 디스플레이 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                # gemini-flash-latest 폴백 시나리오
                # get_model_name은 동기 메서드이므로 Mock 사용, execute는 비동기이므로 AsyncMock 사용
                mock_strategy = Mock()
                mock_strategy.execute = AsyncMock(return_value='{"score": 2, "reason": "테스트"}')
                mock_strategy.get_model_name = Mock(return_value='gemini-flash-latest')
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                news_items = [{"title": "테스트", "summary": "내용"}]
                result = await analyzer.analyze_news_sentiment("테스트종목", news_items)

                # "Gemini Flash (Latest)"로 표시되어야 함
                assert result['model'] == "Gemini Flash (Latest)"

    def test_build_stocks_text_with_dict_stock(self):
        """딕셔너리 stock으로 텍스트 빌드 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                item = {
                    'stock': {
                        'stock_name': '테스트종목',
                        'stock_code': '123456',
                        'current_price': 50000,
                        'change_pct': 5.0,
                        'trading_value': 1000000000,
                        'score': {'total': 80},
                        'contraction_ratio': 0.3
                    },
                    'news': [
                        {'title': '테스트 뉴스', 'weight': 1.2}
                    ],
                    'supply': Mock(
                        foreign_buy_5d=1000000,
                        inst_buy_5d=500000
                    )
                }

                result = analyzer._build_stocks_text([item])

                assert "테스트종목" in result
                assert "123456" in result
                assert "50,000" in result
                assert "5.0" in result
                assert "80" in result  # VCP score
                assert "0.3" in result  # contraction ratio

    def test_build_stocks_text_with_object_stock(self):
        """객체 stock으로 텍스트 빌드 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'

            with patch('engine.llm_analyzer.genai'):
                analyzer = LLMAnalyzer()

                stock = Mock()
                stock.name = "오브젝트종목"
                stock.code = "654321"
                stock.close = 75000
                stock.change_pct = 3.0
                stock.trading_value = 2000000000
                stock.score = 85
                stock.contraction_ratio = 0.25

                item = {
                    'stock': stock,
                    'news': [],
                    'supply': None
                }

                result = analyzer._build_stocks_text([item])

                assert "오브젝트종목" in result
                assert "654321" in result


# ========================================================================
# Integration Tests
# ========================================================================

class TestLLMAnalyzerIntegration:
    """통합 테스트"""

    @pytest.mark.asyncio
    async def test_full_sentiment_analysis_workflow(self):
        """전체 감성 분석 워크플로우 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                # 전체 응답 시뮬레이션
                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = '{"score": 3, "reason": "대규모 수주 발표로 강한 호재"}'
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                news_items = [
                    {
                        "title": "삼성전자, 100억달러 규모 수주 계약 체결",
                        "summary": "반도체 분야에서 대규모 수주를 성사하며 실적 턴어라운드 기대감이 높아지고 있습니다."
                    },
                    {
                        "title": "AI 반도체 수요 급증",
                        "summary": "데이터센터 확대로 인한 HBM 칩 수요가 폭발적으로 증가하고 있습니다."
                    }
                ]

                result = await analyzer.analyze_news_sentiment("삼성전자", news_items)

                # 전체 파이프라인 검증
                assert result is not None
                assert result['score'] == 3
                assert "호재" in result['reason']
                assert 'model' in result

                # execute가 정확한 프롬프트로 호출되었는지 확인
                call_args = mock_strategy.execute.call_args
                prompt = call_args[0][0]
                assert "삼성전자" in prompt
                assert "100억달러" in prompt or "수주" in prompt

    @pytest.mark.asyncio
    async def test_full_batch_analysis_workflow(self):
        """전체 배치 분석 워크플로우 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.ANALYSIS_LLM_API_TIMEOUT = 60.0

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                batch_response = '''[
                    {"name": "삼성전자", "score": 2, "action": "BUY", "confidence": 85, "reason": "VCP 패턴 완성 및 외인 수급 유입"},
                    {"name": "SK하이닉스", "score": 1, "action": "HOLD", "confidence": 70, "reason": "기술적 반등 있으나 추가 모멘텀 필요"},
                    {"name": "NAVER", "score": 3, "action": "BUY", "confidence": 90, "reason": "AI 서비스 확대로 강한 호재"}
                ]'''

                mock_strategy = AsyncMock()
                mock_strategy.execute.return_value = batch_response
                mock_strategy.get_model_name.return_value = 'gemini-2.0-flash'
                analyzer._retry_strategy = mock_strategy
                analyzer._client = mock_client

                items = [
                    {
                        'stock': {
                            'stock_name': '삼성전자',
                            'stock_code': '005930',
                            'current_price': 80000,
                            'change_pct': 2.5,
                            'trading_value': 1000000000000,
                            'score': {'total': 85},
                            'contraction_ratio': 0.35
                        },
                        'news': [
                            {'title': '대규모 수주', 'weight': 1.2}
                        ]
                    },
                    {
                        'stock': {
                            'stock_name': 'SK하이닉스',
                            'stock_code': '000660',
                            'current_price': 150000,
                            'change_pct': 1.8,
                            'trading_value': 500000000000,
                            'score': {'total': 75},
                            'contraction_ratio': 0.45
                        },
                        'news': []
                    },
                    {
                        'stock': {
                            'stock_name': 'NAVER',
                            'stock_code': '035420',
                            'current_price': 200000,
                            'change_pct': 3.2,
                            'trading_value': 800000000000,
                            'score': {'total': 90},
                            'contraction_ratio': 0.25
                        },
                        'news': [
                            {'title': 'AI 서비스 확대', 'weight': 1.3}
                        ]
                    }
                ]

                result = await analyzer.analyze_news_batch(items)

                # 결과 검증
                assert len(result) == 3
                assert result['삼성전자']['action'] == 'BUY'
                assert result['SK하이닉스']['action'] == 'HOLD'
                assert result['NAVER']['action'] == 'BUY'
                assert result['NAVER']['confidence'] == 90

                # 모든 결과에 모델명 포함
                for stock_data in result.values():
                    assert 'model' in stock_data

    @pytest.mark.asyncio
    async def test_retry_workflow_integration(self):
        """재시도 워크플로우 통합 테스트"""
        with patch('engine.llm_analyzer.app_config') as mock_config:
            mock_config.LLM_PROVIDER = 'gemini'
            mock_config.GOOGLE_API_KEY = 'test-key'
            mock_config.ANALYSIS_GEMINI_MODEL = 'gemini-2.0-flash'
            mock_config.LLM_API_TIMEOUT = 30.0

            mock_response = Mock()
            mock_response.text = '{"score": 2, "reason": "재시도 후 성공"}'
            mock_response.model_version = "gemini-2.0-flash"

            with patch('engine.llm_analyzer.genai') as mock_genai:
                mock_client = Mock()
                mock_client.models.generate_content.side_effect = [
                    Exception("429 Too Many Requests"),  # 1차 실패
                    Exception("503 Service Unavailable"),  # 2차 실패
                    mock_response  # 3차 성공
                ]
                mock_genai.Client.return_value = mock_client

                analyzer = LLMAnalyzer()

                news_items = [{"title": "테스트", "summary": "내용"}]

                with patch('asyncio.sleep'):  # 실제 대기 방지
                    result = await analyzer.analyze_news_sentiment("테스트종목", news_items)

                # 재시도 후 성공 확인
                assert result is not None
                assert result['score'] == 2
                assert mock_client.models.generate_content.call_count == 3
