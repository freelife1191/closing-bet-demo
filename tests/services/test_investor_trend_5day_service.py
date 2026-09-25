#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Investor Trend 5-Day Service 테스트
"""

from __future__ import annotations

import json
import sys
import sqlite3
import types
from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from pykrx import stock as pykrx_stock

import services.investor_trend_5day_service as trend_service
import services.kr_market_data_cache_sqlite_payload as sqlite_payload_cache


@pytest.fixture(autouse=True)
def _no_krx_market_date_lookup(monkeypatch):
    """[INFRA-121] 참조 캐시 토큰의 최신 거래일 조회가 KRX 로 나가지 않게 한다. 빈 결과면 오늘로 물러난다."""
    monkeypatch.setattr(pykrx_stock, "get_index_ohlcv_by_date", lambda *args, **kwargs: pd.DataFrame())


def test_trend_map_aggregates_with_latest_first_details(tmp_path):
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
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert "005930" in trend_map
    assert "000660" not in trend_map
    assert trend_map["005930"]["foreign"] == 15
    assert trend_map["005930"]["institution"] == 150
    assert trend_map["005930"]["details"][0] == {
        "netForeignerBuyVolume": 5,
        "netInstitutionBuyVolume": 50,
    }


def test_trend_map_applies_target_date_filter(tmp_path):
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
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
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
    first = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )
    assert first["005930"]["foreign"] == 15

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_build_trend_map",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("should use sqlite snapshot")),
    )

    second = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )
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
    """verify_with_references 의 기본값 True 가 곧 「이상징후일 때만 참조 조회」다.

    호출자가 False 로 먼저 부르고 플래그를 확인한 뒤 True 로 다시 부르는 패턴은 첫
    반환값을 버리는 중복 호출이다. 이 검사가 그 계약을 고정한다.
    """
    # 오늘 기준 최근 5영업일을 사용해 stale_csv 플래그가 발생하지 않도록 한다.
    today = datetime.now().date()
    recent_dates = [
        (today - pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in (4, 3, 2, 1, 0)
    ]
    pd.DataFrame(
        [
            {"ticker": "005930", "date": recent_dates[0], "foreign_buy": 10, "inst_buy": 20},
            {"ticker": "005930", "date": recent_dates[1], "foreign_buy": 11, "inst_buy": 21},
            {"ticker": "005930", "date": recent_dates[2], "foreign_buy": 12, "inst_buy": 22},
            {"ticker": "005930", "date": recent_dates[3], "foreign_buy": 13, "inst_buy": 23},
            {"ticker": "005930", "date": recent_dates[4], "foreign_buy": 14, "inst_buy": 24},
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
    assert result["quality"]["csv_anomaly_flags"] == []
    assert result["foreign"] == 60
    assert result["institution"] == 110


def test_stale_csv_is_replaced_by_the_reference(monkeypatch, tmp_path):
    """영업일로 세어도 낡은 CSV 는 참조로 갈아 끼운다.

    stale_csv 는 CSV 가 참조와 다른 5거래일을 본다는 뜻이다. 두 자료의 5일 합계가
    우연히 비슷하더라도 하루별 값까지 같다고 볼 근거가 없다. 스크리너 점수는
    details[0](당일 수급)과 연속 부호로 25점까지 매기므로, 합계만 보고 낡은 CSV 를
    남기면 지난달 수급이 오늘 점수로 들어간다.
    """
    pd.DataFrame(
        [
            {"ticker": "005930", "date": date, "foreign_buy": 2_000_000_000, "inst_buy": 1_600_000_000}
            for date in ("2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24")
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
                {"netForeignerBuyVolume": 2_000_000_000, "netInstitutionBuyVolume": 1_600_000_000}
                for _ in range(5)
            ],
            "latest_date": "2026-09-04",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert "stale_csv" in result["quality"]["csv_anomaly_flags"]
    assert result["source"] == "pykrx"
    assert result["latest_date"] == "2026-09-04"


def test_stale_flag_counts_business_days_not_calendar_days(monkeypatch, tmp_path):
    """주말만 낀 자료는 낡은 것으로 보지 않는다.

    달력 날짜로 세면 금요일에 갱신된 자료가 그 주 수요일에 이미 4일을 넘긴다. 주말이
    낀 것만으로 온 시장에 stale_csv 가 붙고, 종목마다 참조 조회가 따라붙는다.
    이 검사는 금요일 자료를 그다음 주 수요일에 읽는 상황을 세운다. 달력으로는 닷새라
    옛 판정에서는 stale 이 붙지만, 영업일로는 사흘이라 붙지 않는다.
    """
    friday = datetime(2026, 8, 21)
    csv_dates = [
        (friday - pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in (6, 5, 4, 3, 0)
    ]
    payload = {
        "foreign": 100,
        "institution": 200,
        "details": [{"netForeignerBuyVolume": 20, "netInstitutionBuyVolume": 40} for _ in range(5)],
        "days": 5,
        "latest_date": csv_dates[-1],
    }

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 26)  # 수요일. 달력으로 닷새, 영업일로 사흘

    monkeypatch.setattr(trend_service, "datetime", _FrozenDatetime)

    flags = trend_service._detect_csv_anomaly_flags(payload, target_datetime=None)
    assert flags == []

    class _LaterDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 8, 28)  # 그다음 금요일. 영업일로 다섯째 날

    monkeypatch.setattr(trend_service, "datetime", _LaterDatetime)
    assert "stale_csv" in trend_service._detect_csv_anomaly_flags(payload, target_datetime=None)


def test_stale_flag_skips_market_holidays(monkeypatch, tmp_path):
    """설 연휴처럼 평일에 걸린 휴장일도 세지 않는다.

    주말만 걸러서는 부족하다. 2026년 설 연휴는 2월 16일부터 18일까지 사흘이 평일에
    걸리므로, 2월 13일 금요일에 갱신된 자료를 2월 20일 금요일에 읽으면 주말만 뺀
    영업일이 닷새가 되어 낡은 것으로 판정된다. 그 사이 실제로 열린 장은 2월 19일
    하루뿐이다. 연휴 직후 온 시장에 참조 조회가 붙던 것이 이 자리에서 갈린다.
    """
    payload = {
        "foreign": 100,
        "institution": 200,
        "details": [{"netForeignerBuyVolume": 20, "netInstitutionBuyVolume": 40} for _ in range(5)],
        "days": 5,
        "latest_date": "2026-02-13",
    }

    class _AfterLunarNewYear(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 2, 20)

    monkeypatch.setattr(trend_service, "datetime", _AfterLunarNewYear)
    assert trend_service._detect_csv_anomaly_flags(payload, target_datetime=None) == []


def test_missing_csv_takes_the_reference(monkeypatch, tmp_path):
    """CSV 에 그 종목이 아예 없어도 참조가 있으면 값을 돌려준다.

    이 분기가 사라지면 CSV 에 없는 종목은 참조가 값을 갖고 있어도 None 으로 떨어지고,
    호출자는 수급 점수를 0 으로 매긴다.
    """
    pd.DataFrame(
        [
            {"ticker": "000660", "date": date, "foreign_buy": 10, "inst_buy": 20}
            for date in ("2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24")
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 3_000_000_000,
            "institution": 2_000_000_000,
            "details": [
                {"netForeignerBuyVolume": 600_000_000, "netInstitutionBuyVolume": 400_000_000}
                for _ in range(5)
            ],
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["foreign"] == 3_000_000_000
    assert "missing_csv" in result["quality"]["csv_anomaly_flags"]


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

    clock = [100.0]
    monkeypatch.setattr(trend_service.time, "monotonic", lambda: clock[0])
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
    clock[0] += 60.0  # Short failure TTL expires; misses are never pinned indefinitely.
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


def test_safe_int_survives_infinite_values_from_external_json():
    """json.loads 는 Infinity 와 1e400 을 inf 로 파싱하고 int(inf) 는 OverflowError 다.

    참조 자료는 비공식 API 에서 오므로 이 값이 들어올 수 있다. 신뢰 경계의 검증
    장치가 스스로 터지면 그 종목의 조회가 예외로 끝난다.
    """
    assert trend_service._safe_int(float("inf")) == 0
    assert trend_service._safe_int(float("-inf")) == 0
    assert trend_service._safe_int(float("nan")) == 0
    assert trend_service._safe_int(json.loads('{"v": Infinity}')["v"]) == 0
    assert trend_service._safe_int(json.loads('{"v": 1e400}')["v"]) == 0


def test_verify_false_keeps_anomalous_csv_without_touching_references(monkeypatch, tmp_path):
    """verify_with_references=False 는 이상징후가 있어도 참조를 조회하지 않는다.

    [FLOW-026] 이후 운영 호출자는 모두 검증을 켠다. 이 검사는 CSV 판정만 떼어 보는 다른 검사들이
    기대는 격리 계약을 지킨다.
    """
    # 두 달 전 날짜라 stale_csv 가 붙는다.
    old_dates = [
        (datetime.now().date() - pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in (64, 63, 62, 61, 60)
    ]
    pd.DataFrame(
        [
            {"ticker": "005930", "date": old_dates[0], "foreign_buy": 10, "inst_buy": 20},
            {"ticker": "005930", "date": old_dates[1], "foreign_buy": 11, "inst_buy": 21},
            {"ticker": "005930", "date": old_dates[2], "foreign_buy": 12, "inst_buy": 22},
            {"ticker": "005930", "date": old_dates[3], "foreign_buy": 13, "inst_buy": 23},
            {"ticker": "005930", "date": old_dates[4], "foreign_buy": 14, "inst_buy": 24},
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
        verify_with_references=False,
    )

    assert result is not None
    assert result["source"] == "csv"
    assert result["foreign"] == 60
    assert "stale_csv" in result["quality"]["csv_anomaly_flags"]


def _write_five_day_csv(tmp_path, *, ticker: str) -> None:
    """5거래일이 모인 정상 CSV 를 만든다. 5일 합은 외국인 6000, 기관 11000 이다."""
    pd.DataFrame(
        [
            {"ticker": ticker, "date": "2026-02-20", "foreign_buy": 1_000, "inst_buy": 2_000},
            {"ticker": ticker, "date": "2026-02-21", "foreign_buy": 1_100, "inst_buy": 2_100},
            {"ticker": ticker, "date": "2026-02-22", "foreign_buy": 1_200, "inst_buy": 2_200},
            {"ticker": ticker, "date": "2026-02-23", "foreign_buy": 1_300, "inst_buy": 2_300},
            {"ticker": ticker, "date": "2026-02-24", "foreign_buy": 1_400, "inst_buy": 2_400},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)


def test_trend_map_drops_a_ticker_with_a_blank_in_the_last_five_rows(tmp_path):
    """[FLOW-023] 최근 5행의 빈 칸·무한대는 0 이 아니라 결측이다. 더 오래된 행으로 창을 채우지 않는다."""
    rows = []
    for ticker, blank_at in (("005930", None), ("000660", "2026-02-23"), ("035720", "2026-02-19")):
        for day in ("2026-02-19", "2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"):
            rows.append({"ticker": ticker, "date": day,
                         "foreign_buy": "" if day == blank_at else 1, "inst_buy": 10})
    for day in ("2026-02-20", "2026-02-21", "2026-02-22", "2026-02-23", "2026-02-24"):
        rows.append({"ticker": "051910", "date": day, "foreign_buy": 1, "inst_buy": "inf" if day == "2026-02-24" else 10})
    # 파일 순서가 아니라 날짜로 창을 고른다. 거꾸로 쓰면 정렬 없이는 035720 창에 빈 칸이 들어온다
    pd.DataFrame(rows[::-1]).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert trend_map["005930"]["foreign"] == 5
    assert "000660" not in trend_map  # 최근 5행 안의 빈 칸
    assert trend_map["035720"]["foreign"] == 5  # 빈 칸이 6번째 이전 행에만 있다
    assert "051910" not in trend_map  # 무한대 한 칸이 map 전체를 깨뜨리지 않는다


def test_trend_map_drops_a_ticker_missing_a_day_inside_the_window(tmp_path):
    """[FLOW-025] 마지막 5행이 아니라 모든 종목에 공통인 최근 5거래일로 잰다.

    000020 은 02-20 행이 없어 마지막 5행이 02-17~02-24 의 6거래일에 걸치고, 000030 은 02-24 행이 없어 창이 하루 앞에서
    끝난다. 정상 종목을 여럿 두는 이유는 한 종목의 02-24 누락이 그날을 부분 날짜(전날의 80% 미만)로 만들지 않게 하려는 것이다.
    """
    days = ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24"]
    rows = []
    normal = [(f"00001{n}", None) for n in range(5)]
    # 000040 은 창 밖(02-17) 행만 없으므로 남는다
    normal.append(("000040", "2026-02-17"))
    for ticker, missing in normal + [("000020", "2026-02-20"), ("000030", "2026-02-24")]:
        for index, day in enumerate(days, start=1):
            if day != missing:
                rows.append({"ticker": ticker, "date": day, "foreign_buy": index, "inst_buy": 10 * index})
    pd.DataFrame(rows).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert sorted(trend_map) == [ticker for ticker, _ in normal]
    assert trend_map["000010"]["foreign"] == 2 + 3 + 4 + 5 + 6
    assert trend_map["000010"]["latest_date"] == "2026-02-24"
    assert trend_map["000010"]["details"][0] == {"netForeignerBuyVolume": 6, "netInstitutionBuyVolume": 60}


def test_trend_map_ignores_a_latest_date_that_only_some_tickers_have(tmp_path):
    """[FLOW-025] 최신 날짜가 일부 종목에만 들어왔으면 그날을 창에서 빼고 모두 직전 5거래일을 쓴다."""
    days = ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23"]
    rows = [
        {"ticker": f"00001{n}", "date": day, "foreign_buy": 1, "inst_buy": 10}
        for n in range(5) for day in days
    ]
    rows.append({"ticker": "000010", "date": "2026-02-24", "foreign_buy": 1_000, "inst_buy": 1_000})
    pd.DataFrame(rows).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    trend_map = trend_service._get_or_build_trend_map(
        data_dir=trend_service._normalize_data_dir(str(tmp_path)),
        filename=trend_service._TREND_FILENAME,
    )

    assert len(trend_map) == 5
    assert {payload["latest_date"] for payload in trend_map.values()} == {"2026-02-23"}
    assert trend_map["000010"]["foreign"] == 5


def test_stale_flag_uses_the_target_date_when_given():
    """[FLOW-025] 기준일을 준 호출도 CSV 의 마지막 날이 기준일보다 영업일 4일 넘게 앞서면 낡은 자료다."""
    payload = {
        "foreign": 5, "institution": 50, "latest_date": "2026-02-24",
        "details": [{"netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 10}] * 5,
    }

    assert "stale_csv" in trend_service._detect_csv_anomaly_flags(payload, target_datetime="2026-03-10")
    assert "stale_csv" not in trend_service._detect_csv_anomaly_flags(payload, target_datetime="2026-02-25")


def test_pykrx_reference_with_a_nan_day_is_rejected_as_insufficient_days(monkeypatch):
    """[FLOW-023] pykrx 가 하루 값을 NaN 으로 주면 0 이 아니라 결측이므로 참조를 버린다."""
    days = pd.to_datetime(["2026-02-18", "2026-02-19", "2026-02-20", "2026-02-23", "2026-02-24"])
    frame = pd.DataFrame(
        {"기관합계": [10.0, 10.0, 10.0, 10.0, 10.0], "외국인합계": [1.0, 2.0, float("nan"), 4.0, 5.0]},
        index=days,
    )
    monkeypatch.setattr(pykrx_stock, "get_market_trading_value_by_date", lambda *a, **k: frame)

    payload = trend_service._fetch_pykrx_reference_trend(ticker="005930", target_datetime="2026-02-24")

    assert payload["foreign"] == 12  # 값 있는 날만 더한다
    assert [d["netForeignerBuyVolume"] for d in payload["details"]] == [5, 4, None, 2, 1]
    normalized = trend_service._normalize_external_trend_payload(payload, source="pykrx")
    assert trend_service._reference_reject_reason(normalized) == "insufficient_days"


def test_extreme_csv_with_no_usable_reference_returns_nothing(monkeypatch, tmp_path):
    """[FLOW-023] 20조 상한을 넘은 CSV 는 참조가 없으면 값으로 쓰지 않는다. 과거 기준일에서도 같다."""
    pd.DataFrame(
        [{"ticker": "005930", "date": f"2026-02-{day}", "foreign_buy": 5_000_000_000_000, "inst_buy": 0}
         for day in ("20", "21", "22", "23", "24")]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_kwargs: None)
    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", lambda **_kwargs: None)

    assert trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930", data_dir=str(tmp_path), target_datetime="2026-02-24"
    ) is None
    # verify=False 는 플래그 붙은 CSV 를 그대로 돌려준다(호출자가 자기 폴백으로 빠진다)
    kept = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930", data_dir=str(tmp_path), target_datetime="2026-02-24", verify_with_references=False
    )
    assert "extreme_abs_total" in kept["quality"]["csv_anomaly_flags"]


def test_reference_reject_reason_accepts_a_complete_payload():
    payload = {
        "foreign": 1_000,
        "institution": 2_000,
        "details": [{"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400}] * 5,
    }
    assert trend_service._reference_reject_reason(payload) is None


def test_reference_reject_reason_rejects_short_or_missing_details():
    assert trend_service._reference_reject_reason(None) == "not_a_dict"
    assert (
        trend_service._reference_reject_reason(
            {"foreign": 1_000, "institution": 0, "details": []}
        )
        == "insufficient_days"
    )
    assert (
        trend_service._reference_reject_reason(
            {
                "foreign": 1_000,
                "institution": 0,
                "details": [{"netForeignerBuyVolume": 1_000, "netInstitutionBuyVolume": 0}] * 4,
            }
        )
        == "insufficient_days"
    )
    assert (
        trend_service._reference_reject_reason(
            {"foreign": 1_000, "institution": 0, "details": [None] * 5}
        )
        == "insufficient_days"
    )


def test_reference_reject_reason_rejects_an_all_zero_payload():
    payload = {
        "foreign": 0,
        "institution": 0,
        "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
    }
    assert trend_service._reference_reject_reason(payload) == "zero_total"


def test_reference_reject_reason_rejects_a_day_with_missing_volume():
    """[FLOW-022] 하루라도 수량이 비면 5일 합계가 5일치가 아니다. 5일 집계로 채택하지 않는다."""
    for side in ("netForeignerBuyVolume", "netInstitutionBuyVolume"):
        details = [{"netForeignerBuyVolume": 200, "netInstitutionBuyVolume": 400} for _ in range(5)]
        details[2][side] = None
        payload = {"foreign": 800, "institution": 1_600, "details": details}
        assert trend_service._reference_reject_reason(payload) == "insufficient_days", side


def test_reference_reject_reason_keeps_a_payload_whose_sum_cancels_out():
    """5일 합계가 0 이어도 하루별 값이 살아 있으면 정상 자료다."""
    payload = {
        "foreign": 0,
        "institution": 0,
        "details": [
            {"netForeignerBuyVolume": 500, "netInstitutionBuyVolume": -500},
            {"netForeignerBuyVolume": -500, "netInstitutionBuyVolume": 500},
            {"netForeignerBuyVolume": 300, "netInstitutionBuyVolume": -300},
            {"netForeignerBuyVolume": -300, "netInstitutionBuyVolume": 300},
            {"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0},
        ],
    }
    assert trend_service._reference_reject_reason(payload) is None


def test_reference_reject_reason_rejects_an_extreme_total():
    details = [{"netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 0}] * 5
    at_threshold = {
        "foreign": trend_service._CSV_EXTREME_ABS_TOTAL,
        "institution": 0,
        "details": details,
    }
    assert trend_service._reference_reject_reason(at_threshold) == "extreme_abs_total"

    just_below = {
        "foreign": trend_service._CSV_EXTREME_ABS_TOTAL - 1,
        "institution": 0,
        "details": details,
    }
    assert trend_service._reference_reject_reason(just_below) is None


def test_a_zero_reference_does_not_overwrite_a_stale_csv_and_nothing_is_returned(monkeypatch, tmp_path):
    """퇴화한 참조로 CSV 가 덮이지 않는다.

    이 검사가 없으면 거래정지 종목이나 파싱 실패로 전 항목이 0 이 된 참조가 5거래일이
    모인 CSV 를 통째로 덮고, 그 0 이 스크리너 수급 점수와 대시보드로 흘러간다.
    [FLOW-023] 낡은 CSV 도 최근 5일 값처럼 내보내지 않으므로 결과는 None 이다. 0 참조가
    채택됐다면 source 가 pykrx 인 0 값이 나오므로 None 이 「덮지 않았다」도 함께 보인다.
    """
    _write_five_day_csv(tmp_path, ticker="005930")

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 0,
            "institution": 0,
            "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", lambda **_kwargs: None)

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is None
    # None 은 CSV 가 map 에 없어서가 아니라 stale_csv 갈래 때문이다
    kept = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930", data_dir=str(tmp_path), verify_with_references=False
    )
    assert "stale_csv" in kept["quality"]["csv_anomaly_flags"]


def test_toss_is_tried_when_the_pykrx_reference_is_discarded(monkeypatch, tmp_path):
    """걸러 낸 참조는 없는 것과 같으므로 대체 자료를 찾아야 한다."""
    _write_five_day_csv(tmp_path, ticker="000660")

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 0,
            "institution": 0,
            "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(
        trend_service,
        "_fetch_toss_reference_trend",
        lambda **_kwargs: {
            "foreign": 7_000,
            "institution": 3_000,
            "details": [{"netForeignerBuyVolume": 1_400, "netInstitutionBuyVolume": 600}] * 5,
            "latest_date": "2026-02-24",
            "source": "toss",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "toss"
    assert result["quality"]["discarded_references"] == ["pykrx:zero_total"]
    assert result["quality"]["reference_sources"] == ["toss"]


def test_a_toss_reference_missing_one_day_does_not_replace_the_csv(monkeypatch, tmp_path):
    """[FLOW-022] 실제 Toss 파서·정규화를 거친 부분 일수 참조는 버려지고 CSV 가 남는다.

    [FLOW-023] 낡은 CSV 는 참조를 모두 버리면 None 이므로, 남는 CSV 는 최근 날짜에 하루 급등만 붙은 것으로 둔다.
    """
    from engine.toss_collector_metric_parsers import parse_investor_trend

    today = datetime.now().date()
    recent = [(today - pd.Timedelta(days=offset)).strftime("%Y-%m-%d") for offset in (4, 3, 2, 1, 0)]
    pd.DataFrame(
        [{"ticker": "005930", "date": day, "foreign_buy": 50_000_000_000 if day == recent[-1] else 1_000, "inst_buy": 0}
         for day in recent]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)
    rows = [
        {"baseDate": f"2026-02-{day}", "close": 100, "netIndividualsBuyVolume": 0,
         "netForeignerBuyVolume": foreign, "netInstitutionBuyVolume": 10}
        for day, foreign in zip(("27", "26", "25", "24", "23"), (1, 2, None, 4, 5))
    ]

    class _FakeToss:
        def get_investor_trend(self, code, days=5):
            return parse_investor_trend({"result": {"body": rows}}, days)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(trend_service, "_fetch_pykrx_reference_trend", lambda **_kwargs: None)
    # 캐시 토큰을 만들며 실제 pykrx 지수 조회(KRX 로그인)로 나가지 않게 막는다
    monkeypatch.setattr(trend_service, "_resolve_pykrx_latest_market_date", lambda **_kwargs: datetime(2026, 2, 27))
    monkeypatch.setattr(trend_service, "_get_toss_collector", lambda: _FakeToss())

    result = trend_service.get_investor_trend_5day_for_ticker(ticker="005930", data_dir=str(tmp_path))

    assert result is not None
    assert result["source"] == "csv"
    assert result["foreign"] == 50_000_004_000
    assert result["quality"]["csv_anomaly_flags"] == ["single_day_spike"]
    assert result["quality"]["discarded_references"] == ["toss:insufficient_days"]
    # CSV 에 없는 종목은 버린 뒤 남는 자료가 없다. 상세 API 는 키를 빼고 모달이 Toss 합계 「(N일)」로 물러선다
    assert trend_service.get_investor_trend_5day_for_ticker(ticker="000660", data_dir=str(tmp_path)) is None


def test_missing_csv_with_only_a_bad_reference_returns_nothing(monkeypatch, tmp_path):
    """CSV 도 없고 쓸 만한 참조도 없으면 자료가 없는 것이다."""
    _write_five_day_csv(tmp_path, ticker="000660")

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 5_000,
            "institution": 0,
            "details": [],
            "latest_date": "",
            "source": "pykrx",
        },
    )
    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", lambda **_kwargs: None)

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is None


def test_reference_only_marks_a_payload_built_without_any_csv(monkeypatch, tmp_path):
    """CSV 대응값이 아예 없어 참조가 유일한 진실인 값에 표식을 남긴다."""
    _write_five_day_csv(tmp_path, ticker="000660")

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 7_000,
            "institution": 3_000,
            "details": [{"netForeignerBuyVolume": 1_400, "netInstitutionBuyVolume": 600}] * 5,
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["quality"]["reference_only"] is True
    assert "missing_csv" in result["quality"]["csv_anomaly_flags"]


def test_reference_only_is_false_when_a_csv_row_existed(monkeypatch, tmp_path):
    """CSV 가 이상징후로 교체된 경우는 reference_only 가 아니다. 견줄 값이 남아 있다.

    _write_five_day_csv 의 날짜는 오늘 기준으로 stale_csv 에 해당하므로 참조가
    CSV 를 교체한다. 그래도 CSV 대응값 자체는 남아 있으므로 표식은 붙지 않는다.
    """
    _write_five_day_csv(tmp_path, ticker="005930")

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 7_000,
            "institution": 3_000,
            "details": [{"netForeignerBuyVolume": 1_400, "netInstitutionBuyVolume": 600}] * 5,
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
    )

    assert result is not None
    assert result["source"] == "pykrx"
    assert result["quality"]["reference_only"] is False
    assert result["quality"]["discarded_references"] == []


def test_historical_target_keeps_the_csv_when_the_pykrx_reference_is_discarded(monkeypatch, tmp_path):
    """과거 기준일에서 pykrx 참조를 걸러 내면 Toss 로 넘어가지 않고 CSV 가 남는다.

    Toss 는 과거 기준일 조회를 지원하지 않으므로 대체 자료가 없다. 백테스트가
    이 경로로 값을 읽으므로, 거부 판정이 그 자리에서 CSV 를 살리는지 확인한다.
    """
    # 하루만 값이 크고 나머지는 작아 single_day_spike 가 붙는다. target_datetime 을
    # 주면 stale_csv 는 붙지 않으므로 다른 이상징후로 참조 조회를 유도한다.
    pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "foreign_buy": 100_000_000, "inst_buy": 0},
            {"ticker": "005930", "date": "2026-02-21", "foreign_buy": 100_000_000, "inst_buy": 0},
            {"ticker": "005930", "date": "2026-02-22", "foreign_buy": 100_000_000, "inst_buy": 0},
            {"ticker": "005930", "date": "2026-02-23", "foreign_buy": 100_000_000, "inst_buy": 0},
            {"ticker": "005930", "date": "2026-02-24", "foreign_buy": 50_000_000_000, "inst_buy": 0},
        ]
    ).to_csv(tmp_path / "all_institutional_trend_data.csv", index=False)

    trend_service.clear_investor_trend_5day_memory_cache()
    monkeypatch.setattr(
        trend_service,
        "_fetch_pykrx_reference_trend",
        lambda **_kwargs: {
            "foreign": 0,
            "institution": 0,
            "details": [{"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 0}] * 5,
            "latest_date": "2026-02-24",
            "source": "pykrx",
        },
    )

    toss_calls: list[dict] = []

    def _record_toss(**kwargs):
        toss_calls.append(kwargs)
        return None

    monkeypatch.setattr(trend_service, "_fetch_toss_reference_trend", _record_toss)

    result = trend_service.get_investor_trend_5day_for_ticker(
        ticker="005930",
        data_dir=str(tmp_path),
        target_datetime="2026-02-24",
    )

    assert result is not None
    assert result["source"] == "csv"
    assert result["foreign"] == 50_400_000_000
    assert "single_day_spike" in result["quality"]["csv_anomaly_flags"]
    assert result["quality"]["discarded_references"] == ["pykrx:zero_total"]
    assert toss_calls == []


def _snapshot_payload(details_rows):
    return {"rows": {"005930": [15, 150, details_rows, "2026-02-24"]}}


def test_deserialize_rejects_a_row_whose_details_are_short():
    four_days = [[5, 50], [4, 40], [3, 30], [2, 20]]

    assert trend_service._deserialize_trend_map(_snapshot_payload(four_days)) is None


def test_deserialize_keeps_a_row_with_five_days():
    five_days = [[5, 50], [4, 40], [3, 30], [2, 20], [1, 10]]

    restored = trend_service._deserialize_trend_map(_snapshot_payload(five_days))

    assert restored is not None
    assert restored["005930"]["days"] == 5
    assert len(restored["005930"]["details"]) == 5


def test_deserialize_rejects_a_malformed_row_instead_of_dropping_it():
    payload = {
        "rows": {
            "005930": [15, 150, [[5, 50], [4, 40], [3, 30], [2, 20], [1, 10]], "2026-02-24"],
            "000660": ["not-a-number", 150, [], ""],
        }
    }

    assert trend_service._deserialize_trend_map(payload) is None


def test_deserialize_rejects_infinity_from_a_corrupted_snapshot():
    # json.loads 는 Infinity 를 float("inf") 로 파싱하고 int(float("inf")) 는
    # ValueError 가 아니라 OverflowError 를 던진다.
    payload = json.loads(
        '{"rows": {"005930": [15, 150, '
        '[[Infinity, 50], [4, 40], [3, 30], [2, 20], [1, 10]], "2026-02-24"]}}'
    )

    assert trend_service._deserialize_trend_map(payload) is None


def test_normalize_external_trend_payload_keeps_missing_day_as_none_through_cache():
    """[INFRA-109] 하루 결측은 0 이 아니라 None 이고, SQLite 캐시(JSON) 왕복 뒤에도 None 이다."""
    payload = {
        "foreign": 9,
        "institution": 5,
        "details": [
            {"netForeignerBuyVolume": "", "netInstitutionBuyVolume": None, "date": "2026-02-24"},
            {"netForeignerBuyVolume": 0, "netInstitutionBuyVolume": "0", "date": "2026-02-23"},
        ],
    }
    result = trend_service._normalize_external_trend_payload(payload, source="toss")

    assert result["details"][0]["netForeignerBuyVolume"] is None
    assert result["details"][0]["netInstitutionBuyVolume"] is None
    assert result["details"][1]["netForeignerBuyVolume"] == 0
    assert result["details"][1]["netInstitutionBuyVolume"] == 0
    reloaded = trend_service._normalize_external_trend_payload(
        json.loads(json.dumps(result)), source="toss", from_cache=True
    )
    assert reloaded["details"] == result["details"]


def test_normalize_external_trend_payload_missing_sum_is_missing_payload():
    assert trend_service._normalize_external_trend_payload({"foreign": None, "institution": 1}, source="toss") is None
    assert trend_service._normalize_external_trend_payload({"institution": 1}, source="toss") is None


def _fake_pykrx_frame(foreign, inst):
    index = pd.bdate_range("2026-02-26", periods=len(foreign))
    return pd.DataFrame({"외국인합계": foreign, "기관합계": inst}, index=index)


@pytest.mark.parametrize(
    ("foreign", "inst", "expected"),
    [
        ([1, 2, 3, 4, 5], [10, 20, 30, 40, 50], (15, 150)),
        ([1, 2, 3, 4], [10, 20, 30, 40], None),  # 4행
        ([1, np.nan, 3, 4, 5], [10, 20, 30, 40, 50], None),  # NaN 인 날
        ([0] * 5, [0] * 5, None),  # 전부 0
        ([], [], None),
    ],
)
def test_get_pykrx_trend_5day_returns_only_complete_windows(monkeypatch, tmp_path, foreign, inst, expected):
    """[FLOW-026] 수집기가 쓰는 pykrx 5일 값은 참조와 같은 거부 판정을 거친다. 부분합이나 0 을 돌려주지 않는다."""
    trend_service.clear_investor_trend_5day_memory_cache()
    fake = types.ModuleType("pykrx")
    fake.stock = types.SimpleNamespace(get_market_trading_value_by_date=lambda *_a: _fake_pykrx_frame(foreign, inst))
    monkeypatch.setitem(sys.modules, "pykrx", fake)

    result = trend_service.get_pykrx_trend_5day(ticker="005930", data_dir=str(tmp_path), target_datetime="2026-03-04")

    trend_service.clear_investor_trend_5day_memory_cache()
    assert (None if result is None else (result["foreign"], result["institution"])) == expected
