#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
챗봇 런타임 초기화/클라이언트/프로필 설정 서비스
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.kr_market_data_cache_service import load_csv_file

from .runtime_stock_map_cache import (
    build_stock_maps as _build_stock_maps_impl,
    clear_stock_map_cache as _clear_stock_map_cache_impl,
    file_signature as _stock_map_file_signature,
    load_stock_map_cache as _load_stock_map_cache_impl,
    save_stock_map_cache as _save_stock_map_cache_impl,
)


DEFAULT_PROFILE = {
    "name": "흑기사",
    "persona": "주식 투자를 배우고 있는 열정적인 투자자",
}


def resolve_api_key(api_key: Optional[str]) -> str:
    """[Deprecated] 사용자별 API 키 기능 제거됨 - 항상 빈 문자열 반환.

    Vertex AI 전환 후 인증은 프로젝트 단위 IAM(서비스 계정)으로만 이뤄진다.
    함수 시그니처는 하위 호환을 위해 유지하되 입력값을 무시한다.
    """
    del api_key
    return ""


def init_models(
    current_model_name: str,
    default_model_name: str,
) -> Tuple[List[str], str]:
    """사용 가능한 모델 목록과 현재 모델명을 초기화한다."""
    env_models = os.getenv(
        "CHATBOT_AVAILABLE_MODELS",
        "gemini-3.1-flash-lite-preview,gemini-3-flash-preview,gemini-3.1-pro-preview,gemini-2.5-flash",
    )
    model_names = [m.strip() for m in env_models.split(",") if m.strip()]
    if not model_names:
        model_names = [default_model_name]

    resolved_model = current_model_name
    if resolved_model not in model_names:
        resolved_model = model_names[0]

    return model_names, resolved_model


def _default_client_factory(_api_key: str = "") -> Any:
    """Vertex AI 기반 google-genai Client 기본 팩토리.

    api_key 인자는 하위 호환을 위해 받지만 무시된다 (Vertex 전환 이후).
    """
    from engine.genai_client import build_genai_client

    return build_genai_client()


def create_genai_client(
    api_key: str,
    gemini_available: bool,
    user_id: str,
    logger: Any,
    client_factory: Optional[Callable[[str], Any]] = None,
) -> Optional[Any]:
    """Vertex AI 기반 Gemini 클라이언트를 생성한다.

    api_key 인자는 무시된다 (Vertex 모드는 ADC 사용).
    """
    del api_key  # ignored - Vertex 모드는 ADC 사용
    if not gemini_available:
        logger.warning("google-genai 패키지 미설치로 Gemini 사용 불가")
        return None

    try:
        factory = client_factory or _default_client_factory
        client = factory("")
        logger.debug("Gemini(Vertex) initialized for user: %s", user_id)
        return client
    except Exception as e:
        logger.error("Gemini(Vertex) initialization failed: %s", e)
        return None


def close_client(client: Optional[Any], logger: Any) -> None:
    """Gemini 클라이언트 리소스 정리."""
    if not client:
        return

    try:
        if hasattr(client, "_api_client") and hasattr(client._api_client, "aclose"):
            pass
        logger.info("Gemini client resources released.")
    except Exception as e:
        logger.debug("Error during Gemini client close: %s", e)


def clear_stock_map_cache() -> None:
    _clear_stock_map_cache_impl()


def load_stock_map(data_dir: Path, logger: Any) -> Tuple[Dict[str, str], Dict[str, str]]:
    """korean_stocks_list.csv 로드하여 name<->ticker 매핑을 생성한다."""
    stock_map: Dict[str, str] = {}
    ticker_map: Dict[str, str] = {}

    try:
        path = data_dir / "korean_stocks_list.csv"
        if not path.exists():
            logger.warning("korean_stocks_list.csv not found")
            return stock_map, ticker_map

        signature = _stock_map_file_signature(path)
        if signature is None:
            return stock_map, ticker_map

        cached = _load_stock_map_cache_impl(
            data_dir=data_dir,
            source_path=path,
            signature=signature,
            logger=logger,
        )
        if cached is not None:
            stock_map, ticker_map = cached
            logger.debug("Loaded %s stocks from cache", len(stock_map))
            return stock_map, ticker_map

        df = load_csv_file(
            str(data_dir),
            "korean_stocks_list.csv",
            deep_copy=False,
            usecols=["name", "ticker"],
            signature=signature,
        )
        stock_map, ticker_map = _build_stock_maps_impl(df)
        _save_stock_map_cache_impl(
            data_dir=data_dir,
            source_path=path,
            signature=signature,
            stock_map=stock_map,
            ticker_map=ticker_map,
            logger=logger,
        )
        logger.debug("Loaded %s stocks from list", len(stock_map))
    except Exception as e:
        logger.error("Failed to load stock map: %s", e)

    return stock_map, ticker_map


def init_user_profile_from_env(memory: Any, logger: Any) -> None:
    """환경변수 USER_PROFILE 기준으로 초기 사용자 프로필을 저장한다."""
    profile = os.getenv("USER_PROFILE")
    if profile and not memory.memories:
        memory.add("user_profile", {"name": "흑기사", "persona": profile})
        logger.info("Initialized user profile from env")


def get_user_profile(memory: Any) -> Dict[str, Any]:
    """사용자 프로필 조회 (레거시 value wrapper 호환)."""
    profile = memory.get("user_profile")
    if profile and isinstance(profile, dict) and "value" in profile:
        val = profile["value"]
        if isinstance(val, dict):
            return val
        return {"name": "흑기사", "persona": str(val)}

    return dict(DEFAULT_PROFILE)


def update_user_profile(memory: Any, name: str, persona: str) -> Dict[str, Any]:
    """사용자 프로필 업데이트."""
    data = {"name": name, "persona": persona}
    memory.update("user_profile", data)
    return data


def resolve_active_client(
    current_client: Optional[Any],
    api_key: Optional[str],
    logger: Any,
    client_factory: Optional[Callable[[str], Any]] = None,
) -> Tuple[Optional[Any], Optional[str]]:
    """활성 클라이언트를 반환한다.

    Vertex AI 전환 이후 사용자별 API 키 입력 기능은 제거되었다.
    api_key/client_factory 인자는 하위 호환을 위해 받지만 무시된다.
    """
    del api_key, client_factory
    if not current_client:
        return (
            None,
            (
                "⚠️ AI 모델이 초기화되지 않았습니다. "
                "GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT 설정과 "
                "서비스 계정 키(GOOGLE_APPLICATION_CREDENTIALS)를 확인해주세요."
            ),
        )
    return current_client, None
