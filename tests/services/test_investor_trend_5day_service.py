#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investor Trend 5-Day Service 테스트
"""

from __future__ import annotations

import sys
import sqlite3
import types
from datetime import datetime

import pandas as pd

import services.investor_trend_5day_service as trend_service
import services.kr_market_data_cache_sqlite_payload as sqlite_payload_cache


def test_load_investor_trend_5day_map_aggregates_with_latest_first_details(tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 2, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 3, "inst_buy": 30},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 4, "inst_buy": 40},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 5, "inst_buy": 50},
            # 5일 미만 종목은 제외
            {"ticker": "000660", "date": "2026-02-24", "foreign_buy": 100, "inst_buy": 200},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service.load_investor_trend_5day_map(data_dir=str(tmp_path))

    assert "005930" in trend_map
    assert "000660" not in trend_map
    assert trend_map["005930"]["foreign"] == 15
    assert trend_map["005930"]["institution"] == 150
    assert trend_map["005930"]["details"][0] == {
        "netForeignerBuyVolume": 5,
        "netInstitutionBuyVolume": 50,
    }


def test_load_investor_trend_5day_map_applies_target_date_filter(tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-19", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 2, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 3, "inst_buy": 30},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 4, "inst_buy": 40},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 5, "inst_buy": 50},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 999, "inst_buy": 999},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service.load_investor_trend_5day_map(
        data_dir=str(tmp_path),
        target_datetime=datetime(2026, 2, 23),
    )

    assert trend_map["005930"]["foreign"] == 15
    assert trend_map["005930"]["institution"] == 150
    assert trend_map["005930"]["details"][0]["netForeignerBuyVolume"] == 5


def test_load_trend_df_projects_existing_columns_on_usecols_mismatch(monkeypatch):
    calls = {"count": 0, "usecols": []}

    def _fake_load_csv_file(_data_dir, _filename, **kwargs):
        calls["count"] += 1
        calls["usecols"].append(kwargs.get("usecols"))
        if kwargs.get("usecols") is not None:
            raise ValueError("Usecols do not match columns")
        return pd.DataFrame(
            [
                {"ticker": "005930", "foreign_buy": 1, "extra_col": 999},
            ]
        )

    monkeypatch.setattr(trend_service, "load_csv_file", _fake_load_csv_file)

    loaded = trend_service._load_trend_df(
        data_dir="/tmp",
        filename="all_institutional_trend_data.csv",
        signature=(1, 1),
    )

    assert calls["count"] == 2
    assert calls["usecols"][0] is not None
    assert calls["usecols"][1] is None
    assert list(loaded.columns) == ["ticker", "foreign_buy"]


def test_investor_trend_5day_service_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    trend_path = tmp_path / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 10},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 2, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 3, "inst_buy": 30},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 4, "inst_buy": 40},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 5, "inst_buy": 50},
        ]
    ).to_csv(trend_path, index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    first = trend_service.load_investor_trend_5day_map(data_dir=str(tmp_path))
    assert first["005930"]["foreign"] == 15

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_build_trend_map",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite snapshot")),
    )

    second = trend_service.load_investor_trend_5day_map(data_dir=str(tmp_path))
    assert second["005930"]["institution"] == 150

    sqlite_key = trend_service._sqlite_cache_key(str(trend_path), "latest")
    with sqlite3.connect(tmp_path / "runtime_cache.db") as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (sqlite_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1


def test_get_investor_trend_5day_for_ticker_replaces_anomalous_csv_with_pykrx(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 50_000_000_000, "inst_buy": 40_000_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 10_000_000_000,
            "institution": 8_000_000_000,
            "details": [
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 2_000_000_000},
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: {
            "foreign": 10_500_000_000,
            "institution": 8_500_000_000,
            "details": [
                {"netForeignerBuyVolume": 2_100_000_000, "netInstitutionBuyVolume": 1_700_000_000},
                {"netForeignerBuyVolume": 2_100_000_000, "netInstitutionBuyVolume": 1_700_000_000},
                {"netForeignerBuyVolume": 2_100_000_000, "netInstitutionBuyVolume": 1_700_000_000},
                {"netForeignerBuyVolume": 2_100_000_000, "netInstitutionBuyVolume": 1_700_000_000},
                {"netForeignerBuyVolume": 2_100_000_000, "netInstitutionBuyVolume": 1_700_000_000},
            ],
            "latest_date": "2026-02-24",
            "source": "toss",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["foreign"] == 10_000_000_000
    assert result["institution"] == 8_000_000_000
    assert "single_day_spike" in result["quality"]["csv_anomaly_flags"]


def test_get_investor_trend_5day_for_ticker_skips_toss_when_pykrx_available(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 50_000_000_000, "inst_buy": 40_000_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 9_000_000_000,
            "institution": 7_000_000_000,
            "details": [
                {"netForeignerBuyVolume": 1_800_000_000, "netInstitutionBuyVolume": 1_400_000_000},
                {"netForeignerBuyVolume": 1_800_000_000, "netInstitutionBuyVolume": 1_400_000_000},
                {"netForeignerBuyVolume": 1_800_000_000, "netInstitutionBuyVolume": 1_400_000_000},
                {"netForeignerBuyVolume": 1_800_000_000, "netInstitutionBuyVolume": 1_400_000_000},
                {"netForeignerBuyVolume": 1_800_000_000, "netInstitutionBuyVolume": 1_400_000_000},
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("toss fetch should be skipped")),
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["foreign"] == 9_000_000_000


def test_get_investor_trend_5day_for_ticker_skips_reference_when_csv_is_normal(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 10, "inst_buy": 20},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 11, "inst_buy": 21},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 12, "inst_buy": 22},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 13, "inst_buy": 23},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 14, "inst_buy": 24},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("reference fetch should be skipped")),
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("reference fetch should be skipped")),
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "csv"
    assert result["foreign"] == 60
    assert result["institution"] == 110


def test_get_investor_trend_5day_for_ticker_reuses_reference_sqlite_after_memory_clear(
    monkeypatch,
    tmp_path,
):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 50_000_000_000, "inst_buy": 40_000_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 10_000_000_000,
            "institution": 8_000_000_000,
            "details": [
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_500_000_000},
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 2_000_000_000},
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", lambda **_kwargs: None)

    first = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )
    assert first is not None
    assert first["source"] == "pykrx"
    assert first["foreign"] == 10_000_000_000

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should use sqlite reference snapshot")),
    )

    second = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )
    assert second is not None
    assert second["source"] == "pykrx"
    assert second["institution"] == 8_000_000_000

    reference_sqlite_key, _ = trend_service._reference_sqlite_context(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )
    reference_db_path = sqlite_payload_cache.resolve_payload_sqlite_db_path(reference_sqlite_key)
    with sqlite3.connect(reference_db_path) as conn:
        row_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM json_file_payload_cache
                WHERE filepath = ?
                """,
                (reference_sqlite_key,),
            ).fetchone()[0]
        )
    assert row_count >= 1


def test_reference_cache_rotates_by_reference_token_for_latest(monkeypatch, tmp_path):
    trend_service.clear_investor_trend_5day_memory_cache()

    cache_token = {"value": "20260224"}
    monkeypatch.setattr(
        trend_service,
        "_reference_cache_token",
        lambda **_kwargs: cache_token["value"],
    )

    call_count = {"value": 0}

    def _fake_fetch_pykrx_reference_trend(**_kwargs):
        call_count["value"] += 1
        return {
            "foreign": 1_000,
            "institution": 2_000,
            "details": [
                {"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400},
                {"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400},
                {"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400},
                {"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400},
                {"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400},
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        }

    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", _fake_fetch_pykrx_reference_trend)

    first = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )
    assert first is not None

    second = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )
    assert second is not None

    cache_token["value"] = "20260225"
    third = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )
    assert third is not None

    assert call_count["value"] == 2


def test_reference_cache_does_not_pin_miss_result(monkeypatch, tmp_path):
    trend_service.clear_investor_trend_5day_memory_cache()

    call_count = {"value": 0}

    def _fake_fetch_pykrx_reference_trend(**_kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return None
        return {
            "foreign": 1_500,
            "institution": 2_500,
            "details": [
                {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": 500},
                {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": 500},
                {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": 500},
                {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": 500},
                {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": 500},
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        }

    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", _fake_fetch_pykrx_reference_trend)

    first = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )
    second = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="pykrx",
        ticker="005930",
        target_datetime=None,
    )

    assert first is None
    assert second is not None
    assert second["foreign"] == 1_500
    assert call_count["value"] == 2


def test_get_reference_trend_cached_skips_toss_lookup_for_historical_target(monkeypatch, tmp_path):
    trend_service.clear_investor_trend_5day_memory_cache()

    monkeypatch.setattr(
        trend_service,
        "load_json_payload_from_sqlite",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("sqlite lookup should be skipped")),
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("toss fetch should be skipped")),
    )

    result = trend_service._get_reference_trend_cached(
        data_dir=str(tmp_path),
        source="toss",
        ticker="005930",
        target_datetime=datetime(2026, 2, 24),
    )

    assert result is None


def test_get_investor_trend_5day_for_ticker_does_not_try_toss_for_historical_target(monkeypatch, tmp_path):
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 1, "inst_buy": 1},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 50_000_000_000, "inst_buy": 40_000_000_000},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_kwargs: None)
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("toss fetch should be skipped")),
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
        target_datetime=datetime(2026, 2, 24),
    )

    assert result is not None
    assert result["source"] == "csv"
    assert "single_day_spike" in result["quality"]["csv_anomaly_flags"]


def test_resolve_pykrx_latest_market_date_reuses_sqlite_snapshot_after_memory_clear(monkeypatch, tmp_path):
    trend_service.clear_investor_trend_5day_memory_cache()

    call_count = {"value": 0}

    def _fake_get_index_ohlcv_by_date(*_args, **_kwargs):
        call_count["value"] += 1
        idx = pd.to_datetime(["2026-02-24"])
        return pd.DataFrame({"종가": [2_600]}, index=idx)

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = types.SimpleNamespace(get_index_ohlcv_by_date=_fake_get_index_ohlcv_by_date)
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    first = trend_service._resolve_pykrx_latest_market_date(data_dir=str(tmp_path))
    assert first.strftime("%Y-%m-%d") == "2026-02-24"
    assert call_count["value"] == 1

    trend_service.clear_investor_trend_5day_memory_cache()
    fake_pykrx.stock = types.SimpleNamespace(
        get_index_ohlcv_by_date=lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("pykrx call should be skipped by sqlite snapshot")
        )
    )

    second = trend_service._resolve_pykrx_latest_market_date(data_dir=str(tmp_path))
    assert second.strftime("%Y-%m-%d") == "2026-02-24"
    assert call_count["value"] == 1
