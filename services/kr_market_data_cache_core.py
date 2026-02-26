#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data Cache Core
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
from collections import OrderedDict
from typing import Any, Callable

import pandas as pd

from services.file_row_count_cache import get_cached_file_row_count
from services import kr_market_data_cache_sqlite_payload as sqlite_payload_cache


FILE_CACHE_LOCK = threading.Lock()
JSON_FILE_CACHE: OrderedDict[str, tuple[tuple[int, int], Any]] = OrderedDict()
CSV_FILE_CACHE: OrderedDict[
    tuple[str, tuple[str, ...] | None],
    tuple[tuple[int, int], pd.DataFrame],
] = OrderedDict()
LATEST_VCP_PRICE_MAP_CACHE: dict[str, Any] = {
    "signature": None,
    "value": {},
}
SCANNED_STOCK_COUNT_CACHE: dict[str, Any] = {
    "signature": None,
    "value": 0,
}
BACKTEST_PRICE_SNAPSHOT_CACHE: dict[str, Any] = {
    "signature": None,
    "df": pd.DataFrame(),
    "price_map": {},
}
JONGGA_RESULT_PAYLOADS_CACHE: dict[str, Any] = {
    "signature": None,
    "payloads": [],
}
_JSON_PAYLOAD_SQLITE_READY = sqlite_payload_cache.JSON_PAYLOAD_SQLITE_READY
_JSON_PAYLOAD_SQLITE_MAX_ROWS = sqlite_payload_cache.DEFAULT_JSON_PAYLOAD_SQLITE_MAX_ROWS
_CSV_PAYLOAD_SQLITE_READY = sqlite_payload_cache.CSV_PAYLOAD_SQLITE_READY
_CSV_PAYLOAD_SQLITE_MAX_ROWS = sqlite_payload_cache.DEFAULT_CSV_PAYLOAD_SQLITE_MAX_ROWS
_FULL_CSV_SQLITE_MAX_BYTES = 8 * 1024 * 1024
_JSON_FILE_CACHE_MAX_ENTRIES = 256
_CSV_FILE_CACHE_MAX_ENTRIES = 128
_LOGGER = logging.getLogger(__name__)


def _normalize_cache_path(filepath: str) -> str:
    return os.path.abspath(filepath)


def _get_lru_cache_entry(
    cache: OrderedDict[Any, Any],
    key: Any,
) -> Any | None:
    if key not in cache:
        return None
    value = cache[key]
    cache.move_to_end(key)
    return value


def _set_bounded_lru_cache_entry(
    cache: OrderedDict[Any, Any],
    key: Any,
    value: Any,
    *,
    max_entries: int,
) -> None:
    cache[key] = value
    cache.move_to_end(key)
    normalized_max_entries = max(1, int(max_entries))
    while len(cache) > normalized_max_entries:
        cache.popitem(last=False)


def file_signature(filepath: str) -> tuple[int, int] | None:
    try:
        stat = os.stat(filepath)
    except OSError:
        return None
    return int(stat.st_mtime_ns), int(stat.st_size)


def _annotate_csv_cache_metadata(
    *,
    frame: pd.DataFrame,
    filepath: str,
    signature: tuple[int, int],
    usecols: tuple[str, ...] | None,
) -> None:
    """
    CSV 원본 식별 메타데이터를 DataFrame attrs에 주입한다.

    하위 서비스에서 frame 객체 id가 바뀌어도(얕은 복사) 동일 원본임을 빠르게 식별해
    추가 집계/파싱 비용을 줄일 수 있다.
    """
    try:
        frame.attrs["kr_cache_filepath"] = str(filepath)
        frame.attrs["kr_cache_signature"] = (int(signature[0]), int(signature[1]))
        frame.attrs["kr_cache_usecols"] = tuple(usecols) if usecols is not None else None
    except Exception:
        # attrs 미지원/readonly 변형 프레임 방어
        return


def invalidate_file_cache(filepath: str) -> None:
    normalized_path = _normalize_cache_path(filepath)
    should_delete_json_sqlite = False
    should_delete_csv_sqlite = False
    with FILE_CACHE_LOCK:
        JSON_FILE_CACHE.pop(normalized_path, None)
        csv_keys_to_remove = [key for key in CSV_FILE_CACHE if key[0] == normalized_path]
        for key in csv_keys_to_remove:
            CSV_FILE_CACHE.pop(key, None)
        if normalized_path.endswith("daily_prices.csv"):
            LATEST_VCP_PRICE_MAP_CACHE["signature"] = None
            LATEST_VCP_PRICE_MAP_CACHE["value"] = {}
            BACKTEST_PRICE_SNAPSHOT_CACHE["signature"] = None
            BACKTEST_PRICE_SNAPSHOT_CACHE["df"] = pd.DataFrame()
            BACKTEST_PRICE_SNAPSHOT_CACHE["price_map"] = {}
        if normalized_path.endswith("korean_stocks_list.csv"):
            SCANNED_STOCK_COUNT_CACHE["signature"] = None
            SCANNED_STOCK_COUNT_CACHE["value"] = 0
        if "jongga_v2_results_" in normalized_path and normalized_path.endswith(".json"):
            JONGGA_RESULT_PAYLOADS_CACHE["signature"] = None
            JONGGA_RESULT_PAYLOADS_CACHE["payloads"] = []
        should_delete_json_sqlite = normalized_path.endswith(".json")
        should_delete_csv_sqlite = normalized_path.endswith(".csv")

    if should_delete_json_sqlite:
        _delete_json_payload_from_sqlite(normalized_path)
    if should_delete_csv_sqlite:
        _delete_csv_payload_from_sqlite(normalized_path)


def atomic_write_text(
    file_path: str,
    content: str,
    *,
    invalidate_fn: Callable[[str], None] = invalidate_file_cache,
) -> None:
    """텍스트 파일을 원자적으로 저장한다."""
    target_dir = os.path.dirname(file_path) or "."
    os.makedirs(target_dir, exist_ok=True)
    tmp_path = ""

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target_dir,
            delete=False,
        ) as tmp_file:
            tmp_file.write(content)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
            tmp_path = tmp_file.name

        os.replace(tmp_path, file_path)
        invalidate_fn(file_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _load_json_payload_from_path(
    filepath: str,
    *,
    signature: tuple[int, int] | None = None,
    deep_copy: bool = True,
) -> Any:
    """절대경로 JSON 파일을 시그니처 기반으로 캐시 로드한다."""
    normalized_path = _normalize_cache_path(filepath)
    file_sig = signature if signature is not None else file_signature(normalized_path)
    if file_sig is None:
        return {}

    with FILE_CACHE_LOCK:
        cached = _get_lru_cache_entry(JSON_FILE_CACHE, normalized_path)
        if cached and cached[0] == file_sig:
            if deep_copy:
                return copy.deepcopy(cached[1])
            return cached[1]

    found_in_sqlite, sqlite_payload = _load_json_payload_from_sqlite(
        filepath=normalized_path,
        signature=file_sig,
    )
    if found_in_sqlite:
        with FILE_CACHE_LOCK:
            _set_bounded_lru_cache_entry(
                JSON_FILE_CACHE,
                normalized_path,
                (file_sig, sqlite_payload),
                max_entries=_JSON_FILE_CACHE_MAX_ENTRIES,
            )
        if deep_copy:
            return copy.deepcopy(sqlite_payload)
        return sqlite_payload

    with open(normalized_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    with FILE_CACHE_LOCK:
        _set_bounded_lru_cache_entry(
            JSON_FILE_CACHE,
            normalized_path,
            (file_sig, payload),
            max_entries=_JSON_FILE_CACHE_MAX_ENTRIES,
        )
    _save_json_payload_to_sqlite(
        filepath=normalized_path,
        signature=file_sig,
        payload=payload,
    )

    if deep_copy:
        return copy.deepcopy(payload)
    return payload


def load_json_payload_from_path(filepath: str, *, deep_copy: bool = True) -> Any:
    """절대경로 JSON 파일을 시그니처 기반으로 캐시 로드한다."""
    return _load_json_payload_from_path(filepath, deep_copy=deep_copy)


def _load_json_payload_from_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
) -> tuple[bool, dict[str, Any]]:
    return sqlite_payload_cache.load_json_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        logger=_LOGGER,
    )


def _save_json_payload_to_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    payload: dict[str, Any],
) -> None:
    sqlite_payload_cache.save_json_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        payload=payload,
        max_rows=_JSON_PAYLOAD_SQLITE_MAX_ROWS,
        logger=_LOGGER,
    )


def _delete_json_payload_from_sqlite(filepath: str) -> None:
    sqlite_payload_cache.delete_json_payload_from_sqlite(
        filepath,
        logger=_LOGGER,
    )


def _load_csv_payload_from_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    usecols: tuple[str, ...] | None,
) -> pd.DataFrame | None:
    return sqlite_payload_cache.load_csv_payload_from_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=usecols,
        logger=_LOGGER,
    )


def _save_csv_payload_to_sqlite(
    *,
    filepath: str,
    signature: tuple[int, int],
    usecols: tuple[str, ...] | None,
    payload: pd.DataFrame,
) -> None:
    sqlite_payload_cache.save_csv_payload_to_sqlite(
        filepath=filepath,
        signature=signature,
        usecols=usecols,
        payload=payload,
        max_rows=_CSV_PAYLOAD_SQLITE_MAX_ROWS,
        logger=_LOGGER,
    )


def _delete_csv_payload_from_sqlite(filepath: str) -> None:
    sqlite_payload_cache.delete_csv_payload_from_sqlite(
        filepath,
        logger=_LOGGER,
    )


def _read_csv_with_usecols_fallback(
    *,
    filepath: str,
    usecols: tuple[str, ...] | None,
) -> pd.DataFrame:
    """usecols 스키마 불일치 시 전체 로드 후 가능한 컬럼만 투영해 반환한다."""
    read_kwargs: dict[str, Any] = {"low_memory": False}
    if usecols is not None:
        read_kwargs["usecols"] = list(usecols)

    try:
        return pd.read_csv(filepath, **read_kwargs)
    except ValueError as error:
        if usecols is None:
            raise

        _LOGGER.debug("CSV usecols fallback to full read (%s): %s", filepath, error)
        loaded = pd.read_csv(filepath, low_memory=False)
        existing_columns = [column for column in usecols if column in loaded.columns]
        if existing_columns:
            return loaded.loc[:, existing_columns]
        raise


def load_json_file(
    data_dir: str,
    filename: str,
    *,
    deep_copy: bool = True,
) -> dict[str, Any]:
    filepath = _normalize_cache_path(os.path.join(data_dir, filename))
    loaded = _load_json_payload_from_path(filepath, deep_copy=deep_copy)
    if isinstance(loaded, dict):
        return loaded
    return {}


def load_csv_file(
    data_dir: str,
    filename: str,
    *,
    deep_copy: bool = True,
    usecols: list[str] | tuple[str, ...] | None = None,
    signature: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """
    CSV 파일을 시그니처 기반으로 캐시 로드한다.

    deep_copy=True (기본): 호출자 변경이 캐시에 영향을 주지 않도록 완전 복사 반환
    deep_copy=False: 읽기 전용 경로에서 복사 비용을 줄이기 위해 얕은 복사 반환
    """
    filepath = _normalize_cache_path(os.path.join(data_dir, filename))
    normalized_usecols = tuple(str(col) for col in usecols) if usecols is not None else None
    cache_key = (filepath, normalized_usecols)
    file_sig = signature if signature is not None else file_signature(filepath)
    if file_sig is None:
        return pd.DataFrame()

    with FILE_CACHE_LOCK:
        cached = _get_lru_cache_entry(CSV_FILE_CACHE, cache_key)
        if cached and cached[0] == file_sig:
            _annotate_csv_cache_metadata(
                frame=cached[1],
                filepath=filepath,
                signature=file_sig,
                usecols=normalized_usecols,
            )
            return cached[1].copy(deep=deep_copy)

    use_sqlite_snapshot = normalized_usecols is not None
    if not use_sqlite_snapshot:
        use_sqlite_snapshot = int(file_sig[1]) <= int(_FULL_CSV_SQLITE_MAX_BYTES)

    if use_sqlite_snapshot:
        sqlite_cached = _load_csv_payload_from_sqlite(
            filepath=filepath,
            signature=file_sig,
            usecols=normalized_usecols,
        )
        if sqlite_cached is not None:
            _annotate_csv_cache_metadata(
                frame=sqlite_cached,
                filepath=filepath,
                signature=file_sig,
                usecols=normalized_usecols,
            )
            with FILE_CACHE_LOCK:
                _set_bounded_lru_cache_entry(
                    CSV_FILE_CACHE,
                    cache_key,
                    (file_sig, sqlite_cached),
                    max_entries=_CSV_FILE_CACHE_MAX_ENTRIES,
                )
            return sqlite_cached.copy(deep=deep_copy)

    df = _read_csv_with_usecols_fallback(
        filepath=filepath,
        usecols=normalized_usecols,
    )
    _annotate_csv_cache_metadata(
        frame=df,
        filepath=filepath,
        signature=file_sig,
        usecols=normalized_usecols,
    )
    with FILE_CACHE_LOCK:
        _set_bounded_lru_cache_entry(
            CSV_FILE_CACHE,
            cache_key,
            (file_sig, df),
            max_entries=_CSV_FILE_CACHE_MAX_ENTRIES,
        )
    if use_sqlite_snapshot:
        _save_csv_payload_to_sqlite(
            filepath=filepath,
            signature=file_sig,
            usecols=normalized_usecols,
            payload=df,
        )
    return df.copy(deep=deep_copy)


def count_total_scanned_stocks(data_dir: str) -> int:
    """스캔 대상 종목 수(korean_stocks_list.csv 라인 수-헤더)를 반환한다."""
    stocks_file = os.path.join(data_dir, "korean_stocks_list.csv")
    signature = file_signature(stocks_file)
    if signature is None:
        return 0

    with FILE_CACHE_LOCK:
        if SCANNED_STOCK_COUNT_CACHE.get("signature") == signature:
            return int(SCANNED_STOCK_COUNT_CACHE.get("value", 0))
    count = get_cached_file_row_count(
        path=stocks_file,
        signature=signature,
        logger=_LOGGER,
    )
    normalized_count = int(max(0, count or 0))

    with FILE_CACHE_LOCK:
        SCANNED_STOCK_COUNT_CACHE["signature"] = signature
        SCANNED_STOCK_COUNT_CACHE["value"] = normalized_count
    return normalized_count
