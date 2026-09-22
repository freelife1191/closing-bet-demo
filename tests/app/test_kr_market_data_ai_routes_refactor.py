#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Data AI Routes 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging

import pandas as pd
from flask import Blueprint, Flask

import app.routes.kr_market_data_ai_routes as ai_routes
from services import kr_market_cumulative_cache as cumulative_cache


def test_load_cumulative_price_source_prefers_backtest_snapshot_loader():
    expected = pd.DataFrame(
        [{"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90}]
    )
    calls = {"snapshot": 0}

    def _snapshot_loader():
        calls["snapshot"] += 1
        return expected, {"005930": 100.0}

    deps = {
        "load_backtest_price_snapshot": _snapshot_loader,
        "load_csv_file": lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("csv loader should not run")),
    }

    loaded = ai_routes._load_cumulative_price_source(
        deps=deps,
        logger=logging.getLogger("test-cumulative-price-source"),
    )

    assert calls["snapshot"] == 1
    assert loaded.equals(expected)


def test_load_cumulative_price_source_falls_back_to_csv_when_snapshot_loader_fails(monkeypatch):
    expected = pd.DataFrame(
        [{"date": "2026-02-20", "ticker": "005930", "open": 95, "high": 110, "low": 90, "close": 100}]
    )
    calls = {"csv": 0}

    def _csv_loader(load_csv_file, filename: str, usecols=None):
        calls["csv"] += 1
        assert filename == "daily_prices.csv"
        assert usecols == ["date", "ticker", "open", "high", "low", "close"]
        return expected

    monkeypatch.setattr(ai_routes, "load_csv_readonly", _csv_loader)

    deps = {
        "load_backtest_price_snapshot": lambda: (_ for _ in ()).throw(RuntimeError("snapshot failure")),
        "load_csv_file": lambda _name: pd.DataFrame(),
    }

    loaded = ai_routes._load_cumulative_price_source(
        deps=deps,
        logger=logging.getLogger("test-cumulative-price-source-fallback"),
    )

    assert calls["csv"] == 1
    assert loaded.equals(expected)


def test_cumulative_route_reuses_sqlite_cache_after_memory_clear(tmp_path, monkeypatch):
    cumulative_cache.clear_cumulative_cache()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    daily_prices = tmp_path / "daily_prices.csv"
    daily_prices.write_text(
        "date,ticker,open,high,low,close\n2026-02-20,005930,95,110,90,100\n",
        encoding="utf-8",
    )
    result_file = tmp_path / "jongga_v2_results_20260220.json"
    result_file.write_text(
        '{"date":"2026-02-20","signals":[{"stock_code":"005930","entry_price":100}]}',
        encoding="utf-8",
    )

    state = {"block_loader": False}
    calls = {"load_results": 0, "build_trade": 0}

    def _load_results():
        if state["block_loader"]:
            raise AssertionError("result loader should not run when sqlite cache exists")
        calls["load_results"] += 1
        return [
            (
                str(result_file),
                {"date": "2026-02-20", "signals": [{"stock_code": "005930", "entry_price": 100}]},
            )
        ]

    def _build_trade(*_args, **_kwargs):
        if state["block_loader"]:
            raise AssertionError("trade builder should not run when sqlite cache exists")
        calls["build_trade"] += 1
        return {"id": "005930-2026-02-20", "roi": 3.0}

    deps = {
        "build_ai_analysis_payload_for_target_date": lambda **_k: {"signals": []},
        "build_latest_ai_analysis_payload": lambda **_k: {"signals": []},
        "load_json_file": lambda _name: {},
        "build_ai_signals_from_jongga_results": lambda **_k: [],
        "normalize_ai_payload_tickers": lambda payload: payload,
        "should_use_jongga_ai_payload": lambda *_a, **_k: False,
        "format_signal_date": lambda value: str(value),
        "load_jongga_result_payloads": _load_results,
        "load_backtest_price_snapshot": lambda: (
            pd.DataFrame(
                [{"date": "2026-02-20", "ticker": "005930", "close": 100, "high": 110, "low": 90}]
            ),
            {"005930": 100.0},
        ),
        "load_csv_file": lambda _name: pd.DataFrame(),
        "prepare_cumulative_price_dataframe": lambda df: df,
        "build_ticker_price_index": lambda _df: {},
        "extract_stats_date_from_results_filename": lambda _fp, fallback_date="": str(fallback_date),
        "build_cumulative_trade_record": _build_trade,
        "aggregate_cumulative_kpis": lambda trades, _price_df, _now: {"count": len(trades)},
        "paginate_items": lambda items, page, limit: (
            items[(page - 1) * limit : page * limit],
            {"page": page, "limit": limit, "total": len(items)},
        ),
        "get_data_path": lambda filename: str(tmp_path / filename),
        "data_dir_getter": lambda: str(tmp_path),
    }

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr", __name__)
    ai_routes.register_market_data_ai_routes(bp, logger=logging.getLogger(__name__), deps=deps)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    first = client.get("/api/kr/closing-bet/cumulative")
    assert first.status_code == 200
    assert first.get_json()["kpi"]["count"] == 1
    assert calls == {"load_results": 1, "build_trade": 1}

    cumulative_cache.clear_cumulative_cache()
    state["block_loader"] = True
    second = client.get("/api/kr/closing-bet/cumulative")
    assert second.status_code == 200
    assert second.get_json()["kpi"]["count"] == 1


def test_cumulative_route_handles_invalid_page_limit_query_params(tmp_path):
    cumulative_cache.clear_cumulative_cache()
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    deps = {
        "build_ai_analysis_payload_for_target_date": lambda **_k: {"signals": []},
        "build_latest_ai_analysis_payload": lambda **_k: {"signals": []},
        "load_json_file": lambda _name: {},
        "build_ai_signals_from_jongga_results": lambda **_k: [],
        "normalize_ai_payload_tickers": lambda payload: payload,
        "should_use_jongga_ai_payload": lambda *_a, **_k: False,
        "format_signal_date": lambda value: str(value),
        "load_jongga_result_payloads": lambda: [],
        "load_backtest_price_snapshot": lambda: (pd.DataFrame(), {}),
        "load_csv_file": lambda _name: pd.DataFrame(),
        "prepare_cumulative_price_dataframe": lambda df: df,
        "build_ticker_price_index": lambda _df: {},
        "extract_stats_date_from_results_filename": lambda _fp, fallback_date="": str(fallback_date),
        "build_cumulative_trade_record": lambda *_a, **_k: None,
        "aggregate_cumulative_kpis": lambda trades, _price_df, _now: {"count": len(trades)},
        "paginate_items": lambda items, page, limit: (
            items[(page - 1) * limit : page * limit],
            {"page": page, "limit": limit, "total": len(items)},
        ),
        "get_data_path": lambda filename: str(tmp_path / filename),
        "data_dir_getter": lambda: str(tmp_path),
    }

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr-invalid-query-test", __name__)
    ai_routes.register_market_data_ai_routes(bp, logger=logging.getLogger(__name__), deps=deps)
    app.register_blueprint(bp, url_prefix="/api/kr")
    client = app.test_client()

    response = client.get("/api/kr/closing-bet/cumulative?page=abc&limit=-10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["pagination"]["page"] == 1
    assert payload["pagination"]["limit"] == 50


def _filter_route_client(tmp_path, monkeypatch):
    """[FLOW-017] 필터 검사용. 거래 넷을 만드는 순서가 곧 서버 목록 순서다."""
    from services.kr_market_backtest_kpi_helpers import paginate_items

    cumulative_cache.clear_cumulative_cache()
    monkeypatch.setattr(
        cumulative_cache,
        "_CUMULATIVE_CACHE_DB_PATH",
        str(tmp_path / "runtime_cache.db"),
    )
    cumulative_cache._CUMULATIVE_SQLITE_READY.clear()

    signals = [
        {"id": "t0", "outcome": "WIN", "grade": "S"},
        {"id": "t1", "outcome": "LOSS", "grade": "A"},
        {"id": "t2", "outcome": "WIN", "grade": "A"},
        {"id": "t3", "outcome": "OPEN", "grade": "B"},
    ]
    deps = {
        "build_ai_analysis_payload_for_target_date": lambda **_k: {"signals": []},
        "build_latest_ai_analysis_payload": lambda **_k: {"signals": []},
        "load_json_file": lambda _name: {},
        "build_ai_signals_from_jongga_results": lambda **_k: [],
        "normalize_ai_payload_tickers": lambda payload: payload,
        "should_use_jongga_ai_payload": lambda *_a, **_k: False,
        "format_signal_date": lambda value: str(value),
        "load_jongga_result_payloads": lambda: [("r.json", {"signals": signals})],
        "load_backtest_price_snapshot": lambda: (pd.DataFrame(), {}),
        "load_csv_file": lambda _name: pd.DataFrame(),
        "prepare_cumulative_price_dataframe": lambda df: df,
        "build_ticker_price_index": lambda _df: {},
        "extract_stats_date_from_results_filename": lambda _fp, fallback_date="": str(fallback_date),
        "build_cumulative_trade_record": lambda signal, *_a, **_k: dict(signal),
        "aggregate_cumulative_kpis": lambda trades, _price_df, _now: {"count": len(trades)},
        "paginate_items": paginate_items,
        "get_data_path": lambda filename: str(tmp_path / filename),
        "data_dir_getter": lambda: str(tmp_path),
    }

    app = Flask(__name__)
    app.testing = True
    bp = Blueprint("kr-filter-test", __name__)
    ai_routes.register_market_data_ai_routes(bp, logger=logging.getLogger(__name__), deps=deps)
    app.register_blueprint(bp, url_prefix="/api/kr")
    return app.test_client()


def test_cumulative_route_filters_before_paginating_and_keeps_original_numbers(tmp_path, monkeypatch):
    client = _filter_route_client(tmp_path, monkeypatch)

    payload = client.get("/api/kr/closing-bet/cumulative?outcome=WIN&limit=1&page=2").get_json()

    # 성공 두 건 가운데 두 번째 페이지. 번호는 필터 전 전체 넷 기준(4,3,2,1)의 2 다.
    assert [(t["id"], t["no"]) for t in payload["trades"]] == [("t2", 2)]
    assert payload["pagination"]["total"] == 2
    assert payload["pagination"]["totalPages"] == 2

    both = client.get("/api/kr/closing-bet/cumulative?outcome=WIN&grade=A").get_json()
    assert [(t["id"], t["no"]) for t in both["trades"]] == [("t2", 2)]

    unfiltered = client.get("/api/kr/closing-bet/cumulative").get_json()
    assert [t["no"] for t in unfiltered["trades"]] == [4, 3, 2, 1]


def test_cumulative_route_counts_the_whole_list_regardless_of_filter(tmp_path, monkeypatch):
    client = _filter_route_client(tmp_path, monkeypatch)

    payload = client.get("/api/kr/closing-bet/cumulative?outcome=LOSS").get_json()

    assert payload["counts"] == {
        "total": 4,
        "outcome": {"WIN": 2, "LOSS": 1, "OPEN": 1},
        "grade": {"S": 1, "A": 2, "B": 1, "D": 0},
    }


def test_cumulative_route_rejects_unknown_filter_values(tmp_path, monkeypatch):
    client = _filter_route_client(tmp_path, monkeypatch)

    assert client.get("/api/kr/closing-bet/cumulative?outcome=All").status_code == 400
    assert client.get("/api/kr/closing-bet/cumulative?grade=C").status_code == 400
    assert client.get("/api/kr/closing-bet/cumulative?grade=S").status_code == 200
