#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Stock Chatbot Core - 메인 챗봇 클래스
Gemini AI 연동 및 대화 처리 로직 (지원 모델 설정 가능)
"""

import os
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .prompts import get_welcome_message, SYSTEM_PERSONA
from .markdown_utils import (
    _normalize_markdown_text,
    _extract_reasoning_and_answer as _extract_reasoning_and_answer_impl,
)
from .storage import (
    MemoryManager as _BaseMemoryManager,
    HistoryManager as _BaseHistoryManager,
)
from .stock_context import (
    fetch_stock_history,
    fetch_institutional_trend,
    fetch_signal_history,
    format_stock_context,
)
from .chat_handlers import handle_chat, handle_chat_stream
from .daily_suggestions_service import generate_daily_suggestions
from .session_access import (
    is_ephemeral_command as _is_ephemeral_command_impl,
    ensure_session_access as _ensure_session_access_impl,
    prepare_chat_request as _prepare_chat_request_impl,
)
from .command_service import (
    clear_current_session_messages as _clear_current_session_messages_impl,
    handle_clear_command as _handle_clear_command_impl,
    handle_refresh_command as _handle_refresh_command_impl,
    render_model_command_help as _render_model_command_help_impl,
    handle_model_command as _handle_model_command_impl,
    render_memory_view as _render_memory_view_impl,
    render_memory_help as _render_memory_help_impl,
    handle_memory_write_action as _handle_memory_write_action_impl,
    handle_memory_command as _handle_memory_command_impl,
    handle_command as _handle_command_impl,
    get_status_message as _get_status_message_impl,
    get_help as _get_help_impl,
)
from .intent_context import (
    build_vcp_intent_context as _build_vcp_intent_context_impl,
    build_news_intent_context as _build_news_intent_context_impl,
    resolve_primary_intent_context as _resolve_primary_intent_context_impl,
    build_watchlist_context_bundle as _build_watchlist_context_bundle_impl,
    build_additional_context as _build_additional_context_impl,
)
from .payload_service import (
    collect_market_context as _collect_market_context_impl,
    compose_system_prompt as _compose_system_prompt_impl,
    build_api_history as _build_api_history_impl,
    build_content_parts as _build_content_parts_impl,
    build_chat_payload as _build_chat_payload_impl,
)
from .data_service import (
    get_cached_data as _get_cached_data_impl,
    fetch_mock_data as _fetch_mock_data_impl,
    fetch_market_gate as _fetch_market_gate_impl,
    fetch_vcp_ai_analysis as _fetch_vcp_ai_analysis_impl,
    fetch_latest_news as _fetch_latest_news_impl,
    fetch_jongga_data as _fetch_jongga_data_impl,
    build_daily_suggestions_cache_key as _build_daily_suggestions_cache_key_impl,
    get_cached_daily_suggestions as _get_cached_daily_suggestions_impl,
    build_watchlist_suggestions_text as _build_watchlist_suggestions_text_impl,
    build_daily_suggestions_prompt as _build_daily_suggestions_prompt_impl,
    default_daily_suggestions as _default_daily_suggestions_impl,
)
from .stock_query_service import (
    detect_stock_query_from_stock_map as _detect_stock_query_from_stock_map_impl,
    detect_stock_query_from_vcp_data as _detect_stock_query_from_vcp_data_impl,
    detect_stock_query as _detect_stock_query_impl,
    fallback_response as _fallback_response_impl,
    format_stock_info as _format_stock_info_impl,
)
from .intent_detail_service import (
    contains_any_keyword as _contains_any_keyword_impl,
    build_closing_bet_context as _build_closing_bet_context_impl,
    build_market_gate_context as _build_market_gate_context_impl,
    build_watchlist_detailed_context as _build_watchlist_detailed_context_impl,
    build_watchlist_summary_context as _build_watchlist_summary_context_impl,
)
from .runtime_setup_service import (
    resolve_api_key as _resolve_api_key_impl,
    init_models as _init_models_impl,
    create_genai_client as _create_genai_client_impl,
    close_client as _close_client_impl,
    load_stock_map as _load_stock_map_impl,
    init_user_profile_from_env as _init_user_profile_from_env_impl,
    get_user_profile as _get_user_profile_impl,
    update_user_profile as _update_user_profile_impl,
    resolve_active_client as _resolve_active_client_impl,
)

logger = logging.getLogger(__name__)

# 기본 설정 (env에서 오버라이드 가능)
DEFAULT_GEMINI_MODEL = "gemini-2.0-flash-lite"

# ... import lines ...

# 데이터 저장 경로 설정
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"


def _extract_reasoning_and_answer(text: str, is_streaming: bool = False) -> Tuple[str, str]:
    """하위호환용 파서 노출 (tests/chatbot에서 직접 import)."""
    return _extract_reasoning_and_answer_impl(text, is_streaming=is_streaming)


class MemoryManager(_BaseMemoryManager):
    """`chatbot.core` 하위호환용 래퍼 (DATA_DIR 바인딩)."""

    def __init__(self, user_id: str):
        super().__init__(user_id=user_id, data_dir=DATA_DIR)


class HistoryManager(_BaseHistoryManager):
    """`chatbot.core` 하위호환용 래퍼 (DATA_DIR 바인딩)."""

    def __init__(self, user_id: str):
        super().__init__(user_id=user_id, data_dir=DATA_DIR)

class KRStockChatbot:
    """
    VCP 기반 한국 주식 분석 챗봇
    """
    
    def __init__(
        self, 
        user_id: str,
        api_key: str = None,
        data_fetcher: Optional[Callable] = None
    ):
        self.user_id = user_id
        self.memory = MemoryManager(user_id)
        self.history = HistoryManager(user_id)
        self.data_fetcher = data_fetcher
        
        # Cache initialization
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60
        
        # Data maps initialization
        self.stock_map = {} 
        self.ticker_map = {}
        self._load_stock_map()
        
        # .env에서 사용자 프로필 초기화 (기본값이 없을 때만 설정)
        self._init_user_profile_from_env()

        # Gemini 초기화 - ZAI_API_KEY도 확인 (무료 티어 지원)
        self.api_key = _resolve_api_key_impl(api_key)
        self.available_models = []
        self.current_model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.client = None

        self.client = _create_genai_client_impl(
            api_key=self.api_key,
            gemini_available=GEMINI_AVAILABLE,
            user_id=user_id,
            logger=logger,
        )
        if self.client:
            self._init_models()

    def close(self):
        """Gemini 클라이언트 리소스 정리 (asyncio Task pending 오류 방지)"""
        _close_client_impl(self.client, logger)
        self.client = None
            
        # 데이터 캐시
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 60 # 60 seconds TTL
        
        # 전체 종목 리스트 로드 (이름/코드 매핑용)
        self.stock_map = {} # name -> ticker
        self.ticker_map = {} # ticker -> name
        self._load_stock_map()

    def _load_stock_map(self):
        """korean_stocks_list.csv 로드하여 매핑 생성"""
        self.stock_map, self.ticker_map = _load_stock_map_impl(DATA_DIR, logger)

    def _init_user_profile_from_env(self):
        """환경변수에서 초기 사용자 프로필 설정"""
        _init_user_profile_from_env_impl(self.memory, logger)

    def get_user_profile(self) -> Dict[str, Any]:
        """사용자 프로필 조회"""
        return _get_user_profile_impl(self.memory)

    def update_user_profile(self, name: str, persona: str):
        """사용자 프로필 업데이트"""
        return _update_user_profile_impl(self.memory, name, persona)

    def _init_models(self):
        """Available models setup from env"""
        self.available_models, self.current_model_name = _init_models_impl(
            current_model_name=self.current_model_name,
            default_model_name=DEFAULT_GEMINI_MODEL,
        )

    def get_available_models(self) -> List[str]:
        return self.available_models

    def set_model(self, model_name: str):
        if model_name in self.available_models:
            self.current_model_name = model_name
            return True
        return False
        
    def _get_cached_data(self) -> Dict[str, Any]:
        """Fetch market data with caching"""
        return _get_cached_data_impl(self)

    def _fetch_mock_data(self):
        """폴백용 Mock 데이터 (실제 데이터 로드 실패 시)"""
        return _fetch_mock_data_impl()

    def _fetch_market_gate(self) -> Dict[str, Any]:
        """market_gate.json에서 최신 시장 상태 조회"""
        return _fetch_market_gate_impl(DATA_DIR)

    def _fetch_vcp_ai_analysis(self) -> str:
        """kr_ai_analysis.json에서 VCP AI 분석 결과 조회 (상위 5개)"""
        return _fetch_vcp_ai_analysis_impl(DATA_DIR)

    def _build_daily_suggestions_cache_key(
        self,
        watchlist: Optional[list],
        persona: Optional[str],
    ) -> str:
        """일일 추천 캐시 키 생성."""
        return _build_daily_suggestions_cache_key_impl(watchlist, persona)

    def _get_cached_daily_suggestions(
        self,
        cache_key: str,
        now: datetime,
    ) -> Optional[List[Dict[str, str]]]:
        """유효한(1시간 이내) 일일 추천 캐시 조회."""
        return _get_cached_daily_suggestions_impl(self.memory, cache_key, now)

    def _build_watchlist_suggestions_text(self, watchlist: Optional[list]) -> str:
        """일일 추천 생성용 관심종목 상세 텍스트 구성."""
        return _build_watchlist_suggestions_text_impl(
            watchlist=watchlist,
            stock_map=self.stock_map,
            format_stock_context_fn=self._format_stock_context,
        )

    def _build_daily_suggestions_prompt(
        self,
        persona: Optional[str],
        market_summary: str,
        vcp_text: str,
        news_text: str,
        watchlist_text: str,
    ) -> str:
        """페르소나별 추천 질문 생성 프롬프트 구성."""
        return _build_daily_suggestions_prompt_impl(
            persona=persona,
            market_summary=market_summary,
            vcp_text=vcp_text,
            news_text=news_text,
            watchlist_text=watchlist_text,
            fetch_jongga_data_fn=self._fetch_jongga_data,
        )

    def _default_daily_suggestions(self) -> List[Dict[str, str]]:
        """일일 추천 생성 실패 시 기본 질문 세트."""
        return _default_daily_suggestions_impl()

    def get_daily_suggestions(self, watchlist: list = None, persona: str = None) -> List[Dict[str, str]]:
        """시장/데이터/페르소나 기반 일일 추천 질문 5개 생성."""
        return generate_daily_suggestions(
            bot=self,
            watchlist=watchlist,
            persona=persona,
        )

    def _fetch_latest_news(self) -> str:
        """jongga_v2_latest.json 내 뉴스 데이터 조회 (최근 5개)"""
        return _fetch_latest_news_impl(DATA_DIR)

    def _fetch_stock_history(self, ticker: str) -> str:
        """daily_prices.csv에서 최근 5일 주가 조회"""
        return fetch_stock_history(DATA_DIR, ticker, logger)

    def _fetch_institutional_trend(self, ticker: str) -> str:
        """all_institutional_trend_data.csv에서 수급 데이터 조회 (최근 5일)"""
        return fetch_institutional_trend(DATA_DIR, ticker)

    def _fetch_signal_history(self, ticker: str) -> str:
        """signals_log.csv에서 VCP 시그널 이력 조회"""
        return fetch_signal_history(DATA_DIR, ticker)

    def _format_stock_context(self, name: str, ticker: str) -> str:
        """종목 관련 모든 데이터 통합"""
        price_txt = self._fetch_stock_history(ticker)
        trend_txt = self._fetch_institutional_trend(ticker)
        signal_txt = self._fetch_signal_history(ticker)
        return format_stock_context(name, ticker, price_txt, trend_txt, signal_txt)

    def _detect_stock_query_from_stock_map(self, message: str) -> Optional[str]:
        """전체 종목 맵에서 종목 질문을 감지해 상세 컨텍스트를 반환한다."""
        return _detect_stock_query_from_stock_map_impl(
            message=message,
            stock_map=self.stock_map,
            ticker_map=self.ticker_map,
            format_stock_context_fn=self._format_stock_context,
            logger=logger,
        )

    def _detect_stock_query_from_vcp_data(self, message: str) -> Optional[str]:
        """VCP 캐시 데이터에서 종목 질문을 감지해 요약 정보를 반환한다."""
        vcp_stocks = self._get_cached_data().get("vcp_stocks", [])
        return _detect_stock_query_from_vcp_data_impl(
            message=message,
            vcp_stocks=vcp_stocks,
            format_stock_info_fn=self._format_stock_info,
        )

    def _detect_stock_query(self, message: str) -> Optional[str]:
        """
        종목 관련 질문 감지.
        현재 동작 호환을 위해 VCP 캐시 기반 탐지 경로를 우선(사실상 단일) 사용한다.
        """
        return _detect_stock_query_impl(
            message=message,
            get_cached_data_fn=self._get_cached_data,
            detect_stock_query_from_vcp_data_fn=lambda msg, stocks: _detect_stock_query_from_vcp_data_impl(
                message=msg,
                vcp_stocks=stocks,
                format_stock_info_fn=self._format_stock_info,
            ),
        )

    def _normalize_markdown_response(self, text: str) -> str:
        """LLM 응답의 자주 깨지는 마크다운 문법을 안전하게 정규화"""
        return _normalize_markdown_text(text)

    def _resolve_active_client(self, api_key: Optional[str]) -> Tuple[Optional[Any], Optional[str]]:
        """요청별 활성 클라이언트 선택 (사용자 키 우선)."""
        return _resolve_active_client_impl(
            current_client=self.client,
            api_key=api_key,
            logger=logger,
        )

    def _is_ephemeral_command(self, user_message: str, files: Optional[list]) -> bool:
        """저장 없이 처리 가능한 경량 명령 여부."""
        return _is_ephemeral_command_impl(user_message, files)

    def _ensure_session_access(
        self,
        session_id: Optional[str],
        target_model_name: str,
        is_ephemeral: bool,
        owner_id: Optional[str],
        reuse_session_id_on_owner_mismatch: bool,
    ) -> str:
        """세션 생성/검증 및 소유권 확인."""
        return _ensure_session_access_impl(
            history=self.history,
            session_id=session_id,
            target_model_name=target_model_name,
            is_ephemeral=is_ephemeral,
            owner_id=owner_id,
            reuse_session_id_on_owner_mismatch=reuse_session_id_on_owner_mismatch,
            logger=logger,
        )

    def _execute_command(
        self,
        user_message: str,
        session_id: str,
        files: Optional[list],
        is_ephemeral: bool,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        슬래시 명령 실행.
        returns: (handled, response, error_message)
        """
        if files or not user_message.startswith("/"):
            return False, None, None

        try:
            cmd_resp = self._handle_command(user_message, session_id)
            should_save = not is_ephemeral
            self.history.add_message(session_id, "user", user_message, save=should_save)
            self.history.add_message(session_id, "model", cmd_resp, save=should_save)
            return True, cmd_resp, None
        except Exception as e:
            logger.error(f"Command error: {e}")
            return True, None, f"⚠️ 명령어 처리 중 오류가 발생했습니다: {str(e)}"

    def _collect_market_context(
        self,
    ) -> Tuple[Dict[str, Any], List[dict], Dict[str, Any], Dict[str, Any]]:
        """챗봇 프롬프트용 시장/시그널 컨텍스트를 수집한다."""
        return _collect_market_context_impl(self)

    def _contains_any_keyword(self, user_message: str, keywords: List[str]) -> bool:
        """문자열에 키워드 중 하나라도 포함되는지 확인."""
        return _contains_any_keyword_impl(user_message, keywords)

    def _build_closing_bet_context(self) -> Tuple[str, str]:
        """종가베팅 의도 컨텍스트/지시문 생성."""
        return _build_closing_bet_context_impl(
            memory=self.memory,
            user_id=self.user_id,
            fetch_jongga_data_fn=self._fetch_jongga_data,
            logger=logger,
        )

    def _build_market_gate_context(self, market_gate_data: Dict[str, Any]) -> str:
        """시장/마켓게이트 질문용 컨텍스트 생성."""
        return _build_market_gate_context_impl(market_gate_data)

    def _build_watchlist_detailed_context(
        self,
        watchlist: List[str],
        vcp_data: List[dict],
    ) -> str:
        """관심종목 상세 컨텍스트 생성."""
        return _build_watchlist_detailed_context_impl(
            watchlist=watchlist,
            vcp_data=vcp_data,
            stock_map=self.stock_map,
            format_stock_context_fn=self._format_stock_context,
        )

    def _build_watchlist_summary_context(self, watchlist: List[str], vcp_data: List[dict]) -> str:
        """관심종목 VCP 요약 컨텍스트 생성."""
        return _build_watchlist_summary_context_impl(watchlist, vcp_data)

    def _build_vcp_intent_context(self) -> Tuple[str, str]:
        """VCP/수급 질문용 컨텍스트 생성."""
        return _build_vcp_intent_context_impl(self._fetch_vcp_ai_analysis)

    def _build_news_intent_context(self) -> Tuple[str, str]:
        """뉴스/이슈 질문용 컨텍스트 생성."""
        return _build_news_intent_context_impl(self._fetch_latest_news)

    def _resolve_primary_intent_context(
        self,
        user_message: str,
        market_gate_data: Dict[str, Any],
    ) -> Tuple[str, str, bool]:
        """메시지의 1차 의도를 해석해 컨텍스트/지시문을 반환한다."""
        return _resolve_primary_intent_context_impl(
            user_message=user_message,
            market_gate_data=market_gate_data,
            contains_any_keyword=self._contains_any_keyword,
            build_closing_bet_context=self._build_closing_bet_context,
            build_market_gate_context=self._build_market_gate_context,
            build_vcp_intent_context_fn=self._build_vcp_intent_context,
            build_news_intent_context_fn=self._build_news_intent_context,
        )

    def _build_watchlist_context_bundle(
        self,
        user_message: str,
        watchlist: Optional[list],
        vcp_data: List[dict],
    ) -> Tuple[str, str]:
        """관심종목 컨텍스트와(필요 시) 지시문 오버라이드를 생성한다."""
        return _build_watchlist_context_bundle_impl(
            user_message=user_message,
            watchlist=watchlist,
            vcp_data=vcp_data,
            contains_any_keyword=self._contains_any_keyword,
            build_watchlist_detailed_context=self._build_watchlist_detailed_context,
            build_watchlist_summary_context=self._build_watchlist_summary_context,
        )

    def _build_additional_context(
        self,
        user_message: str,
        watchlist: Optional[list],
        vcp_data: List[dict],
        market_gate_data: Dict[str, Any],
    ) -> Tuple[str, str, bool]:
        """질문 의도별 추가 컨텍스트와 intent 문구를 구성한다."""
        return _build_additional_context_impl(
            user_message=user_message,
            watchlist=watchlist,
            vcp_data=vcp_data,
            market_gate_data=market_gate_data,
            resolve_primary_intent_context_fn=self._resolve_primary_intent_context,
            build_watchlist_context_bundle_fn=self._build_watchlist_context_bundle,
        )

    def _compose_system_prompt(
        self,
        user_message: str,
        target_model_name: str,
        market_data: Dict[str, Any],
        vcp_data: List[dict],
        sector_scores: Dict[str, Any],
        watchlist: Optional[list],
        persona: Optional[str],
        additional_context: str,
    ) -> str:
        """기본 시스템 프롬프트 + 질의별 컨텍스트 병합."""
        return _compose_system_prompt_impl(
            bot=self,
            user_message=user_message,
            target_model_name=target_model_name,
            market_data=market_data,
            vcp_data=vcp_data,
            sector_scores=sector_scores,
            watchlist=watchlist,
            persona=persona,
            additional_context=additional_context,
        )

    def _build_api_history(self, session_id: str) -> List[dict]:
        """Gemini SDK 전달용 히스토리(role/parts만 유지)."""
        return _build_api_history_impl(self, session_id)

    def _build_content_parts(
        self,
        files: Optional[list],
        system_prompt: str,
        intent_instruction: str,
        user_message: str,
        jongga_context: bool,
    ) -> List[Any]:
        """멀티모달 요청 payload(parts) 생성."""
        return _build_content_parts_impl(
            files=files,
            system_prompt=system_prompt,
            intent_instruction=intent_instruction,
            user_message=user_message,
            jongga_context=jongga_context,
        )

    def _format_user_history_message(self, user_message: str, files: Optional[list]) -> str:
        if not files:
            return user_message
        return f"{user_message} [파일 {len(files)}개 첨부됨]"

    def _persist_chat_history(
        self,
        session_id: str,
        user_message: str,
        files: Optional[list],
        bot_response: str,
    ) -> None:
        """대화 히스토리(유저/모델)를 저장한다."""
        user_history_msg = self._format_user_history_message(user_message, files)
        self.history.add_message(session_id, "user", user_history_msg)
        self.history.add_message(session_id, "model", bot_response)

    def _build_chat_payload(
        self,
        user_message: str,
        session_id: str,
        target_model_name: str,
        files: Optional[list],
        watchlist: Optional[list],
        persona: Optional[str],
    ) -> Tuple[List[dict], List[Any]]:
        """챗/스트림 공통 요청 payload(history + parts)를 구성한다."""
        return _build_chat_payload_impl(
            bot=self,
            user_message=user_message,
            session_id=session_id,
            target_model_name=target_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
        )

    def _prepare_chat_request(
        self,
        user_message: str,
        session_id: Optional[str],
        target_model_name: str,
        files: Optional[list],
        api_key: Optional[str],
        owner_id: Optional[str],
        reuse_session_id_on_owner_mismatch: bool,
    ) -> Tuple[Optional[Any], str, Optional[str], Optional[str], Optional[str]]:
        """채팅 공통 사전 처리 래퍼."""
        return _prepare_chat_request_impl(
            resolve_active_client=self._resolve_active_client,
            ensure_session_access_fn=self._ensure_session_access,
            execute_command=self._execute_command,
            user_message=user_message,
            session_id=session_id,
            target_model_name=target_model_name,
            files=files,
            api_key=api_key,
            owner_id=owner_id,
            reuse_session_id_on_owner_mismatch=reuse_session_id_on_owner_mismatch,
        )

    def chat(self, user_message: str, session_id: str = None, model: str = None, files: list = None, watchlist: list = None, persona: str = None, api_key: str = None, owner_id: str = None) -> Dict[str, Any]:
        """
        사용자 메시지 처리 및 응답 생성
        
        Args:
            user_message: 사용자 입력
            session_id: 세션 ID (없으면 생성)
            model: 사용할 모델명 (없으면 기본값)
            files: 첨부 파일 리스트
            watchlist: 사용자 관심종목 리스트
            persona: 특정 페르소나 지정 ('vcp' 등)
            api_key: (Optional) 사용자 제공 API Key
        """
        return handle_chat(
            bot=self,
            user_message=user_message,
            session_id=session_id,
            model=model,
            files=files,
            watchlist=watchlist,
            persona=persona,
            api_key=api_key,
            owner_id=owner_id,
        )

    def chat_stream(self, user_message: str, session_id: str = None, model: str = None, files: list = None, watchlist: list = None, persona: str = None, api_key: str = None, owner_id: str = None) -> Dict[str, Any]:
        """
        사용자 메시지 처리 및 응답 생성
        
        Args:
            user_message: 사용자 입력
            session_id: 세션 ID (없으면 생성)
            model: 사용할 모델명 (없으면 기본값)
            files: 첨부 파일 리스트
            watchlist: 사용자 관심종목 리스트
            persona: 특정 페르소나 지정 ('vcp' 등)
            api_key: (Optional) 사용자 제공 API Key
        """
        yield from handle_chat_stream(
            bot=self,
            user_message=user_message,
            session_id=session_id,
            model=model,
            files=files,
            watchlist=watchlist,
            persona=persona,
            api_key=api_key,
            owner_id=owner_id,
        )

    def _fetch_jongga_data(self) -> str:
        """jongga_v2_latest.json에서 최신 S/A급 종목 조회"""
        return _fetch_jongga_data_impl(DATA_DIR)

    def _fallback_response(self, user_message: str, vcp_data: list) -> str:
        """AI 사용 불가 시 폴백 응답"""
        return _fallback_response_impl(user_message, vcp_data)

    def _format_stock_info(self, stock: Dict) -> str:
        """종목 정보 포맷팅"""
        return _format_stock_info_impl(stock)

    def _clear_current_session_messages(self, session_id: Optional[str]) -> bool:
        """현재 세션 메시지를 초기화한다."""
        return _clear_current_session_messages_impl(self, session_id)

    def _handle_clear_command(self, parts: List[str], session_id: Optional[str]) -> str:
        """`/clear` 명령 처리."""
        return _handle_clear_command_impl(self, parts, session_id)

    def _handle_refresh_command(self) -> str:
        """데이터 캐시 초기화."""
        return _handle_refresh_command_impl(self)

    def _render_model_command_help(self) -> str:
        """`/model` 도움말 텍스트 렌더링."""
        return _render_model_command_help_impl(self)

    def _handle_model_command(self, parts: List[str], session_id: Optional[str]) -> str:
        """`/model` 명령 처리."""
        return _handle_model_command_impl(self, parts, session_id)

    def _render_memory_view(self) -> str:
        """저장된 메모리 목록 문자열 생성."""
        return _render_memory_view_impl(self)

    def _render_memory_help(self) -> str:
        """메모리 명령어 사용법 문자열."""
        return _render_memory_help_impl()

    def _handle_memory_write_action(self, action: str, args: List[str]) -> Optional[str]:
        """메모리 쓰기 액션(add/update/remove/clear)을 처리한다."""
        return _handle_memory_write_action_impl(self, action, args)

    def _handle_command(self, command: str, session_id: str = None) -> str:
        """명령어 처리"""
        return _handle_command_impl(self, command, session_id)
    
    def _handle_memory_command(self, args: list) -> str:
        """메모리 명령어 처리"""
        return _handle_memory_command_impl(self, args)
    
    def _get_status_message(self) -> str:
        """현재 상태 확인 메시지"""
        return _get_status_message_impl(self)
    
    def _get_help(self) -> str:
        """도움말"""
        return _get_help_impl()

    def get_welcome_message(self) -> str:
        """웰컴 메시지 반환 (VCP 데이터 기반)"""
        # Fetch current data to make welcome message dynamic
        data = self._get_cached_data()
        vcp_data = data.get("vcp_stocks", [])
        return get_welcome_message(vcp_data)

    def get_memory(self):
        return self.memory.to_dict()
        
    def update_memory(self, data):
        for k, v in data.items():
            self.memory.add(k, v)
            
    def clear_memory(self):
        self.memory.clear()
        
    def get_history(self):
        return self.history.to_dict()
    
    def clear_history(self):
        self.history.clear()
        
    def get_status(self):
        return {
            "user_id": self.user_id,
            "model": self.current_model_name,
            "available_models": self.get_available_models(),
            "memory_count": len(self.memory.view()),
            "history_count": len(self.history.get_all_sessions())
        }
