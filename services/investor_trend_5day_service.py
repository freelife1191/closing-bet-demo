#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Investor Trend 5-Day Service

외국인/기관 5거래일 합산 데이터를 단일 경로로 제공한다.
"""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any
import copy
import logging
import os
import threading
import time

from pandas.api.types import is_datetime64_any_dtype
import numpy as np
import pandas as pd

from engine.investor_personal_flow import personal_flow_details
from engine.ticker_utils import normalize_ticker
from engine.toss_collector_numeric_helpers import optional_volume
from services.kr_market_csv_utils import get_ticker_padded_series
from services.kr_market_data_cache_service import load_csv_file
from services.kr_market_data_cache_sqlite_payload import (
    load_json_payload_from_sqlite,
    save_json_payload_to_sqlite,
)

logger = logging.getLogger(__name__)

_TREND_FILENAME = "all_institutional_trend_data.csv"
_SQLITE_KEY_SUFFIX = "::investor_trend_5day_unified"
_SQLITE_MAX_ROWS = 256
_REFERENCE_SQLITE_MAX_ROWS = 20_000
_REFERENCE_SQLITE_NAMESPACE_DIR = ".investor_trend_reference_cache"
_PYKRX_MARKET_DATE_SQLITE_MAX_ROWS = 256
_MEMORY_CACHE_MAX_ENTRIES = 32
_REFERENCE_CACHE_MAX_ENTRIES = 4_096
_CSV_EXTREME_ABS_TOTAL = 20_000_000_000_000
# 영업일로 센다. 달력 날짜로 세면 주말만 끼어도 최신 자료가 낡은 것으로 판정된다.
_CSV_STALE_BUSINESS_DAYS = 4
# 하루 급등 판정에서 "의미 있는 규모"의 하한이다.
_SPIKE_SIGNIFICANT_TOTAL = 10_000_000_000
_TREND_CACHE_LOCK = threading.Lock()
_TREND_CACHE: OrderedDict[
    tuple[str, int, int, str],
    dict[str, dict[str, Any]],
] = OrderedDict()
_REFERENCE_CACHE_LOCK = threading.Lock()
_REFERENCE_CACHE: OrderedDict[
    tuple[str, str, str, str],
    dict[str, Any] | None,
] = OrderedDict()
_REFERENCE_FAILURE_TTL = 60.0
_REFERENCE_FAILURES: OrderedDict[tuple[str, str, str, str], float] = OrderedDict()
_REFERENCE_INFLIGHT: dict[tuple[int, tuple[str, str, str, str]], Future[dict[str, Any] | None]] = {}
_REFERENCE_GENERATION = 0
_TOSS_COLLECTOR_LOCK = threading.Lock()
_TOSS_COLLECTOR: Any | None = None
_PYKRX_MARKET_DATE_LOCK = threading.Lock()
_PYKRX_MARKET_DATE_CACHE: dict[str, datetime] = {}

def _normalize_data_dir(data_dir: str) -> str:
    normalized = (data_dir or "").strip()
    if not normalized:
        normalized = "data"
    return os.path.abspath(normalized)

def _normalize_target_datetime(target_datetime: datetime | pd.Timestamp | str | None) -> datetime | None:
    if target_datetime is None:
        return None
    try:
        parsed = pd.to_datetime(target_datetime, errors="coerce")
    except Exception:
        return None
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.to_pydatetime()

def _target_token(target_datetime: datetime | pd.Timestamp | str | None) -> str:
    normalized = _normalize_target_datetime(target_datetime)
    if normalized is None:
        return "latest"
    return normalized.strftime("%Y%m%d")

def _safe_int(value: Any) -> int:
    """수치로 바꿀 수 없는 값을 0 으로 눌러 준다.

    OverflowError 를 함께 잡는 이유는 무한대 때문이다. json.loads 는 Infinity 와
    1e400 을 inf 로 파싱하고 int(float("inf")) 는 ValueError 가 아니라 OverflowError
    를 던진다. 참조 자료가 비공식 API 에서 오므로 이 값이 들어올 수 있고, 그때
    신뢰 경계의 검증 장치가 스스로 터지면 그 종목의 조회가 통째로 예외가 된다.
    """
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0

def _extract_abs_total(payload: dict[str, Any] | None) -> int:
    if not isinstance(payload, dict):
        return 0
    foreign_value = _safe_int(payload.get("foreign", 0))
    inst_value = _safe_int(payload.get("institution", 0))
    return abs(foreign_value) + abs(inst_value)

def _parse_date_string(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if parsed is None or pd.isna(parsed):
        return None
    return parsed.to_pydatetime()

def _normalize_latest_date_from_details(details: list[dict[str, Any]]) -> str | None:
    if not details:
        return None
    first = details[0]
    if not isinstance(first, dict):
        return None
    for key in ("date", "localDate", "baseDate"):
        parsed = _parse_date_string(first.get(key))
        if parsed is not None:
            return parsed.strftime("%Y-%m-%d")
    return None

def _stable_token_to_int(token: str) -> int:
    normalized = str(token or "")
    if normalized.isdigit():
        try:
            return int(normalized)
        except Exception:
            pass
    acc = 17
    for ch in normalized:
        acc = (acc * 31 + ord(ch)) % 2_000_000_000
    return int(acc)

def _reference_time_token(target_datetime: datetime | pd.Timestamp | str | None) -> str:
    normalized_target = _normalize_target_datetime(target_datetime)
    if normalized_target is not None:
        return normalized_target.strftime("%Y%m%d")
    return datetime.now().strftime("%Y%m%d")

def _reference_cache_token(
    *,
    source: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    data_dir: str | None = None,
) -> str:
    normalized_target = _normalize_target_datetime(target_datetime)
    if normalized_target is not None:
        return normalized_target.strftime("%Y%m%d")

    normalized_source = str(source or "").lower().strip()
    if normalized_source == "pykrx":
        try:
            latest_market_dt = _resolve_pykrx_latest_market_date(data_dir=data_dir)
            return latest_market_dt.strftime("%Y%m%d")
        except Exception:
            pass
    return _reference_time_token(target_datetime)

def _pykrx_market_date_sqlite_context(
    *,
    data_dir: str,
    cache_token: str,
) -> tuple[str, tuple[int, int]]:
    normalized_dir = _normalize_data_dir(data_dir)
    namespace_dir = os.path.join(normalized_dir, _REFERENCE_SQLITE_NAMESPACE_DIR, "pykrx")
    cache_key = os.path.join(namespace_dir, f"latest_market_date__{cache_token}.snapshot")
    signature = (_stable_token_to_int(cache_token), _stable_token_to_int("pykrx_market_date"))
    return cache_key, signature

def _reference_sqlite_context(
    *,
    data_dir: str,
    source: str,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> tuple[str, tuple[int, int]]:
    normalized_dir = _normalize_data_dir(data_dir)
    token = _reference_cache_token(
        source=source,
        target_datetime=target_datetime,
        data_dir=normalized_dir,
    )
    namespace_dir = os.path.join(
        normalized_dir,
        _REFERENCE_SQLITE_NAMESPACE_DIR,
        str(source or "unknown").strip().lower(),
    )
    cache_key = os.path.join(
        namespace_dir,
        f"{str(ticker).zfill(6)}__{token}.snapshot",
    )
    signature = (_stable_token_to_int(token), _stable_token_to_int(source))
    return cache_key, signature

def _resolve_trend_file_context(
    *,
    data_dir: str,
    filename: str,
) -> tuple[str, tuple[int, int]] | None:
    filepath = os.path.abspath(os.path.join(data_dir, filename))
    try:
        stat = os.stat(filepath)
    except OSError:
        return None
    return filepath, (int(stat.st_mtime_ns), int(stat.st_size))

def _sqlite_cache_key(filepath: str, target_token: str) -> str:
    return f"{filepath}{_SQLITE_KEY_SUFFIX}::{target_token}"

def _serialize_trend_map(trend_map: dict[str, dict[str, Any]]) -> dict[str, object]:
    rows: dict[str, object] = {}
    for ticker, payload in trend_map.items():
        if not isinstance(payload, dict):
            continue
        details = payload.get("details")
        serialized_details: list[list[int]] = []
        if isinstance(details, list):
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                try:
                    foreign_value = int(float(detail.get("netForeignerBuyVolume", 0)))
                    inst_value = int(float(detail.get("netInstitutionBuyVolume", 0)))
                except (TypeError, ValueError):
                    continue
                serialized_details.append([foreign_value, inst_value])

        try:
            foreign_5d = int(float(payload.get("foreign", 0)))
            inst_5d = int(float(payload.get("institution", 0)))
        except (TypeError, ValueError):
            continue

        latest_date = payload.get("latest_date")
        latest_date_value = str(latest_date) if latest_date else ""
        rows[str(ticker).zfill(6)] = [foreign_5d, inst_5d, serialized_details, latest_date_value]
    return {"rows": rows}

def _deserialize_trend_map(payload: dict[str, object]) -> dict[str, dict[str, Any]] | None:
    """SQLite 스냅숏을 되살린다. 5거래일치 불변식을 지키지 못하면 ``None`` 을 돌려준다.

    ``_build_trend_map`` 은 ``details`` 가 다섯 건인 항목만 만드므로 되살린 쪽도 같은
    불변식을 지킨다. 네 건짜리 항목이 ``days: 5`` 를 달고 나가면 불필요한 참조 조회를
    부르고 연속 부호 스트릭이 하루를 잃는다.

    ``OverflowError`` 를 함께 잡는 이유는 이 페이로드가 ``json.loads`` 를 거쳐 오기
    때문이다. 저장소는 프로세스 밖에 있고 JSON 은 ``Infinity`` 를 표현하므로,
    ``int(float("inf"))`` 가 던지는 ``OverflowError`` 를 놓치면 손상을 버리려던 함수가
    스스로 터져 종목 상세 요청 하나가 통째로 실패한다.

    행 하나라도 되살릴 수 없으면 남은 행까지 버린다. 그 행만 건너뛰면 해당 종목은
    호출자에게 「CSV 에 종목이 없다」와 구분되지 않는데, 남은 캐시는 계속 채택되므로
    재빌드가 영영 일어나지 않는다. 그러면 그 종목만 CSV 경로를 잃고 요청마다 pykrx 나
    Toss 참조 조회를 타며, 그 참조까지 ``_reference_reject_reason`` 에 걸리면 수급이
    아예 없는 것으로 나간다. ``None`` 은 호출자 ``_get_or_build_trend_map`` 에게 캐시
    미스이므로 CSV 에서 다시 만들어진다.
    """
    rows_payload = payload.get("rows")
    if not isinstance(rows_payload, dict):
        return None

    trend_map: dict[str, dict[str, Any]] = {}
    for ticker, row_payload in rows_payload.items():
        if not isinstance(row_payload, (list, tuple)) or len(row_payload) < 2:
            logger.warning("Discarding trend snapshot: malformed row for %s", ticker)
            return None

        try:
            foreign_5d = int(float(row_payload[0]))
            inst_5d = int(float(row_payload[1]))
        except (TypeError, ValueError, OverflowError):
            logger.warning("Discarding trend snapshot: non-numeric total for %s", ticker)
            return None

        details_payload = row_payload[2] if len(row_payload) >= 3 else []
        if not isinstance(details_payload, list):
            logger.warning("Discarding trend snapshot: malformed details for %s", ticker)
            return None

        details: list[dict[str, int]] = []
        for item in details_payload:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                logger.warning("Discarding trend snapshot: malformed detail for %s", ticker)
                return None
            try:
                foreign_value = int(float(item[0]))
                inst_value = int(float(item[1]))
            except (TypeError, ValueError, OverflowError):
                logger.warning("Discarding trend snapshot: non-numeric detail for %s", ticker)
                return None
            details.append(
                {
                    "netForeignerBuyVolume": foreign_value,
                    "netInstitutionBuyVolume": inst_value,
                }
            )

        if len(details) != 5:
            logger.warning(
                "Discarding trend snapshot: %s has %d days, expected 5", ticker, len(details)
            )
            return None

        latest_date_value = ""
        if len(row_payload) >= 4 and isinstance(row_payload[3], str):
            latest_date_value = row_payload[3]

        ticker_key = str(ticker).zfill(6)
        trend_map[ticker_key] = {
            "foreign": foreign_5d,
            "institution": inst_5d,
            "details": details,
            "days": 5,
            "latest_date": latest_date_value,
        }
    return trend_map

def _load_trend_df(
    *,
    data_dir: str,
    filename: str,
    signature: tuple[int, int],
) -> pd.DataFrame:
    usecols = ["ticker", "date", "foreign_buy", "inst_buy"]
    try:
        return load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=usecols,
            signature=signature,
        )
    except ValueError:
        loaded = load_csv_file(
            data_dir,
            filename,
            deep_copy=False,
            usecols=None,
            signature=signature,
        )
        existing_columns = [column for column in usecols if column in loaded.columns]
        if existing_columns:
            return loaded.loc[:, existing_columns]
        return loaded

def _build_trend_map(
    trend_df: pd.DataFrame,
    *,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, dict[str, Any]]:
    if trend_df.empty:
        return {}
    required_columns = {"ticker", "foreign_buy", "inst_buy"}
    if not required_columns.issubset(set(trend_df.columns)):
        return {}

    working = trend_df
    ticker_series = get_ticker_padded_series(working)
    try:
        working["ticker"] = ticker_series
    except Exception:
        working = working.copy()
        working["ticker"] = ticker_series

    working["foreign_buy"] = pd.to_numeric(working["foreign_buy"], errors="coerce").fillna(0)
    working["inst_buy"] = pd.to_numeric(working["inst_buy"], errors="coerce").fillna(0)

    normalized_target_datetime = _normalize_target_datetime(target_datetime)
    has_date = "date" in working.columns
    if has_date:
        if not is_datetime64_any_dtype(working["date"]):
            working["date"] = pd.to_datetime(working["date"], errors="coerce")
        working = working[working["date"].notna()]
        if normalized_target_datetime is not None:
            working = working[working["date"] <= normalized_target_datetime]
        if working.empty:
            return {}
        working = working.sort_values(["ticker", "date"])
    elif normalized_target_datetime is not None:
        return {}
    else:
        working = working.sort_values(["ticker"])

    trend_map: dict[str, dict[str, Any]] = {}
    grouped = working.groupby("ticker", sort=False)
    for ticker, group in grouped:
        recent = group.tail(5)
        if len(recent) < 5:
            continue

        ordered = recent.sort_values("date", ascending=False) if has_date else recent.iloc[::-1]
        details: list[dict[str, int]] = []
        foreign_5d = 0
        inst_5d = 0
        for foreign_value, inst_value in ordered[["foreign_buy", "inst_buy"]].itertuples(index=False, name=None):
            try:
                foreign_int = int(float(foreign_value))
                inst_int = int(float(inst_value))
            except (TypeError, ValueError):
                continue

            foreign_5d += foreign_int
            inst_5d += inst_int
            details.append(
                {
                    "netForeignerBuyVolume": foreign_int,
                    "netInstitutionBuyVolume": inst_int,
                }
            )

        if len(details) < 5:
            continue

        latest_date_value = ""
        if has_date:
            try:
                latest_date_value = ordered["date"].iloc[0].strftime("%Y-%m-%d")
            except Exception:
                latest_date_value = ""

        ticker_key = str(ticker).zfill(6)
        trend_map[ticker_key] = {
            "foreign": int(foreign_5d),
            "institution": int(inst_5d),
            "details": details,
            "days": 5,
            "latest_date": latest_date_value,
        }

    return trend_map

def _normalize_external_trend_payload(
    payload: dict[str, Any] | None,
    *,
    source: str,
    from_cache: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    # [INFRA-109] 5일 합계가 결측이면 그 참조 전체가 결측이다. 0 으로 채우면 순매수 0 으로 판정된다
    try:
        foreign_value = int(float(payload.get("foreign")))
        inst_value = int(float(payload.get("institution")))
    except (TypeError, ValueError, OverflowError):
        return None

    details_payload = payload.get("details")
    details: list[dict[str, Any]] = []
    if isinstance(details_payload, list):
        for item in details_payload[:5]:
            if not isinstance(item, dict):
                continue
            foreign_1d, inst_1d = (
                None if v is None else int(v)
                for v in (
                    optional_volume(item.get("netForeignerBuyVolume")),
                    optional_volume(item.get("netInstitutionBuyVolume")),
                )
            )
            day = next((_parse_date_string(item.get(key)) for key in ("date", "localDate", "baseDate", "tradeDate") if item.get(key)), None)
            detail: dict[str, Any] = {"netForeignerBuyVolume": foreign_1d, "netInstitutionBuyVolume": inst_1d}
            if day is not None:
                detail["date"] = day.strftime("%Y-%m-%d")
            details.append(detail)

    if not details and (foreign_value != 0 or inst_value != 0):
        # details가 없더라도 5일합 자체는 유지한다.
        details = []

    latest_date = payload.get("latest_date")
    if not latest_date:
        latest_date = _normalize_latest_date_from_details(payload.get("details", []))

    personal_rows = payload.get("individual_details", details_payload)
    personal = personal_flow_details(personal_rows) if isinstance(personal_rows, list) else []
    if from_cache and payload.get("individual_schema") != 1:
        personal = []
    if source == "csv":
        personal = []
    selected_dates = {item.get("date") for item in details}
    if personal and (len(selected_dates) != 5 or None in selected_dates or selected_dates != {item["date"] for item in personal}):
        personal = []
    if personal and latest_date and max(item["date"] for item in personal) != str(latest_date)[:10]:
        personal = []
    return {
        "individual": sum(item["netIndividualsBuyVolume"] for item in personal) if personal else None,
        "individual_schema": 1 if personal else 0,
        "individual_details": personal,
        "foreign": foreign_value,
        "institution": inst_value,
        "details": details,
        "days": 5,
        "latest_date": str(latest_date) if latest_date else "",
        "source": source,
    }

def _reference_reject_reason(payload: dict[str, Any] | None) -> str | None:
    """참조 페이로드를 쓸 수 없는 사유를 돌려준다. 쓸 만하면 None 이다.

    zero_total 은 하루별 절대값의 총합으로 판정한다. 5일 합계만 0 인 것은 매수와
    매도가 상쇄된 정상 자료라서, 합계로 판정하면 멀쩡한 참조를 버린다.
    """
    if not isinstance(payload, dict):
        return "not_a_dict"

    details = payload.get("details")
    if not isinstance(details, list) or len(details) < 5:
        return "insufficient_days"

    day_abs_total = 0
    for detail in details[:5]:
        if not isinstance(detail, dict):
            return "insufficient_days"
        day_abs_total += abs(_safe_int(detail.get("netForeignerBuyVolume", 0)))
        day_abs_total += abs(_safe_int(detail.get("netInstitutionBuyVolume", 0)))

    if day_abs_total == 0:
        return "zero_total"

    if _extract_abs_total(payload) >= _CSV_EXTREME_ABS_TOTAL:
        return "extreme_abs_total"

    return None

def _detect_csv_anomaly_flags(
    csv_payload: dict[str, Any] | None,
    *,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> list[str]:
    if not isinstance(csv_payload, dict):
        return ["missing_csv"]

    flags: list[str] = []
    details = csv_payload.get("details")
    if not isinstance(details, list) or len(details) < 5:
        flags.append("insufficient_days")
    else:
        day_abs_totals: list[int] = []
        for detail in details[:5]:
            if not isinstance(detail, dict):
                continue
            day_abs_totals.append(
                abs(_safe_int(detail.get("netForeignerBuyVolume", 0)))
                + abs(_safe_int(detail.get("netInstitutionBuyVolume", 0)))
            )
        if len(day_abs_totals) >= 5:
            peak = max(day_abs_totals)
            baseline_values = sorted(day_abs_totals)[:-1]
            baseline = int(sum(baseline_values) / max(1, len(baseline_values)))
            if peak >= _SPIKE_SIGNIFICANT_TOTAL and peak >= max(1, baseline) * 10:
                flags.append("single_day_spike")

    abs_total = _extract_abs_total(csv_payload)
    if abs_total >= _CSV_EXTREME_ABS_TOTAL:
        flags.append("extreme_abs_total")

    if target_datetime is None:
        latest_date = _parse_date_string(csv_payload.get("latest_date"))
        if latest_date is not None:
            # 주말과 휴장일을 세지 않는다. 달력 날짜로 세면 금요일 자료가 그 주
            # 수요일에 이미 낡은 것으로 판정되고, 설·추석 연휴에는 온 시장이 한꺼번에
            # 교체 대상이 되면서 종목마다 참조 조회가 붙는다. 휴장일 목록은 해마다
            # 손으로 채우는 것이라 비어 있는 해에는 주말까지만 걸러진다.
            # engine 패키지가 초기화될 때 이 모듈을 도로 임포트하므로 함수 안에서
            # 가져온다. 같은 파일의 _get_toss_collector 도 같은 이유로 그렇게 한다.
            from engine.market_schedule import MarketSchedule

            business_gap = int(
                np.busday_count(
                    latest_date.date(),
                    datetime.now().date(),
                    holidays=MarketSchedule.known_holidays(),
                )
            )
            if business_gap > _CSV_STALE_BUSINESS_DAYS:
                flags.append("stale_csv")

    return flags

def _resolve_pykrx_latest_market_date(
    *,
    data_dir: str | None = None,
) -> datetime:
    normalized_data_dir = _normalize_data_dir(data_dir or "data")
    cache_token = datetime.now().strftime("%Y%m%d")
    with _PYKRX_MARKET_DATE_LOCK:
        cached_token = _PYKRX_MARKET_DATE_CACHE.get("token")
        cached_value = _PYKRX_MARKET_DATE_CACHE.get("value")
        if cached_token == cache_token and isinstance(cached_value, datetime):
            return cached_value

    sqlite_key, sqlite_signature = _pykrx_market_date_sqlite_context(
        data_dir=normalized_data_dir,
        cache_token=cache_token,
    )
    try:
        loaded, payload = load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load pykrx latest market date sqlite cache: %s", error)
    else:
        if loaded and isinstance(payload, dict):
            parsed_latest = _parse_date_string(payload.get("latest_market_date"))
            if parsed_latest is not None:
                with _PYKRX_MARKET_DATE_LOCK:
                    _PYKRX_MARKET_DATE_CACHE["token"] = cache_token
                    _PYKRX_MARKET_DATE_CACHE["value"] = parsed_latest
                return parsed_latest

    now = datetime.now()
    fallback = now
    if now.weekday() == 5:
        fallback = now - timedelta(days=1)
    elif now.weekday() == 6:
        fallback = now - timedelta(days=2)

    latest_market_dt = fallback
    try:
        from pykrx import stock

        start_date = (now - timedelta(days=14)).strftime("%Y%m%d")
        end_date = now.strftime("%Y%m%d")
        market_df = stock.get_index_ohlcv_by_date(start_date, end_date, "1001")
        if isinstance(market_df, pd.DataFrame) and not market_df.empty:
            latest_market_dt = market_df.index[-1].to_pydatetime()
    except Exception as error:
        logger.debug("Failed to resolve pykrx latest market date: %s", error)

    with _PYKRX_MARKET_DATE_LOCK:
        _PYKRX_MARKET_DATE_CACHE["token"] = cache_token
        _PYKRX_MARKET_DATE_CACHE["value"] = latest_market_dt

    try:
        save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=sqlite_signature,
            payload={"latest_market_date": latest_market_dt.strftime("%Y-%m-%d")},
            max_rows=_PYKRX_MARKET_DATE_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save pykrx latest market date sqlite cache: %s", error)
    return latest_market_dt

def _fetch_pykrx_reference_trend(
    *,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    data_dir: str | None = None,
) -> dict[str, Any] | None:
    try:
        from pykrx import stock
    except Exception:
        return None

    normalized_target = _normalize_target_datetime(target_datetime)
    end_dt = normalized_target or _resolve_pykrx_latest_market_date(data_dir=data_dir)
    start_dt = end_dt - timedelta(days=14)

    try:
        trend_df = stock.get_market_trading_value_by_date(
            start_dt.strftime("%Y%m%d"),
            end_dt.strftime("%Y%m%d"),
            str(ticker).zfill(6),
        )
    except Exception as error:
        logger.debug("pykrx reference trend fetch failed (%s): %s", ticker, error)
        return None

    if not isinstance(trend_df, pd.DataFrame) or trend_df.empty:
        return None

    trend_df = trend_df.tail(5)
    if len(trend_df) < 5:
        return None

    foreign_col = next((col for col in trend_df.columns if "외국인" in col), None)
    inst_col = next((col for col in trend_df.columns if "기관" in col), None)
    if not foreign_col or not inst_col:
        return None

    ordered = trend_df.iloc[::-1]
    details: list[dict[str, int]] = []
    foreign_sum = 0
    inst_sum = 0
    for day, (foreign_value, inst_value) in zip(ordered.index, ordered[[foreign_col, inst_col]].itertuples(index=False, name=None)):
        foreign_int = _safe_int(foreign_value)
        inst_int = _safe_int(inst_value)
        foreign_sum += foreign_int
        inst_sum += inst_int
        details.append(
            {
                "date": str(day)[:10],
                "netForeignerBuyVolume": foreign_int,
                "netInstitutionBuyVolume": inst_int,
            }
        )

    latest_date = ""
    try:
        latest_date = ordered.index[0].strftime("%Y-%m-%d")
    except Exception:
        latest_date = ""

    personal_col = next((col for col in ordered.columns if col in ("개인", "개인합계")), None)
    personal_rows = [{"date": str(day)[:10], "netIndividualsBuyVolume": row[personal_col]}
                     for day, row in ordered.iterrows()] if personal_col else []
    return {
        "individual_details": personal_rows,
        "foreign": int(foreign_sum),
        "institution": int(inst_sum),
        "details": details,
        "days": 5,
        "latest_date": latest_date,
        "source": "pykrx",
    }

def _get_toss_collector() -> Any | None:
    global _TOSS_COLLECTOR
    if _TOSS_COLLECTOR is not None:
        return _TOSS_COLLECTOR

    with _TOSS_COLLECTOR_LOCK:
        if _TOSS_COLLECTOR is not None:
            return _TOSS_COLLECTOR
        try:
            from engine.toss_collector import TossCollector

            _TOSS_COLLECTOR = TossCollector()
        except Exception as error:
            logger.debug("Failed to initialize TossCollector for reference check: %s", error)
            _TOSS_COLLECTOR = None
    return _TOSS_COLLECTOR

def _fetch_toss_reference_trend(
    *,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> dict[str, Any] | None:
    # Toss는 과거 기준일 조회가 불가능하므로 최신 조회에서만 사용한다.
    if _normalize_target_datetime(target_datetime) is not None:
        return None

    collector = _get_toss_collector()
    if collector is None:
        return None

    try:
        trend_payload = collector.get_investor_trend(str(ticker).zfill(6), days=5)
    except Exception as error:
        logger.debug("Toss reference trend fetch failed (%s): %s", ticker, error)
        return None
    return _normalize_external_trend_payload(trend_payload, source="toss")

def _get_reference_trend_cached(
    *, data_dir: str, source: str, ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> dict[str, Any] | None:
    source = str(source).strip().lower()
    ticker_key = normalize_ticker(ticker)
    if not ticker_key or source not in {"pykrx", "toss"}:
        return None
    if source == "toss" and _normalize_target_datetime(target_datetime) is not None:
        return None
    directory = _normalize_data_dir(data_dir)
    target_key = _reference_cache_token(source=source, target_datetime=target_datetime, data_dir=directory)
    cache_key = (directory, source, ticker_key, target_key)
    with _REFERENCE_CACHE_LOCK:
        if cache_key in _REFERENCE_CACHE:
            _REFERENCE_CACHE.move_to_end(cache_key)
            return copy.deepcopy(_REFERENCE_CACHE[cache_key])
        if _REFERENCE_FAILURES.get(cache_key, 0) > time.monotonic():
            _REFERENCE_FAILURES.move_to_end(cache_key)
            return None
        _REFERENCE_FAILURES.pop(cache_key, None)
        generation = _REFERENCE_GENERATION
        flight_key = (generation, cache_key)
        future = _REFERENCE_INFLIGHT.get(flight_key)
        owner = future is None
        if owner:
            future = Future()
            _REFERENCE_INFLIGHT[flight_key] = future
    if not owner:
        return copy.deepcopy(future.result())

    result = None
    fatal = None
    fetched = False
    try:
        sqlite_key, signature = _reference_sqlite_context(
            data_dir=directory, source=source, ticker=ticker_key, target_datetime=target_datetime,
        )
        try:
            loaded, payload = load_json_payload_from_sqlite(filepath=sqlite_key, signature=signature, logger=logger)
        except Exception as error:
            logger.debug("Failed to load reference cache: %s", error)
            loaded, payload = False, None
        if loaded and isinstance(payload, dict):
            result = _normalize_external_trend_payload(payload, source=source, from_cache=True)
        if result is None:
            fetched = True
            if source == "pykrx":
                payload = _fetch_pykrx_reference_trend(ticker=ticker_key, target_datetime=target_datetime, data_dir=directory)
            else:
                payload = _fetch_toss_reference_trend(ticker=ticker_key, target_datetime=target_datetime)
            result = _normalize_external_trend_payload(payload, source=source) if payload else None
    except BaseException as error:
        logger.debug("Reference lookup failed (%s/%s): %s", source, ticker_key, error)
        if not isinstance(error, Exception):
            fatal = error
    finally:
        # A clear separates generations. Publish and clear are serialized, including SQLite.
        with _REFERENCE_CACHE_LOCK:
            if generation == _REFERENCE_GENERATION:
                if result is not None:
                    _REFERENCE_CACHE[cache_key] = copy.deepcopy(result)
                    _REFERENCE_CACHE.move_to_end(cache_key)
                    while len(_REFERENCE_CACHE) > _REFERENCE_CACHE_MAX_ENTRIES:
                        _REFERENCE_CACHE.popitem(last=False)
                    if fetched:
                        try:
                            save_json_payload_to_sqlite(filepath=sqlite_key, signature=signature, payload=result,
                                                       max_rows=_REFERENCE_SQLITE_MAX_ROWS, logger=logger)
                        except Exception as error:
                            logger.debug("Failed to save reference cache: %s", error)
                elif fatal is None:
                    _REFERENCE_FAILURES[cache_key] = time.monotonic() + _REFERENCE_FAILURE_TTL
                    _REFERENCE_FAILURES.move_to_end(cache_key)
                    while len(_REFERENCE_FAILURES) > _REFERENCE_CACHE_MAX_ENTRIES:
                        _REFERENCE_FAILURES.popitem(last=False)
            _REFERENCE_INFLIGHT.pop(flight_key, None)
        # Callbacks/waiters may re-enter; settle outside the lock.
        if fatal is not None:
            future.set_exception(fatal)
        else:
            future.set_result(result)
    if fatal is not None:
        raise fatal
    return copy.deepcopy(result)

def _attach_selection_metadata(
    payload: dict[str, Any],
    *,
    selected_source: str,
    csv_flags: list[str],
    reference_sources: list[str],
    discarded_references: list[str] | None = None,
    reference_only: bool = False,
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["source"] = selected_source
    enriched["quality"] = {
        "csv_anomaly_flags": list(csv_flags),
        "reference_sources": list(reference_sources),
        "discarded_references": list(discarded_references or []),
        "reference_only": bool(reference_only),
    }
    return enriched

def _resolve_best_payload(
    *,
    data_dir: str,
    csv_payload: dict[str, Any] | None,
    ticker: str,
    target_datetime: datetime | pd.Timestamp | str | None,
    verify_with_references: bool,
) -> dict[str, Any] | None:
    csv_flags = _detect_csv_anomaly_flags(csv_payload, target_datetime=target_datetime)
    normalized_csv = _normalize_external_trend_payload(csv_payload, source="csv") if csv_payload else None
    is_latest_reference_window = _normalize_target_datetime(target_datetime) is None
    if normalized_csv is None:
        csv_flags = sorted(set(csv_flags + ["missing_csv"]))

    references: list[dict[str, Any]] = []
    discarded_references: list[str] = []

    def _accept_reference(candidate: dict[str, Any] | None, *, source: str) -> bool:
        """쓸 만한 참조면 references 에 넣는다. 판정을 두 조회 자리에 복제하지 않으려고 둔다."""
        if not candidate:
            return False
        reason = _reference_reject_reason(candidate)
        if reason is not None:
            discarded_references.append(f"{source}:{reason}")
            logger.debug("Discarded %s reference trend for %s: %s", source, ticker, reason)
            return False
        references.append(candidate)
        return True

    if verify_with_references and csv_flags:
        pykrx_ref = _get_reference_trend_cached(
            data_dir=data_dir,
            source="pykrx",
            ticker=ticker,
            target_datetime=target_datetime,
        )
        accepted_pykrx = _accept_reference(pykrx_ref, source="pykrx")

        # 기본 우선순위가 pykrx이므로 쓸 만한 pykrx 참조가 있으면 Toss 조회를 생략해
        # 지연을 줄인다. pykrx 를 걸러 냈다면 Toss 를 조회한다. 걸러 낸 참조는 없는
        # 것과 같으므로 대체 자료를 찾아야 한다.
        if not accepted_pykrx and is_latest_reference_window:
            toss_ref = _get_reference_trend_cached(
                data_dir=data_dir,
                source="toss",
                ticker=ticker,
                target_datetime=target_datetime,
            )
            _accept_reference(toss_ref, source="toss")

    reference_sources = [str(item.get("source", "")) for item in references if isinstance(item, dict)]

    if normalized_csv is None:
        if references:
            # 기본 우선순위: pykrx > toss
            selected = next((item for item in references if item.get("source") == "pykrx"), references[0])
            return _attach_selection_metadata(
                selected,
                selected_source=str(selected.get("source", "reference")),
                csv_flags=csv_flags,
                reference_sources=reference_sources,
                discarded_references=discarded_references,
                reference_only=True,
            )
        return None

    if not references:
        return _attach_selection_metadata(
            normalized_csv,
            selected_source="csv",
            csv_flags=csv_flags,
            reference_sources=[],
            discarded_references=discarded_references,
        )

    # 여기까지 왔다면 CSV 에 이상징후가 있고(그 조건에서만 참조를 조회한다) 참조를 받아
    # 왔다. 그러면 참조를 쓴다. 두 값을 견주어 고르지 않는 이유는 같은 기간을 잰다는
    # 보장이 없기 때문이다. stale_csv 는 정의상 CSV 가 다른 5거래일을 본다는 뜻이고
    # insufficient_days 는 CSV 가 불완전하다는 뜻이라, 5일 합계가 비슷해도 하루별 값이
    # 같다고 볼 수 없다. engine/screener_scoring_helpers.py 의 _score_supply_core 는
    # details[0] 와 연속 부호로 25점까지 매긴다.
    selected = next((item for item in references if item.get("source") == "pykrx"), references[0])
    return _attach_selection_metadata(
        selected,
        selected_source=str(selected.get("source", "reference")),
        csv_flags=csv_flags,
        reference_sources=reference_sources,
        discarded_references=discarded_references,
    )

def _get_or_build_trend_map(
    *,
    data_dir: str,
    filename: str,
    target_datetime: datetime | pd.Timestamp | str | None = None,
) -> dict[str, dict[str, Any]]:
    context = _resolve_trend_file_context(data_dir=data_dir, filename=filename)
    if context is None:
        return {}

    filepath, signature = context
    target_key = _target_token(target_datetime)
    memory_cache_key = (filepath, int(signature[0]), int(signature[1]), target_key)

    with _TREND_CACHE_LOCK:
        cached = _TREND_CACHE.get(memory_cache_key)
        if isinstance(cached, dict):
            _TREND_CACHE.move_to_end(memory_cache_key)
            return cached

    sqlite_key = _sqlite_cache_key(filepath, target_key)
    try:
        loaded, payload = load_json_payload_from_sqlite(
            filepath=sqlite_key,
            signature=signature,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to load investor trend 5day sqlite cache: %s", error)
    else:
        if loaded and isinstance(payload, dict):
            cached_map = _deserialize_trend_map(payload)
            if cached_map is not None:
                with _TREND_CACHE_LOCK:
                    _TREND_CACHE[memory_cache_key] = cached_map
                    _TREND_CACHE.move_to_end(memory_cache_key)
                    while len(_TREND_CACHE) > _MEMORY_CACHE_MAX_ENTRIES:
                        _TREND_CACHE.popitem(last=False)
                return cached_map

    trend_df = _load_trend_df(
        data_dir=data_dir,
        filename=filename,
        signature=signature,
    )
    trend_map = _build_trend_map(trend_df, target_datetime=target_datetime)
    with _TREND_CACHE_LOCK:
        _TREND_CACHE[memory_cache_key] = trend_map
        _TREND_CACHE.move_to_end(memory_cache_key)
        while len(_TREND_CACHE) > _MEMORY_CACHE_MAX_ENTRIES:
            _TREND_CACHE.popitem(last=False)

    try:
        save_json_payload_to_sqlite(
            filepath=sqlite_key,
            signature=signature,
            payload=_serialize_trend_map(trend_map),
            max_rows=_SQLITE_MAX_ROWS,
            logger=logger,
        )
    except Exception as error:
        logger.debug("Failed to save investor trend 5day sqlite cache: %s", error)

    return trend_map

def has_csv_anomaly_flags(trend_data: dict[str, Any] | None) -> bool:
    """반환된 페이로드에 CSV 이상징후 플래그가 붙어 있는지 판정한다.

    수급 조회 결과를 받아 자기 경로로 빠질지 결정하는 호출자를 위한 것이다.
    None 은 False 다. CSV 에 종목이 없다는 뜻이지 이상징후가 있다는 뜻이 아니다.
    """
    if not isinstance(trend_data, dict):
        return False
    quality = trend_data.get("quality")
    if not isinstance(quality, dict):
        return False
    csv_flags = quality.get("csv_anomaly_flags")
    return isinstance(csv_flags, list) and len(csv_flags) > 0

def get_investor_trend_5day_for_ticker(
    *,
    ticker: str,
    data_dir: str,
    filename: str = _TREND_FILENAME,
    target_datetime: datetime | pd.Timestamp | str | None = None,
    verify_with_references: bool = True,
) -> dict[str, Any] | None:
    """
    단일 ticker의 5거래일 수급 합산 데이터를 반환한다.

    verify_with_references=True 는 그 자체가 「이상징후일 때만 참조를 조회한다」는
    정책이다. 플래그가 붙지 않으면 조회하지 않으므로, False 로 먼저 부르고 플래그를
    확인한 뒤 True 로 다시 부르는 것은 첫 반환값을 버리는 중복 호출이다.

    참조를 받아 왔다면 그것을 쓴다. 이상징후가 붙은 CSV 와 값을 견주어 고르지 않는다.
    stale_csv 는 CSV 가 참조와 다른 5거래일을 본다는 뜻이고 insufficient_days 는 CSV 가
    불완전하다는 뜻이라, 두 자료의 합계가 비슷하더라도 하루별 값까지 같다고 볼 근거가
    없기 때문이다.

    다만 참조를 쓰기 전에 _reference_reject_reason 으로 쓸 만한 값인지 먼저 본다.
    퇴화한 참조(전 항목이 0, 5일치가 모이지 않음, 20조 상한 초과)는 채택하지 않으므로
    그 경우 정확한 CSV 가 살아남는다. 버린 참조는 quality.discarded_references 에
    "<출처>:<사유>" 형식으로 남는다.

    quality.reference_only 는 CSV 대응값이 없어 참조 단독으로 채운 값이라는 표식이다.
    이 표식에 점수 감점이나 상한을 두지 않는다. 기본 참조인 pykrx 는 KRX 공식 자료라
    표식이 붙었다는 사실만으로 값이 덜 정확하다고 볼 근거가 없고, 감점을 넣으려면
    등급으로 바로 이어지는 engine/screener_scoring_helpers.py 의 계수를 관측 자료
    없이 정해야 하기 때문이다. 이 표식이 실제로 얼마나 붙는지 관측한 뒤에 정한다.
    """
    normalized_data_dir = _normalize_data_dir(data_dir)
    trend_map = _get_or_build_trend_map(
        data_dir=normalized_data_dir,
        filename=filename,
        target_datetime=target_datetime,
    )
    ticker_key = str(ticker).zfill(6)
    result = trend_map.get(ticker_key)
    normalized_result = result if isinstance(result, dict) else None
    return _resolve_best_payload(
        data_dir=normalized_data_dir,
        csv_payload=normalized_result,
        ticker=ticker_key,
        target_datetime=target_datetime,
        verify_with_references=verify_with_references,
    )

def get_investor_trends_5day_for_tickers(
    *, tickers: list[str], data_dir: str,
    target_datetime: datetime | pd.Timestamp | str | None,
) -> dict[str, dict[str, Any] | None]:
    """최대 네 후보의 참조만 병렬 조회한다. CSV 준비는 호출 스레드에서 한다."""
    if len(tickers) > 4:
        raise ValueError("At most four candidates are allowed")
    keys = list(dict.fromkeys(filter(None, (normalize_ticker(ticker) for ticker in tickers))))
    if not keys:
        return {}
    directory = _normalize_data_dir(data_dir)
    trend_map = _get_or_build_trend_map(data_dir=directory, filename=_TREND_FILENAME, target_datetime=target_datetime)
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="supply-reference") as pool:
        futures = {key: pool.submit(_resolve_best_payload, data_dir=directory, csv_payload=trend_map.get(key),
                                   ticker=key, target_datetime=target_datetime, verify_with_references=True)
                   for key in keys}
        return {key: future.result() for key, future in futures.items()}

def clear_investor_trend_5day_memory_cache() -> None:
    """테스트/디버깅용: in-memory 캐시를 비운다."""
    with _TREND_CACHE_LOCK:
        _TREND_CACHE.clear()
    global _REFERENCE_GENERATION
    with _REFERENCE_CACHE_LOCK:
        _REFERENCE_GENERATION += 1
        _REFERENCE_CACHE.clear()
        _REFERENCE_FAILURES.clear()
        _REFERENCE_INFLIGHT.clear()
    with _PYKRX_MARKET_DATE_LOCK:
        _PYKRX_MARKET_DATE_CACHE.clear()

__all__ = [
    "get_investor_trend_5day_for_ticker",
    "get_investor_trends_5day_for_tickers",
    "has_csv_anomaly_flags",
    "clear_investor_trend_5day_memory_cache",
]
