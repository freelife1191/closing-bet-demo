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

if GEMINI_AVAILABLE:
    if not hasattr(genai, "configure"):
        def _compat_configure(**_kwargs):
            return None
        genai.configure = _compat_configure  # type: ignore[attr-defined]

    if not hasattr(genai, "GenerativeModel"):
        class _CompatGenerativeModel:  # pragma: no cover - 레거시 테스트 호환용
            def __init__(self, *_args, **_kwargs):
                pass

            def start_chat(self, history=None):
                _ = history
                raise NotImplementedError("Legacy GenerativeModel API is unavailable.")

        genai.GenerativeModel = _CompatGenerativeModel  # type: ignore[attr-defined]

from .prompts import get_welcome_message
from .markdown_utils import (
    _extract_reasoning_and_answer as _extract_reasoning_and_answer_impl,
)
from .storage import (
    MemoryManager as _BaseMemoryManager,
    HistoryManager as _BaseHistoryManager,
)
from .chat_handlers import handle_chat, handle_chat_stream
from .core_command_mixin import CoreCommandMixin
from .core_data_context_mixin import CoreDataContextMixin
from .runtime_setup_service import (
    resolve_api_key as _resolve_api_key_impl,
    init_models as _init_models_impl,
    create_genai_client as _create_genai_client_impl,
    close_client as _close_client_impl,
    load_stock_map as _load_stock_map_impl,
    init_user_profile_from_env as _init_user_profile_from_env_impl,
    get_user_profile as _get_user_profile_impl,
    update_user_profile as _update_user_profile_impl,
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

    def _resolve_legacy_session_id(self) -> str:
        if self.sessions:
            latest_session = max(
                self.sessions.values(),
                key=lambda session: session.get("updated_at", ""),
            )
            return latest_session.get("id")
        return self.create_session(save_immediate=False)

    def add(self, role: str, message: str) -> None:
        """레거시 테스트 호환: 기본 세션에 메시지를 추가한다."""
        session_id = self._resolve_legacy_session_id()
        self.add_message(session_id, role, message)

    def count(self) -> int:
        """레거시 테스트 호환: 기본 세션 메시지 수를 반환한다."""
        if not self.sessions:
            return 0
        session_id = self._resolve_legacy_session_id()
        return len(self.get_messages(session_id))

class KRStockChatbot(CoreCommandMixin, CoreDataContextMixin):
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
        self._default_session_id: Optional[str] = None
        
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
        if GEMINI_AVAILABLE and callable(getattr(genai, "configure", None)):
            try:
                genai.configure(api_key=self.api_key)
            except Exception as e:
                logger.debug("Legacy genai.configure skipped: %s", e)

        self.available_models = []
        self.current_model_name = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self.client = None

        self.client = _create_genai_client_impl(
            api_key=self.api_key,
            gemini_available=GEMINI_AVAILABLE,
            user_id=user_id,
            logger=logger,
        )
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
        self._default_session_id = None

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

    def _run_legacy_model_chat(self, user_message: str, target_model_name: str) -> Optional[str]:
        model_cls = getattr(genai, "GenerativeModel", None) if GEMINI_AVAILABLE else None
        if not callable(model_cls):
            return None

        try:
            legacy_model = model_cls(target_model_name)
            if not hasattr(legacy_model, "start_chat"):
                return None
            chat_session = legacy_model.start_chat(history=[])
            response = chat_session.send_message(user_message)
            return getattr(response, "text", str(response))
        except Exception as error:
            logger.debug("Legacy model chat path skipped: %s", error)
            return None

    def chat(
        self,
        user_message: str,
        session_id: str = None,
        model: str = None,
        files: list = None,
        watchlist: list = None,
        persona: str = None,
        api_key: str = None,
        owner_id: str = None,
        model_name: str = None,
        as_dict: bool = False,
    ) -> Any:
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
        resolved_model_name = model_name or model
        resolved_session_id = session_id or self._default_session_id

        if model_name:
            legacy_response = self._run_legacy_model_chat(
                user_message=user_message,
                target_model_name=resolved_model_name,
            )
            if legacy_response is not None:
                return legacy_response

        result = handle_chat(
            bot=self,
            user_message=user_message,
            session_id=resolved_session_id,
            model=resolved_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
            api_key=api_key,
            owner_id=owner_id,
        )
        if isinstance(result, dict):
            session_from_result = result.get("session_id")
            if session_from_result:
                self._default_session_id = session_from_result
        if as_dict:
            return result
        if isinstance(result, dict):
            return result.get("response", "")
        return result

    def chat_stream(
        self,
        user_message: str,
        session_id: str = None,
        model: str = None,
        files: list = None,
        watchlist: list = None,
        persona: str = None,
        api_key: str = None,
        owner_id: str = None,
        model_name: str = None,
    ) -> Dict[str, Any]:
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
        resolved_model_name = model_name or model
        resolved_session_id = session_id or self._default_session_id
        yield from handle_chat_stream(
            bot=self,
            user_message=user_message,
            session_id=resolved_session_id,
            model=resolved_model_name,
            files=files,
            watchlist=watchlist,
            persona=persona,
            api_key=api_key,
            owner_id=owner_id,
        )

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
