#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Screener supply score helper functions.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable

from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite as _load_json_payload_from_sqlite,
    save_json_payload_to_sqlite as _save_json_payload_to_sqlite,
)

_TOSS_SUPPLY_CACHE_LOCK = threading.Lock()
_TOSS_SUPPLY_CACHE: OrderedDict[tuple[str, str, str], dict[str, Any]] = OrderedDict()
_TOSS_SUPPLY_CACHE_MAX_ENTRIES = 2_048
_TOSS_SUPPLY_SQLITE_MAX_ROWS = 8_192
_TOSS_SUPPLY_SQLITE_SCHEMA_VERSION = "screener_toss_supply_v1"


def _stable_token_to_int(token: str) -> int:
    normalized = str(token or "")
    if normalized.isdigit():
        try:
            return int(normalized)
        except Exception:
            pass
    acc = 17
    for char in normalized:
        acc = (acc * 31 + ord(char)) % 2_000_000_000
    return int(acc)


def _normalize_data_dir(data_dir: str | None) -> str | None:
    if not data_dir:
        return None
    normalized = str(data_dir).strip()
    if not normalized:
        return None
    return os.path.abspath(normalized)


def _current_toss_supply_cache_slot(
    *,
    now: datetime | None = None,
    interval_minutes: int = 15,
) -> str:
    normalized_now = now or datetime.now()
    normalized_interval = max(1, int(interval_minutes))
    minute_bucket = (normalized_now.minute // normalized_interval) * normalized_interval
    return normalized_now.replace(minute=minute_bucket, second=0, microsecond=0).strftime("%Y%m%d%H%M")


def _toss_supply_sqlite_context(
    *,
    data_dir: str,
    ticker: str,
    cache_slot: str,
) -> tuple[str, tuple[int, int]]:
    ticker_key = str(ticker).zfill(6)
    slot_key = str(cache_slot or "latest")
    sqlite_key = os.path.join(
        data_dir,
        ".screener_toss_supply_cache",
        f"{ticker_key}__{slot_key}.snapshot",
    )
    signature_seed = f"{ticker_key}:{slot_key}:{_TOSS_SUPPLY_SQLITE_SCHEMA_VERSION}"
    signature = (
        _stable_token_to_int(signature_seed),
        _stable_token_to_int(f"{signature_seed[::-1]}:toss_supply"),
    )
    return sqlite_key, signature


def _normalize_toss_supply_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    try:
        foreign_value = int(float(payload.get("foreign", 0)))
        institution_value = int(float(payload.get("institution", 0)))
    except (TypeError, ValueError):
        return None

    details_payload = payload.get("details")
    normalized_details: list[dict[str, int]] = []
    if isinstance(details_payload, list):
        for row in details_payload[:5]:
            if not isinstance(row, dict):
                continue
            try:
                foreign_1d = int(float(row.get("netForeignerBuyVolume", 0)))
                institution_1d = int(float(row.get("netInstitutionBuyVolume", 0)))
            except (TypeError, ValueError):
                continue
            normalized_details.append(
                {
                    "netForeignerBuyVolume": foreign_1d,
                    "netInstitutionBuyVolume": institution_1d,
                }
            )

    return {
        "foreign": foreign_value,
        "institution": institution_value,
        "details": normalized_details,
        "days": int(payload.get("days", 5) or 5),
    }


def _load_cached_toss_supply_payload(
    *,
    data_dir: str,
    ticker: str,
    cache_slot: str,
) -> dict[str, Any] | None:
    ticker_key = str(ticker).zfill(6)
    memory_key = (str(data_dir), ticker_key, str(cache_slot))
    with _TOSS_SUPPLY_CACHE_LOCK:
        cached = _TOSS_SUPPLY_CACHE.get(memory_key)
        if isinstance(cached, dict):
            _TOSS_SUPPLY_CACHE.move_to_end(memory_key)
            return dict(cached)

    sqlite_key, sqlite_signature = _toss_supply_sqlite_context(
        data_dir=data_dir,
        ticker=ticker_key,
        cache_slot=cache_slot,
    )
    try:
        loaded, payload = _load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            logger=None,
        )
    except Exception:
        return None
    if not loaded or not isinstance(payload, dict):
        return None

    normalized = _normalize_toss_supply_payload(payload)
    if not isinstance(normalized, dict):
        return None

    with _TOSS_SUPPLY_CACHE_LOCK:
        _TOSS_SUPPLY_CACHE[memory_key] = dict(normalized)
        _TOSS_SUPPLY_CACHE.move_to_end(memory_key)
        while len(_TOSS_SUPPLY_CACHE) > _TOSS_SUPPLY_CACHE_MAX_ENTRIES:
            _TOSS_SUPPLY_CACHE.popitem(last=False)
    return normalized


def _save_cached_toss_supply_payload(
    *,
    data_dir: str,
    ticker: str,
    cache_slot: str,
    payload: dict[str, Any],
) -> None:
    normalized = _normalize_toss_supply_payload(payload)
    if not isinstance(normalized, dict):
        return

    ticker_key = str(ticker).zfill(6)
    memory_key = (str(data_dir), ticker_key, str(cache_slot))
    with _TOSS_SUPPLY_CACHE_LOCK:
        _TOSS_SUPPLY_CACHE[memory_key] = dict(normalized)
        _TOSS_SUPPLY_CACHE.move_to_end(memory_key)
        while len(_TOSS_SUPPLY_CACHE) > _TOSS_SUPPLY_CACHE_MAX_ENTRIES:
            _TOSS_SUPPLY_CACHE.popitem(last=False)

    sqlite_key, sqlite_signature = _toss_supply_sqlite_context(
        data_dir=data_dir,
        ticker=ticker_key,
        cache_slot=cache_slot,
    )
    try:
        _save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            payload=normalized,
            max_rows=_TOSS_SUPPLY_SQLITE_MAX_ROWS,
            logger=None,
        )
    except Exception:
        return


def calculate_supply_score_with_toss(
    *,
    ticker: str,
    toss_collector: Any,
    fallback_fn: Callable[[str], dict[str, int]],
    score_supply_from_toss_trend_fn: Callable[[dict[str, Any] | None], dict[str, int]],
    cache_data_dir: str | None = None,
    cache_interval_minutes: int = 15,
) -> dict[str, int]:
    """Toss 수급 조회를 시도하고 실패 시 CSV fallback을 수행한다."""
    normalized_data_dir = _normalize_data_dir(cache_data_dir)
    cache_slot = _current_toss_supply_cache_slot(interval_minutes=cache_interval_minutes)
    ticker_key = str(ticker).zfill(6)

    if normalized_data_dir is not None:
        cached_payload = _load_cached_toss_supply_payload(
            data_dir=normalized_data_dir,
            ticker=ticker_key,
            cache_slot=cache_slot,
        )
        if isinstance(cached_payload, dict):
            return score_supply_from_toss_trend_fn(cached_payload)

    try:
        trend_data = toss_collector.get_investor_trend(ticker_key, days=5)
        normalized_trend = _normalize_toss_supply_payload(trend_data)
        if not normalized_trend:
            return fallback_fn(ticker_key)
        if normalized_data_dir is not None:
            _save_cached_toss_supply_payload(
                data_dir=normalized_data_dir,
                ticker=ticker_key,
                cache_slot=cache_slot,
                payload=normalized_trend,
            )
        return score_supply_from_toss_trend_fn(normalized_trend)
    except Exception:
        return fallback_fn(ticker_key)


def calculate_supply_score_from_csv(
    *,
    ticker: str,
    inst_by_ticker: dict[str, Any],
    target_datetime: Any,
    score_supply_from_csv_fn: Callable[[Any, Any], dict[str, int]],
) -> dict[str, int]:
    """CSV 기반 수급 점수를 계산한다."""
    try:
        if not inst_by_ticker:
            return {"score": 0, "foreign_1d": 0, "inst_1d": 0}

        ticker_inst = inst_by_ticker.get(ticker)
        return score_supply_from_csv_fn(ticker_inst=ticker_inst, target_datetime=target_datetime)
    except Exception:
        return {"score": 0, "foreign_1d": 0, "inst_1d": 0}


__all__ = ["calculate_supply_score_with_toss", "calculate_supply_score_from_csv"]
