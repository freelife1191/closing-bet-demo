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
    """요청/환경변수 기준 API 키 우선순위를 적용한다."""
    return (
        api_key
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY", "")
        or os.getenv("ZAI_API_KEY", "")
    )


def init_models(
    current_model_name: str,
    default_model_name: str,
) -> Tuple[List[str], str]:
    """사용 가능한 모델 목록과 현재 모델명을 초기화한다."""
    env_models = os.getenv(
        "CHATBOT_AVAILABLE_MODELS",
        "gemini-2.0-flash,gemini-2.5-flash,gemini-3-flash-preview",
    )
    model_names = [m.strip() for m in env_models.split(",") if m.strip()]
    if not model_names:
        model_names = [default_model_name]

    resolved_model = current_model_name
    if resolved_model not in model_names:
        resolved_model = model_names[0]

    return model_names, resolved_model


def _default_client_factory(api_key: str) -> Any:
    """google-genai Client 기본 팩토리."""
    from google import genai

    return genai.Client(api_key=api_key)


def create_genai_client(
    api_key: str,
    gemini_available: bool,
    user_id: str,
    logger: Any,
    client_factory: Optional[Callable[[str], Any]] = None,
) -> Optional[Any]:
    """Gemini 클라이언트를 생성한다."""
    if not gemini_available or not api_key:
        logger.warning(
            "Gemini not available or API Config missing (GEMINI_AVAILABLE=%s, api_key=%s)",
            gemini_available,
            bool(api_key),
        )
        return None

    try:
        factory = client_factory or _default_client_factory
        client = factory(api_key)
        logger.debug("Gemini initialized for user: %s (KeyLen: %s)", user_id, len(api_key))
        return client
    except Exception as e:
        logger.error("Gemini initialization failed: %s", e)
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
    """요청별 활성 클라이언트를 선택한다 (사용자 키 우선)."""
    active_client = current_client
    if api_key:
        try:
            factory = client_factory or _default_client_factory
            active_client = factory(api_key)
        except Exception as e:
            logger.error("Temp client init failed: %s", e)
            return None, f"⚠️ API Key 오류: {str(e)}"

    if not active_client:
        debug_info = f"KeyLen: {len(str(api_key))} " if api_key else "Key: None "
        return (
            None,
            (
                "⚠️ AI 모델이 설정되지 않았습니다. "
                f"({debug_info}) [설정 > API & 기능]에서 API Key를 등록하거나, "
                "구글 로그인을 진행해주세요. (데이터 초기화 후에는 재설정이 필요합니다)"
            ),
        )

    return active_client, None
