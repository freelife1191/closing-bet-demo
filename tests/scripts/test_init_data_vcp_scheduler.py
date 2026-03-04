#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_data 스케줄러 회귀 테스트
"""

import os
import sys
from typing import Dict
import json
import datetime
import types

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts import init_data


class _DummyScreener:
    """create_signals_log 테스트용 스크리너 더미"""

    last_max_stocks: int | None = None

    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
        self.__class__.last_max_stocks = max_stocks
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "score": 65.0,  # B등급 경계
                    "market": "KOSPI",
                    "entry_price": 70000,
                    "contraction_ratio": 0.62,
                    "foreign_net_5d": 123456789,
                    "inst_net_5d": 234567890,
                    "foreign_net_1d": 11111111,
                    "inst_net_1d": 22222222,
                    "vcp_score": 8,
                }
            ]
        )


class _DummyMarketGate:
    """VCP 결과 파일 저장 시 사용되는 MarketGate 더미"""

    def analyze(self) -> Dict:
        return {"status": "중립", "is_gate_open": True}


class _FailingScreener:
    """VCP 분석 예외 상황 재현용 스크리너"""

    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
        raise RuntimeError("forced failure")


class _VcpGateScreener:
    """VCP 게이트 테스트용 스크리너"""

    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
        _ = max_stocks
        return pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "name": "삼성전자",
                    "score": 80.0,
                    "market": "KOSPI",
                    "entry_price": 70000,
                    "contraction_ratio": 0.95,
                    "foreign_net_5d": 100,
                    "inst_net_5d": 200,
                    "foreign_net_1d": 10,
                    "inst_net_1d": 20,
                    "vcp_score": 4,
                    "is_vcp": False,
                },
                {
                    "ticker": "000660",
                    "name": "SK하이닉스",
                    "score": 81.0,
                    "market": "KOSPI",
                    "entry_price": 120000,
                    "contraction_ratio": 0.68,
                    "foreign_net_5d": 110,
                    "inst_net_5d": 210,
                    "foreign_net_1d": 11,
                    "inst_net_1d": 21,
                    "vcp_score": 6,
                    "is_vcp": False,
                },
                {
                    "ticker": "035420",
                    "name": "NAVER",
                    "score": 82.0,
                    "market": "KOSPI",
                    "entry_price": 180000,
                    "contraction_ratio": 0.72,
                    "foreign_net_5d": 120,
                    "inst_net_5d": 220,
                    "foreign_net_1d": 12,
                    "inst_net_1d": 22,
                    "vcp_score": 1,
                    "is_vcp": True,
                },
            ]
        )


class _DummyMessenger:
    """알림 호출 여부 검증용 Messenger 더미"""

    instances = []

    def __init__(self):
        self.sent_results = []
        self.sent_custom_messages = []
        self.__class__.instances.append(self)

    def send_screener_result(self, result) -> None:
        self.sent_results.append(result)

    def send_custom_message(self, title: str, message: str, channels=None) -> None:
        self.sent_custom_messages.append(
            {"title": title, "message": message, "channels": channels}
        )


def test_create_signals_log_persists_detected_signal(monkeypatch, tmp_path):
    """VCP 결과 1건이 감지되면 signals_log.csv에 실제로 저장되어야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    result = init_data.create_signals_log(target_date="2026-02-19", run_ai=False)

    assert result is True

    output_path = data_dir / "signals_log.csv"
    assert output_path.exists()

    df = pd.read_csv(output_path, dtype={"ticker": str})
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "005930"
    assert df.iloc[0]["grade"] == "B"


def test_create_signals_log_passes_max_stocks(monkeypatch, tmp_path):
    """create_signals_log의 max_stocks 인자가 screener.run_screening으로 전달되어야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    _DummyScreener.last_max_stocks = None

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    result = init_data.create_signals_log(target_date="2026-02-19", run_ai=False, max_stocks=123)

    assert result is True
    assert _DummyScreener.last_max_stocks == 123


def test_send_jongga_notification_sends_message_when_no_signals(monkeypatch, tmp_path):
    """신호가 0건이어도 실행 결과 메시지는 발송되어야 한다."""
    _DummyMessenger.instances = []

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "date": "2026-02-19",
        "signals": [],
        "by_grade": {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0},
        "by_market": {},
    }
    with open(data_dir / "jongga_v2_latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.messenger.Messenger", _DummyMessenger)

    init_data.send_jongga_notification()

    assert _DummyMessenger.instances, "Messenger 인스턴스가 생성되어야 합니다."
    messenger = _DummyMessenger.instances[-1]
    assert len(messenger.sent_custom_messages) == 1
    assert "신호 없음" in messenger.sent_custom_messages[0]["title"]


def test_create_signals_log_returns_false_on_exception(monkeypatch, tmp_path):
    """VCP 내부 예외 시 create_signals_log은 실패(False)를 반환해야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _FailingScreener)

    result = init_data.create_signals_log(target_date="2026-02-19", run_ai=False)

    assert result is False


def test_create_signals_log_applies_vcp_gate_filter(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _VcpGateScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    result = init_data.create_signals_log(target_date="2026-03-04", run_ai=False)

    assert result is True

    df = pd.read_csv(data_dir / "signals_log.csv", dtype={"ticker": str})
    tickers = set(df["ticker"].astype(str).str.zfill(6).tolist())
    assert "005930" not in tickers
    assert "000660" in tickers
    assert "035420" in tickers


def test_should_abort_daily_pykrx_bulk_fetch_detects_known_error_signature():
    known_error = KeyError(
        "None of [Index(['시가', '고가', '저가', '종가'], dtype='object')] are in the [columns]"
    )
    unknown_error = RuntimeError("temporary failure")

    assert init_data._should_abort_daily_pykrx_bulk_fetch(known_error) is True
    assert init_data._should_abort_daily_pykrx_bulk_fetch(unknown_error) is False


def test_create_daily_prices_switches_to_yfinance_on_known_pykrx_error(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260304", datetime.datetime(2026, 3, 4)),
    )

    class _FailingStock:
        @staticmethod
        def get_market_ohlcv(*_args, **_kwargs):
            raise KeyError(
                "None of [Index(['시가', '고가', '저가', '종가'], dtype='object')] are in the [columns]"
            )

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _FailingStock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)

    logs: list[tuple[str, str]] = []
    monkeypatch.setattr(init_data, "log", lambda message, level="INFO": logs.append((level, str(message))))

    fallback_calls = {"count": 0}

    def _fake_fallback(*_args, **_kwargs):
        fallback_calls["count"] += 1
        return True

    monkeypatch.setattr(init_data, "fetch_prices_yfinance", _fake_fallback)

    result = init_data.create_daily_prices(target_date="2026-03-04", force=True, lookback_days=1)

    assert result is True
    assert fallback_calls["count"] == 1
    assert any("yfinance 폴백으로 전환" in message for _, message in logs)
    assert not any("날짜별 수집 실패" in message for _, message in logs)


def test_extract_yfinance_ohlcv_handles_price_first_multiindex():
    index = pd.DatetimeIndex(
        [datetime.datetime(2026, 3, 3), datetime.datetime(2026, 3, 4)], name="Date"
    )
    columns = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["005930.KS"]]
    )
    values = [
        [10, 12],
        [11, 13],
        [9, 11],
        [10.5, 12.5],
        [1000, 1200],
    ]
    raw_df = pd.DataFrame(
        [list(row) for row in zip(*values)],
        index=index,
        columns=columns,
    )

    normalized = init_data._extract_yfinance_ohlcv(raw_df, "005930.KS")

    assert list(normalized.columns) == ["open", "high", "low", "close", "volume"]
    assert len(normalized) == 2
    assert int(normalized.iloc[0]["open"]) == 10


def test_fetch_prices_yfinance_uses_chunked_download_with_timeout(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    stocks_df = pd.DataFrame(
        [
            {"ticker": "005930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSPI"},
            {"ticker": "035420", "market": "KOSPI"},
            {"ticker": "247540", "market": "KOSDAQ"},
            {"ticker": "086520", "market": "KOSDAQ"},
        ]
    )
    stocks_df.to_csv(data_dir / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    calls = []

    def _fake_download(symbols, **kwargs):
        symbols_list = [symbols] if isinstance(symbols, str) else list(symbols)
        calls.append({"symbols": symbols_list, "kwargs": kwargs})

        index = pd.DatetimeIndex(
            [datetime.datetime(2026, 3, 3), datetime.datetime(2026, 3, 4)], name="Date"
        )
        per_symbol = {}
        for symbol in symbols_list:
            per_symbol[symbol] = pd.DataFrame(
                {
                    "Open": [100, 101],
                    "High": [102, 103],
                    "Low": [99, 100],
                    "Close": [101, 102],
                    "Volume": [1000, 1100],
                },
                index=index,
            )

        if len(symbols_list) == 1:
            return per_symbol[symbols_list[0]]
        return pd.concat(per_symbol, axis=1)

    fake_yf = types.ModuleType("yfinance")
    fake_yf.download = _fake_download
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))

    output_file = data_dir / "daily_prices.csv"
    result = init_data.fetch_prices_yfinance(
        datetime.datetime(2026, 3, 2),
        datetime.datetime(2026, 3, 4),
        pd.DataFrame(),
        str(output_file),
        chunk_size=2,
        request_timeout=3,
        use_threads=False,
    )

    assert result is True
    assert len(calls) == 3
    assert all(len(call["symbols"]) <= 2 for call in calls)
    assert all(call["kwargs"]["timeout"] == 3 for call in calls)

    saved = pd.read_csv(output_file, dtype={"ticker": str})
    assert set(saved["ticker"].unique()) == {"005930", "000660", "035420", "247540", "086520"}


def test_fetch_prices_yfinance_aborts_on_max_runtime(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    stocks_df = pd.DataFrame(
        [
            {"ticker": "005930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSPI"},
            {"ticker": "035420", "market": "KOSPI"},
        ]
    )
    stocks_df.to_csv(data_dir / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    calls = []

    def _fake_download(symbols, **_kwargs):
        symbols_list = [symbols] if isinstance(symbols, str) else list(symbols)
        calls.append(symbols_list)
        index = pd.DatetimeIndex([datetime.datetime(2026, 3, 4)], name="Date")
        if len(symbols_list) == 1:
            return pd.DataFrame(
                {
                    "Open": [100],
                    "High": [101],
                    "Low": [99],
                    "Close": [100],
                    "Volume": [1000],
                },
                index=index,
            )
        return pd.concat(
            {
                symbol: pd.DataFrame(
                    {
                        "Open": [100],
                        "High": [101],
                        "Low": [99],
                        "Close": [100],
                        "Volume": [1000],
                    },
                    index=index,
                )
                for symbol in symbols_list
            },
            axis=1,
        )

    fake_yf = types.ModuleType("yfinance")
    fake_yf.download = _fake_download
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))

    tick = {"value": 0.0}

    def _fake_time():
        tick["value"] += 2.0
        return tick["value"]

    monkeypatch.setattr(init_data.time, "time", _fake_time)

    result = init_data.fetch_prices_yfinance(
        datetime.datetime(2026, 3, 2),
        datetime.datetime(2026, 3, 4),
        pd.DataFrame(),
        str(data_dir / "daily_prices.csv"),
        chunk_size=1,
        request_timeout=3,
        use_threads=False,
        max_runtime_seconds=3,
    )

    assert result is False
    assert len(calls) == 1


def test_create_institutional_trend_returns_false_when_latest_date_is_stale(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    stocks_df = pd.DataFrame(
        [
            {"ticker": "005930", "market": "KOSPI"},
            {"ticker": "000660", "market": "KOSPI"},
        ]
    )
    stocks_df.to_csv(data_dir / "korean_stocks_list.csv", index=False, encoding="utf-8-sig")

    stale_df = pd.DataFrame(
        [
            {"date": "2026-02-27", "ticker": "005930", "foreign_buy": 100, "inst_buy": 200},
            {"date": "2026-02-27", "ticker": "000660", "foreign_buy": 120, "inst_buy": 220},
        ]
    )
    stale_df.to_csv(
        data_dir / "all_institutional_trend_data.csv",
        index=False,
        encoding="utf-8-sig",
    )

    class _EmptyStock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(*_args, **_kwargs):
            return pd.DataFrame()

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _EmptyStock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260304", datetime.datetime(2026, 3, 4)),
    )

    result = init_data.create_institutional_trend(
        target_date="2026-03-04",
        force=True,
        lookback_days=1,
    )

    assert result is False
