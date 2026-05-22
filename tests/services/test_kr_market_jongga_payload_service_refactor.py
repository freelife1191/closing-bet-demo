#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KR Market Jongga Payload Service 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from services.kr_market_jongga_payload_service import build_jongga_latest_payload
import services.kr_market_jongga_payload_latest as latest_payload_module
import services.kr_market_data_cache_core as cache_core


def _reset_csv_cache_state() -> None:
    with cache_core.FILE_CACHE_LOCK:
        cache_core.CSV_FILE_CACHE.clear()
    cache_core._CSV_PAYLOAD_SQLITE_READY.clear()


def test_build_jongga_latest_payload_prefers_preloaded_price_map(tmp_path):
    latest_payload = {
        "date": "2026-02-21",
        "signals": [{"ticker": "000001", "entry_price": 10000, "grade": "A"}],
    }
    called = {"load_csv": 0}

    def _load_csv_file(_name: str):
        called["load_csv"] += 1
        raise AssertionError("load_csv_file should not be called when load_latest_price_map is provided")

    def _load_latest_price_map():
        return {"000001": 10123.0}

    def _apply_prices(signals, price_map):
        signals[0]["current_price"] = price_map["000001"]
        return 1

    result = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=_load_csv_file,
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=_apply_prices,
        load_latest_price_map=_load_latest_price_map,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 2, 21, 18, 0, 0),
    )

    assert called["load_csv"] == 0
    assert result["signals"][0]["current_price"] == 10123.0


def test_build_jongga_latest_payload_uses_latest_price_by_date_when_csv_unsorted(tmp_path):
    latest_payload = {
        "date": "2026-02-21",
        "signals": [{"ticker": "005930", "entry_price": 10000, "grade": "A"}],
    }

    def _load_csv_file(_name: str):
        return pd.DataFrame(
            [
                {"date": "2026-02-22", "ticker": "005930", "close": 120.0},
                {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            ]
        )

    def _apply_prices(signals, price_map):
        signals[0]["current_price"] = price_map["005930"]
        return 1

    result = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=_load_csv_file,
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=_apply_prices,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 2, 21, 18, 0, 0),
    )

    assert result["signals"][0]["current_price"] == 120.0


def test_build_jongga_latest_payload_hides_stale_latest_on_market_day(monkeypatch, tmp_path):
    latest_payload = {
        "date": "2026-03-03",
        "signals": [{"ticker": "005930", "entry_price": 10000, "grade": "A"}],
    }
    price_calls = {"count": 0}
    monkeypatch.setattr(
        latest_payload_module.MarketSchedule,
        "is_market_open",
        lambda _date: True,
    )

    result = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=lambda _name: pd.DataFrame(),
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=(
            lambda _signals, _price_map: price_calls.__setitem__(
                "count",
                price_calls["count"] + 1,
            )
        ),
        logger=logging.getLogger(__name__),
        now=datetime(2026, 3, 4, 18, 0, 0),
    )

    assert result["status"] == "stale"
    assert result["signals"] == []
    assert result["is_stale"] is True
    assert result["latest_available_date"] == "2026-03-03"
    assert "2026-03-03" in result["stale_warning"]
    assert price_calls["count"] == 0


def test_build_jongga_latest_payload_keeps_today_empty_result_without_recent_fallback(tmp_path):
    latest_payload = {
        "date": "2026-05-22",
        "signals": [],
        "filtered_count": 0,
        "by_grade": {"S": 0, "A": 0, "B": 0},
    }
    fallback_file = tmp_path / "jongga_v2_results_20260505.json"
    fallback_file.write_text(
        '{"date":"2026-05-05","signals":[{"ticker":"005930","grade":"S","score":{"total":12}}]}',
        encoding="utf-8",
    )

    result = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=lambda _name: pd.DataFrame(),
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=lambda _signals, _price_map: 0,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 5, 22, 18, 0, 0),
    )

    assert result["date"] == "2026-05-22"
    assert result["status"] == "no_data"
    assert result["signals"] == []
    assert result["filtered_count"] == 0
    assert result["by_grade"]["S"] == 0


def test_build_jongga_latest_payload_uses_sqlite_snapshot_when_load_csv_file_is_none(tmp_path, monkeypatch):
    _reset_csv_cache_state()
    latest_payload = {
        "date": "2026-02-21",
        "signals": [{"ticker": "005930", "entry_price": 10000, "grade": "A"}],
    }
    pd.DataFrame(
        [
            {"date": "2026-02-20", "ticker": "005930", "close": 100.0},
            {"date": "2026-02-22", "ticker": "005930", "close": 121.0},
        ]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")

    def _apply_prices(signals, price_map):
        signals[0]["current_price"] = price_map["005930"]
        return 1

    first = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=None,
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=_apply_prices,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 2, 21, 18, 0, 0),
    )
    assert first["signals"][0]["current_price"] == 121.0

    with cache_core.FILE_CACHE_LOCK:
        cache_core.CSV_FILE_CACHE.clear()

    monkeypatch.setattr(
        cache_core.pd,
        "read_csv",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("read_csv should not run")),
    )
    second = build_jongga_latest_payload(
        data_dir=str(tmp_path),
        load_json_file=lambda _name: dict(latest_payload),
        load_csv_file=None,
        get_data_path=lambda filename: str(tmp_path / filename),
        recalculate_jongga_grades=lambda _payload: False,
        sort_jongga_signals=lambda _signals: None,
        normalize_jongga_signals_for_frontend=lambda _signals: None,
        apply_latest_prices_to_jongga_signals=_apply_prices,
        logger=logging.getLogger(__name__),
        now=datetime(2026, 2, 21, 18, 0, 0),
    )
    assert second["signals"][0]["current_price"] == 121.0
