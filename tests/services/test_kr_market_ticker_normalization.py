#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""가격 및 종가 백테스트 티커 키 정규화 회귀 테스트."""

from __future__ import annotations

import sqlite3

import pandas as pd

from services.kr_market_realtime_price_cache import (
    load_cached_realtime_prices,
    save_realtime_prices_to_cache,
)
from services.kr_market_realtime_price_service import normalize_unique_tickers
from services.kr_market_data_cache_prices import (
    _deserialize_latest_vcp_price_map,
    _serialize_latest_vcp_price_map,
)
from services.kr_market_backtest_scenario_helpers import build_latest_price_map
from services.kr_market_backtest_trade_helpers import build_cumulative_trade_record
from services.kr_market_csv_utils import (
    build_latest_close_map_from_prices_df,
    get_ticker_padded_series,
)


def test_csv_ticker_series_canonicalizes_numeric_mixed_and_missing_values():
    """CSV의 숫자 float·혼합 코드·결측이 같은 가격 키 규칙을 사용해야 한다."""
    price_df = pd.DataFrame(
        {
            "ticker": [5930.0, "0007c0", "A005930", "005930.KS", 0, "20260211"],
        }
    )

    result = get_ticker_padded_series(price_df)

    assert result.tolist() == ["005930", "0007C0", "005930", "005930", "", ""]
    assert price_df["_ticker_padded"].tolist() == result.tolist()


def test_normalize_unique_tickers_excludes_empty_values_from_fast_path():
    """빈 값은 이미 정규화됐다고 오인해 네트워크 가격 요청 키가 되면 안 된다."""
    assert normalize_unique_tickers(["", "0007C0"]) == ["0007C0"]


def test_latest_price_maps_skip_invalid_tickers_and_merge_canonical_spellings():
    """날짜·0 키는 버리고 별칭 행은 마지막 종가를 하나의 정규 키로 합쳐야 한다."""
    price_df = pd.DataFrame(
        [
            {"ticker": "005930", "date": "2026-02-20", "close": 100.0},
            {"ticker": "A005930", "date": "2026-02-22", "close": 120.0},
            {"ticker": "0007c0", "date": "2026-02-21", "close": 85.0},
            {"ticker": "20260211", "date": "2026-02-23", "close": 999.0},
            {"ticker": 0, "date": "2026-02-24", "close": 777.0},
        ]
    )

    assert build_latest_close_map_from_prices_df(price_df) == {"005930": 120.0, "0007C0": 85.0}
    assert build_latest_price_map(price_df) == {"005930": 120.0, "0007C0": 85.0}


def test_cumulative_trade_uses_canonical_ticker_for_prebuilt_price_index():
    """접두사가 있는 시그널도 정규 가격 인덱스를 찾아 거래 결과를 만든다."""
    prices = pd.DataFrame(
        [{"high": 106.0, "low": 99.0, "close": 105.0}],
        index=pd.to_datetime(["2026-02-21"]),
    )

    trade = build_cumulative_trade_record(
        signal={"ticker": "A005930", "entry_price": 100.0, "grade": "S"},
        stats_date="2026-02-20",
        price_df=pd.DataFrame(),
        price_index={"005930": prices},
    )

    assert trade is not None
    assert trade["code"] == "005930"
    assert trade["outcome"] == "WIN"


def test_realtime_sqlite_cache_resolves_legacy_ticker_with_newest_timestamp(tmp_path):
    """기존 소문자·미패딩 SQLite 키도 정규 요청에 맞추되 최신 행을 선택해야 한다."""
    get_data_path = lambda filename: str(tmp_path / filename)
    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="exact",
        get_data_path=get_data_path,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE realtime_price_cache SET updated_at = ? WHERE ticker = ?",
            ("2026-02-21T09:00:00", "005930"),
        )
        conn.execute(
            "INSERT INTO realtime_price_cache (ticker, price, source, updated_at) VALUES (?, ?, ?, ?)",
            ("5930", 120.0, "legacy", "2026-02-21T10:00:00"),
        )
        conn.execute(
            "INSERT INTO realtime_price_cache (ticker, price, source, updated_at) VALUES (?, ?, ?, ?)",
            ("20260211", 999.0, "invalid", "2026-02-21T11:00:00"),
        )
        conn.commit()

    prices = load_cached_realtime_prices(
        ["A005930", "20260211"],
        get_data_path=get_data_path,
        max_age_seconds=31_536_000,
    )

    assert prices == {"005930": 120.0}


def test_realtime_sqlite_cache_resolves_lowercase_mixed_ticker(tmp_path):
    """대소문자가 다른 구형 혼합 티커도 원본 데이터베이스를 고치지 않고 읽는다."""
    get_data_path = lambda filename: str(tmp_path / filename)
    save_realtime_prices_to_cache(
        {"0007C0": 80.0},
        source="exact",
        get_data_path=get_data_path,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE realtime_price_cache SET updated_at = ? WHERE ticker = ?",
            ("2026-02-21T09:00:00", "0007C0"),
        )
        conn.execute(
            "INSERT INTO realtime_price_cache (ticker, price, source, updated_at) VALUES (?, ?, ?, ?)",
            ("0007c0", 85.0, "legacy", "2026-02-21T10:00:00"),
        )
        conn.commit()

    prices = load_cached_realtime_prices(
        ["0007C0"],
        get_data_path=get_data_path,
        max_age_seconds=31_536_000,
    )

    assert prices == {"0007C0": 85.0}


def test_realtime_sqlite_cache_prefers_raw_canonical_key_on_equal_timestamp(tmp_path):
    """공백을 뺀 별칭은 같은 시각이라도 원본 canonical 키보다 우선하면 안 된다."""
    get_data_path = lambda filename: str(tmp_path / filename)
    save_realtime_prices_to_cache(
        {"005930": 100.0},
        source="exact",
        get_data_path=get_data_path,
    )

    db_path = tmp_path / "runtime_cache.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE realtime_price_cache SET updated_at = ? WHERE ticker = ?",
            ("2026-02-21T10:00:00", "005930"),
        )
        conn.execute(
            "INSERT INTO realtime_price_cache (ticker, price, source, updated_at) VALUES (?, ?, ?, ?)",
            (" 005930 ", 120.0, "legacy", "2026-02-21T10:00:00"),
        )
        conn.commit()

    prices = load_cached_realtime_prices(
        ["005930"],
        get_data_path=get_data_path,
        max_age_seconds=31_536_000,
    )

    assert prices == {"005930": 100.0}


def test_latest_vcp_price_map_collision_prefers_canonical_then_lexical_key():
    """JSON 캐시는 timestamp가 없으므로 삽입 순서 대신 정해진 키 우선순위가 필요하다."""
    serialized = _serialize_latest_vcp_price_map(
        {"005930": 100.0, "A005930": 130.0, "005930.KS": 110.0}
    )
    deserialized = _deserialize_latest_vcp_price_map(
        {"rows": {"A005930": 130.0, "005930.KS": 110.0}}
    )

    assert serialized == {"rows": {"005930": 100.0}}
    assert deserialized == {"005930": 110.0}


def test_latest_vcp_price_map_does_not_treat_whitespace_alias_as_canonical():
    """공백 별칭이 lexical 순서로 먼저 와도 실제 canonical 표기가 이겨야 한다."""
    serialized = _serialize_latest_vcp_price_map(
        {" 005930 ": 120.0, "005930": 100.0}
    )

    assert serialized == {"rows": {"005930": 100.0}}
