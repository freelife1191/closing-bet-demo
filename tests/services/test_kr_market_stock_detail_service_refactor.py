#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Stock Detail Service 리팩토링 테스트
"""

from __future__ import annotations

import sys
import types

import pytest

from services.kr_market_stock_detail_service import (
    append_investor_trend_5day,
    build_default_stock_detail_payload,
    fetch_stock_detail_payload,
    load_naver_stock_detail_payload,
)


def test_append_investor_trend_5day_prefers_unified_service_when_data_dir_provided(monkeypatch, tmp_path):
    payload: dict[str, object] = {}
    captured_calls: list[dict[str, object]] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        lambda **kwargs: captured_calls.append(dict(kwargs)) or {"foreign": 321, "institution": 654},
    )

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=str(tmp_path),
    )

    assert payload["investorTrend5Day"] == {"foreign": 321, "institution": 654}
    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is True


def test_append_investor_trend_5day_calls_the_service_once(monkeypatch, tmp_path):
    """서비스가 이상징후일 때만 참조를 조회하므로 호출자가 두 번 부를 이유가 없다."""
    payload: dict[str, object] = {}
    captured_calls: list[dict[str, object]] = []

    import services.kr_market_stock_detail_service as stock_detail_service

    def _fake_get_trend(**kwargs):
        captured_calls.append(dict(kwargs))
        return {
            "foreign": 333,
            "institution": 444,
            "quality": {"csv_anomaly_flags": ["stale_csv"]},
        }

    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        _fake_get_trend,
    )

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=str(tmp_path),
    )

    assert payload["investorTrend5Day"] == {"foreign": 333, "institution": 444}
    assert len(captured_calls) == 1
    assert captured_calls[0]["verify_with_references"] is True


@pytest.mark.parametrize("outcome, data_dir", [("none", "/tmp/unused"), ("raise", "/tmp/unused"), ("none", None)])
def test_append_investor_trend_5day_leaves_the_key_out_without_a_unified_value(monkeypatch, outcome, data_dir):
    """[FLOW-023] 통합 서비스가 값을 주지 않으면 키를 넣지 않는다. 모달은 Toss 합계 「(N일)」로 물러선다."""
    import services.kr_market_stock_detail_service as stock_detail_service

    calls: list[dict[str, object]] = []

    def _fake_get_trend(**kwargs):
        calls.append(kwargs)
        if outcome == "raise":
            raise RuntimeError("boom")
        return None

    monkeypatch.setattr(stock_detail_service, "get_investor_trend_5day_for_ticker", _fake_get_trend)
    payload: dict[str, object] = {}

    append_investor_trend_5day(
        payload=payload,
        ticker_padded="005930",
        logger=type("L", (), {"warning": lambda *_a, **_k: None, "debug": lambda *_a, **_k: None})(),
        data_dir=data_dir,
    )

    assert "investorTrend5Day" not in payload
    # data_dir 가 없으면 서비스를 부르지 않는다. 예외는 삼켜지므로 호출 기록으로 본다
    assert len(calls) == (0 if data_dir is None else 1)


def test_default_stock_detail_payload_leaves_flow_missing():
    """[JONGGA-042] 수급을 모르는 기본 페이로드는 0 이 아니라 결측을 보낸다."""
    trend = build_default_stock_detail_payload("005930")["investorTrend"]
    assert trend["foreign"] is None
    assert trend["institution"] is None


def test_load_naver_stock_detail_payload_clears_event_loop_after_run(monkeypatch):
    fake_collectors = types.ModuleType("engine.collectors")

    class _FakeCollector:
        async def get_stock_detail_info(self, _ticker):
            return {"name": "테스트"}

        async def get_financials(self, _ticker):
            return {"revenue": 1}

    fake_collectors.NaverFinanceCollector = _FakeCollector
    monkeypatch.setitem(sys.modules, "engine.collectors", fake_collectors)
    # 실제 구현이 우선 import하는 모듈 경로도 격리해 네트워크 호출을 막는다.
    fake_naver = types.ModuleType("engine.collectors.naver")
    fake_naver.NaverFinanceCollector = _FakeCollector
    monkeypatch.setitem(sys.modules, "engine.collectors.naver", fake_naver)

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
            "investorTrend": {"foreign": 0, "institution": 0, "individual": 0, "individual_schema": 1},
            "financials": {"revenue": 0, "operatingProfit": 0, "netIncome": 0},
            "safety": {"debtRatio": 0, "currentRatio": 0},
        },
    )
    # 실제 append 를 돌려 fetch → append 호출의 인자 모양도 함께 고정한다([FLOW-023] /review M1)
    monkeypatch.setattr(
        stock_detail_service,
        "get_investor_trend_5day_for_ticker",
        lambda **_kwargs: {"foreign": 1, "institution": 2},
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
        logger=logger,
        data_dir=str(tmp_path),
    )

    assert second_payload == first_payload
    assert calls["count"] == 1
