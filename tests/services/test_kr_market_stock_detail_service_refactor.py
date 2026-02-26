#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Stock Detail Service 리팩토링 테스트
"""

from __future__ import annotations

import sqlite3
import sys
import types

import pandas as pd

from services.kr_market_stock_detail_service import (
    _get_padded_ticker_series,
    _get_or_build_investor_trend_5day_map,
    append_investor_trend_5day,
    fetch_stock_detail_payload,
    load_naver_stock_detail_payload,
)


def test_get_padded_ticker_series_creates_cache_column_once():
    df = pd.DataFrame({"ticker": [5930, 660]})

    first = _get_padded_ticker_series(df)
    second = _get_padded_ticker_series(df)

    assert first.tolist() == ["005930", "000660"]
    assert second.tolist() == ["005930", "000660"]
    assert "_ticker_padded" in df.columns


def test_append_investor_trend_5day_aggregates_recent_five_rows():
    trend_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-25", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-26", "foreign_buy": 1, "inst_buy": 10},
            # 과거 데이터가 파일 뒤쪽에 있어도 날짜 정렬 후 최근 5일만 집계되어야 한다.
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 100, "inst_buy": 1000},
        ]
    )
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=lambda _filename: trend_df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert payload["investorTrend5Day"] == {"foreign": 5, "institution": 50}


def test_append_investor_trend_5day_prefers_unified_service_when_data_dir_provided(monkeypatch, tmp_path):
    payload: dict[str, object] = {}
    calls = {"csv": 0}
    captured_calls: list[dict[str, object]] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured_calls.append(dict(kwargs)) or {"foreign": 321, "institution": 654},
    )

    def _should_not_read_csv(_filename: str) -> pd.DataFrame:
        calls["csv"] += 1
        raise AssertionError("CSV fallback should not be called")

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=_should_not_read_csv,
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=str(tmp_path),
    )

    assert payload["investorTrend5Day"] == {"foreign": 321, "institution": 654}
    assert calls["csv"] == 0
    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is False


def test_append_investor_trend_5day_retries_reference_verify_only_on_anomaly(monkeypatch, tmp_path):
    payload: dict[str, object] = {}
    calls = {"csv": 0}
    captured_calls: list[dict[str, object]] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    def _fake_get_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        if kwargs.get("verify_with_references") is False:
            return {
                "foreign": 111,
                "institution": 222,
                "quality": {"csv_anomaly_flags": ["stale_csv"]},
            }
        return {"foreign": 333, "institution": 444}

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        _fake_get_trend,
    )

    def _should_not_read_csv(_filename: str) -> pd.DataFrame:
        calls["csv"] += 1
        raise AssertionError("CSV fallback should not be called")

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=_should_not_read_csv,
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=str(tmp_path),
    )

    assert payload["investorTrend5Day"] == {"foreign": 333, "institution": 444}
    assert calls["csv"] == 0
    assert len(captured_calls) == 2
    assert captured_calls[0]["verify_with_references"] is False
    assert captured_calls[1]["verify_with_references"] is True


def test_append_investor_trend_5day_falls_back_to_csv_when_unified_service_has_no_data(monkeypatch):
    trend_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-25", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-26", "foreign_buy": 1, "inst_buy": 10},
        ]
    )
    payload: dict[str, object] = {}

    import services.kr_market_stock_detail_service as stock_detail_service

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: None,
    )

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=lambda _filename: trend_df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir="/tmp/unknown",
    )

    assert payload["investorTrend5Day"] == {"foreign": 5, "institution": 50}


def test_append_investor_trend_5day_skips_when_required_columns_missing():
    trend_df = pd.DataFrame([{"ticker": "005930"}])
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        load_csv_file=lambda _filename: trend_df,
        logger=type("L", (), {"warning": lambda *_a, **_k: None})(),
    )

    assert "investorTrend5Day" not in payload


def test_investor_trend_5day_map_cache_reuses_sqlite_metadata_across_shallow_copies(monkeypatch, tmp_path):
    import services.kr_market_stock_detail_service as stock_detail_service

    trend_csv = tmp_path / "all_institutional_trend_data.csv"
    trend_csv.write_text("ticker,date,foreign_buy,inst_buy\n", encoding="utf-8")

    trend_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 2},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 3, "inst_buy": 4},
        ]
    )
    trend_df.attrs["kr_cache_filepath"] = str(trend_csv)
    trend_df.attrs["kr_cache_signature"] = (123456789, 98765)
    trend_df.attrs["kr_cache_usecols"] = ("ticker", "date", "foreign_buy", "inst_buy")

    with stock_detail_service._INVESTOR_TREND_5DAY_CACHE_LOCK:
        stock_detail_service._INVESTOR_TREND_5DAY_CACHE.clear()

    call_count = {"value": 0}
    original_builder = stock_detail_service._build_investor_trend_5day_map

    def _counted_builder(frame):
        call_count["value"] += 1
        return original_builder(frame)

    monkeypatch.setattr(stock_detail_service, "_build_investor_trend_5day_map", _counted_builder)

    # deep_copy=False 시나리오를 모사: 새로운 DataFrame 객체지만 attrs 메타데이터는 동일
    first = trend_df.copy(deep=False)
    second = trend_df.copy(deep=False)

    first_result = _get_or_build_investor_trend_5day_map(first)
    second_result = _get_or_build_investor_trend_5day_map(second)

    assert first_result == second_result
    assert call_count["value"] == 1


def test_investor_trend_5day_map_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    import services.kr_market_stock_detail_service as stock_detail_service

    trend_csv = tmp_path / "all_institutional_trend_data.csv"
    trend_csv.write_text("ticker,date,foreign_buy,inst_buy\n", encoding="utf-8")

    signature = (123456789, 98765)
    trend_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 2, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 3, "inst_buy": 30},
            {"ticker": "005930", "date": "2026-02-25", "foreign_buy": 4, "inst_buy": 40},
            {"ticker": "005930", "date": "2026-02-26", "foreign_buy": 5, "inst_buy": 50},
        ]
    )
    trend_df.attrs["kr_cache_filepath"] = str(trend_csv)
    trend_df.attrs["kr_cache_signature"] = signature
    trend_df.attrs["kr_cache_usecols"] = ("ticker", "date", "foreign_buy", "inst_buy")

    with stock_detail_service._INVESTOR_TREND_5DAY_CACHE_LOCK:
        stock_detail_service._INVESTOR_TREND_5DAY_CACHE.clear()

    first = _get_or_build_investor_trend_5day_map(trend_df.copy(deep=False))
    assert first["005930"] == (15, 150)

    with stock_detail_service._INVESTOR_TREND_5DAY_CACHE_LOCK:
        stock_detail_service._INVESTOR_TREND_5DAY_CACHE.clear()

    monkeypatch.setattr(
        stock_detail_service,
        "_build_investor_trend_5day_map",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should load from sqlite snapshot")),
    )

    second = _get_or_build_investor_trend_5day_map(trend_df.copy(deep=False))
    assert second["005930"] == (15, 150)

    sqlite_cache_key = stock_detail_service._investor_trend_5day_sqlite_cache_key(str(trend_csv))
    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (sqlite_cache_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1


def test_load_naver_stock_detail_payload_clears_event_loop_after_run(monkeypatch):
    fake_collectors = types.ModuleType("engine.collectors")

    class _FakeCollector:
        async def get_stock_detail_info(self, _ticker):
            return {"name": "테스트"}

        async def get_financials(self, _ticker):
            return {"revenue": 1}

    fake_collectors.NaverFinanceCollector = _FakeCollector
    monkeypatch.setitem(sys.modules, "engine.collectors", fake_collectors)

    calls: list[object] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    original_set_event_loop = stock_detail_service.asyncio.set_event_loop

    def _spy_set_event_loop(loop):
        calls.append(loop)
        return original_set_event_loop(loop)

    monkeypatch.setattr(stock_detail_service.asyncio, "set_event_loop", _spy_set_event_loop)

    payload = load_naver_stock_detail_payload("005930")

    assert payload is not None
    assert calls
    assert calls[-1] is None


def test_load_naver_stock_detail_payload_prefers_modular_collector_import(monkeypatch):
    fake_collectors = types.ModuleType("engine.collectors")

    class _LegacyCollector:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("legacy collector import should not be used when modular collector exists")

    fake_collectors.NaverFinanceCollector = _LegacyCollector

    fake_collectors_naver = types.ModuleType("engine.collectors.naver")

    class _ModularCollector:
        async def get_stock_detail_info(self, _ticker):
            return {"name": "모듈형"}

        async def get_financials(self, _ticker):
            return {"revenue": 123}

    fake_collectors_naver.NaverFinanceCollector = _ModularCollector

    monkeypatch.setitem(sys.modules, "engine.collectors", fake_collectors)
    monkeypatch.setitem(sys.modules, "engine.collectors.naver", fake_collectors_naver)

    payload = load_naver_stock_detail_payload("005930")

    assert payload is not None
    assert payload["name"] == "모듈형"
    assert payload["financials"]["revenue"] == 123


def test_fetch_stock_detail_payload_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    import services.kr_market_stock_detail_service as stock_detail_service

    with stock_detail_service._STOCK_DETAIL_CACHE_LOCK:
        stock_detail_service._STOCK_DETAIL_CACHE.clear()

    monkeypatch.setattr(
        stock_detail_service,
        "_current_stock_detail_cache_slot",
        lambda now=None: "20260226:12",
    )

    def _fake_sqlite_context(*, ticker_padded: str, cache_slot: str, data_dir: str | None):
        _ = data_dir
        return (
            str(tmp_path / f"{ticker_padded}__{cache_slot}.snapshot"),
            (71, 71),
            str(tmp_path),
        )

    monkeypatch.setattr(stock_detail_service, "_stock_detail_sqlite_context", _fake_sqlite_context)
    monkeypatch.setattr(
        stock_detail_service,
        "build_toss_detail_payload",
        lambda ticker_padded, _toss_data: {
            "code": ticker_padded,
            "name": "테스트",
            "market": "KOSPI",
            "priceInfo": {"current": 70000},
            "yearRange": {"high_52w": 0, "low_52w": 0},
            "indicators": {"marketCap": 0, "per": 0, "pbr": 0},
            "investorTrend": {"foreign": 0, "institution": 0, "individual": 0},
            "financials": {"revenue": 0, "operatingProfit": 0, "netIncome": 0},
            "safety": {"debtRatio": 0, "currentRatio": 0},
        },
    )
    monkeypatch.setattr(
        stock_detail_service,
        "append_investor_trend_5day",
        lambda payload, *_args, **_kwargs: payload.setdefault(
            "investorTrend5Day",
            {"foreign": 1, "institution": 2},
        ),
    )

    calls = {"count": 0}

    class _FakeTossCollector:
        def get_full_stock_detail(self, _ticker):
            calls["count"] += 1
            return {"name": "테스트"}

    fake_toss_module = types.ModuleType("engine.toss_collector")
    fake_toss_module.TossCollector = _FakeTossCollector
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss_module)

    logger = type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})()
    first_payload = fetch_stock_detail_payload(
        ticker="5930",
        load_csv_file=lambda _filename: pd.DataFrame(),
        logger=logger,
        data_dir=str(tmp_path),
    )
    assert calls["count"] == 1
    assert first_payload["code"] == "005930"
    assert first_payload["investorTrend5Day"] == {"foreign": 1, "institution": 2}

    with stock_detail_service._STOCK_DETAIL_CACHE_LOCK:
        stock_detail_service._STOCK_DETAIL_CACHE.clear()

    class _FailingTossCollector:
        def __init__(self):
            raise AssertionError("SQLite snapshot hit이면 TossCollector를 생성하면 안 됩니다.")

    fake_toss_module.TossCollector = _FailingTossCollector
    second_payload = fetch_stock_detail_payload(
        ticker="5930",
        load_csv_file=lambda _filename: pd.DataFrame(),
        logger=logger,
        data_dir=str(tmp_path),
    )

    assert second_payload == first_payload
    assert calls["count"] == 1
