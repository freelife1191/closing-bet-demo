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
import pytest


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
                    "is_vcp": True,
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


class _EmptyScreener:
    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
        _ = max_stocks
        return pd.DataFrame()


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
    assert df.iloc[0]["foreign_1d"] == 11_111_111
    assert df.iloc[0]["inst_1d"] == 22_222_222
    # [VCP-050] 결측이 없으면 5일 값은 정수 표기 그대로다(기존 행이 `123.0` 으로 바뀌지 않게)
    assert ",123456789,234567890," in output_path.read_text(encoding="utf-8-sig")


class _MissingSupplyScreener(_DummyScreener):
    """[VCP-050] 수급 결측 종목(None)과 실제 순매수 0 종목을 함께 돌려준다."""

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
        base = super().run_screening(max_stocks).iloc[0].to_dict()
        missing = {**base, "foreign_net_5d": None, "inst_net_5d": None, "foreign_net_1d": None, "inst_net_1d": None}
        zero = {**base, "ticker": "000660", "foreign_net_5d": 0, "inst_net_5d": 0}
        return pd.DataFrame([missing, zero])


def test_create_signals_log_keeps_missing_supply_blank(monkeypatch, tmp_path):
    """[VCP-050] 결측은 빈 칸, 실제 0 은 0 으로 저장한다. 예전에는 둘 다 0 이었다."""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _MissingSupplyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is True

    df = pd.read_csv(tmp_path / "data" / "signals_log.csv", dtype={"ticker": str}).set_index("ticker")
    assert df.loc["005930", ["foreign_5d", "inst_5d", "foreign_1d", "inst_1d"]].isna().all()
    assert df.loc["000660", "foreign_5d"] == 0
    assert df.loc["000660", "inst_5d"] == 0


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


def test_send_jongga_notification_skips_duplicate_payload(monkeypatch, tmp_path):
    """동일 종가베팅 결과 payload는 스케줄러가 재호출되어도 한 번만 발송되어야 한다."""
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
    init_data.send_jongga_notification()

    sent_messages = [
        message
        for messenger in _DummyMessenger.instances
        for message in messenger.sent_custom_messages
    ]
    assert len(sent_messages) == 1


def test_send_jongga_notification_skips_duplicate_signal_payload(monkeypatch, tmp_path):
    """신호가 있는 동일 종가베팅 결과도 한 번만 send_screener_result로 전달되어야 한다."""
    _DummyMessenger.instances = []

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "date": "2026-02-19",
        "signals": [
            {
                "stock_code": "005930",
                "stock_name": "삼성전자",
                "market": "KOSPI",
                "sector": "반도체",
                "signal_date": "2026-02-19",
                "grade": "S",
                "status": "PENDING",
                "score": {"total": 92, "volume": 20, "chart": 18},
                "checklist": {"has_news": True, "supply_positive": True},
                "current_price": 70000,
                "entry_price": 70500,
                "stop_price": 68000,
                "target_price": 76000,
                "trading_value": 1_200_000_000_000,
                "change_pct": 8.2,
                "volume_ratio": 4.1,
                "created_at": "2026-02-19T16:10:00",
            }
        ],
        "by_grade": {"S": 1},
        "by_market": {"KOSPI": 1},
    }
    with open(data_dir / "jongga_v2_latest.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.messenger.Messenger", _DummyMessenger)

    init_data.send_jongga_notification()
    init_data.send_jongga_notification()

    sent_results = [
        result
        for messenger in _DummyMessenger.instances
        for result in messenger.sent_results
    ]
    assert len(sent_results) == 1
    assert sent_results[0].signals[0].stock_code == "005930"


def test_send_jongga_notification_skips_changed_signal_payload_same_date(monkeypatch, tmp_path):
    """같은 기준일 결과가 재생성되어 가격/점수가 바뀌어도 메일은 한 번만 발송되어야 한다."""
    _DummyMessenger.instances = []

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    def _write_payload(current_price: int, score_total: int) -> None:
        payload = {
            "date": "2026-05-26",
            "signals": [
                {
                    "stock_code": "005930",
                    "stock_name": "삼성전자",
                    "market": "KOSPI",
                    "sector": "반도체",
                    "signal_date": "2026-05-26",
                    "grade": "S",
                    "status": "PENDING",
                    "score": {"total": score_total, "volume": 20, "chart": 18},
                    "checklist": {"has_news": True, "supply_positive": True},
                    "current_price": current_price,
                    "entry_price": current_price + 500,
                    "stop_price": current_price - 2000,
                    "target_price": current_price + 6000,
                    "trading_value": 1_200_000_000_000,
                    "change_pct": 8.2,
                    "volume_ratio": 4.1,
                    "created_at": "2026-05-26T17:07:00",
                }
            ],
            "by_grade": {"S": 1},
            "by_market": {"KOSPI": 1},
        }
        with open(data_dir / "jongga_v2_latest.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.messenger.Messenger", _DummyMessenger)

    _write_payload(current_price=70000, score_total=92)
    init_data.send_jongga_notification()
    _write_payload(current_price=70100, score_total=93)
    init_data.send_jongga_notification()

    sent_results = [
        result
        for messenger in _DummyMessenger.instances
        for result in messenger.sent_results
    ]
    assert len(sent_results) == 1
    assert sent_results[0].signals[0].current_price == 70000


def test_create_signals_log_returns_false_on_exception(monkeypatch, tmp_path):
    """VCP 내부 예외 시 create_signals_log은 실패(False)를 반환해야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _FailingScreener)

    result = init_data.create_signals_log(target_date="2026-02-19", run_ai=False)

    assert result is False


def test_create_signals_log_keeps_existing_log_on_exception(monkeypatch, tmp_path):
    """[VCP-028] 예외로 끝나도 그동안 쌓인 signals_log.csv 는 그대로 남아야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    seeded = pd.DataFrame(
        [
            {"ticker": "005930", "signal_date": "2026-09-19", "status": "OPEN", "score": 80, "is_vcp": True},
            {"ticker": "000660", "signal_date": "2026-09-21", "status": "OPEN", "score": 81, "is_vcp": True},
        ]
    )
    seeded.to_csv(data_dir / "signals_log.csv", index=False)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _FailingScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    log_df = pd.read_csv(data_dir / "signals_log.csv", dtype={"ticker": str})
    assert log_df["signal_date"].tolist() == ["2026-09-19", "2026-09-21"]
    assert log_df.columns.tolist() == seeded.columns.tolist()


def test_create_signals_log_creates_full_column_log_on_exception_without_file(monkeypatch, tmp_path):
    """[VCP-028] 파일이 없을 때의 빈 로그는 정상 갈래와 같은 열 목록이어야 한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _FailingScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    log_df = pd.read_csv(data_dir / "signals_log.csv")
    assert log_df.empty
    assert len(log_df.columns) == 23
    assert {"is_vcp", "vcp_score", "hold_days"} <= set(log_df.columns)


def test_create_signals_log_persists_only_vcp_screening_results(monkeypatch, tmp_path):
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
    assert "000660" not in tickers
    assert "035420" in tickers


def test_create_signals_log_writes_latest_metadata_when_no_signals(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"ticker": "005930", "signal_date": "2026-03-05", "score": 80},
            {"ticker": "000660", "signal_date": "2026-03-06", "score": 81},
        ]
    ).to_csv(data_dir / "signals_log.csv", index=False)

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _EmptyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    result = init_data.create_signals_log(target_date="2026-03-06", run_ai=False)

    assert result is True

    latest_payload = json.loads((data_dir / "vcp_signals_latest.json").read_text(encoding="utf-8"))
    assert latest_payload["date"] == "2026-03-06"
    assert latest_payload["signals"] == []
    assert latest_payload["total_candidates"] == 0

    log_df = pd.read_csv(data_dir / "signals_log.csv", dtype={"ticker": str})
    assert log_df["signal_date"].tolist() == ["2026-03-05"]


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


def _krx_ohlcv_frame(rows: Dict[str, tuple]) -> pd.DataFrame:
    """pykrx get_market_ohlcv(date, market="ALL") 모양. rows: {티커: (시가, 고가, 저가, 종가)}"""
    records = [
        {"시가": o, "고가": h, "저가": lo, "종가": c, "거래량": 100 if c else 0, "거래대금": c * 100}
        for o, h, lo, c in rows.values()
    ]
    return pd.DataFrame(records, index=pd.Index(list(rows), name="티커"))


def _run_daily_prices_with_fake_krx(monkeypatch, tmp_path, target, frames, existing_rows, on_fetch=None):
    """기존 파일과 날짜별 가짜 pykrx 응답으로 create_daily_prices 를 돌린다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "daily_prices.csv"
    pd.DataFrame(
        existing_rows,
        columns=["date", "ticker", "open", "high", "low", "close", "volume", "trading_value"],
    ).to_csv(file_path, index=False)

    target_dt = datetime.datetime.strptime(target, "%Y-%m-%d")
    monkeypatch.setattr(init_data.shared_state, "STOP_REQUESTED", False)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: (target_dt.strftime("%Y%m%d"), target_dt),
    )

    class _FakeStock:
        @staticmethod
        def get_market_ohlcv(date_str, *_args, **_kwargs):
            if on_fetch:
                on_fetch(date_str)
            return frames.get(date_str, pd.DataFrame())

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _FakeStock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "log", lambda message, level="INFO": None)

    fallback_calls = {"count": 0}

    def _fake_fallback(*_args, **_kwargs):
        fallback_calls["count"] += 1
        return True

    monkeypatch.setattr(init_data, "fetch_prices_yfinance", _fake_fallback)

    result = init_data.create_daily_prices(target_date=target)
    saved = pd.read_csv(file_path, dtype={"ticker": str})
    return result, fallback_calls["count"], saved


_ZERO_DAY = {"000001": (0, 0, 0, 0), "000002": (0, 0, 0, 0)}


def test_create_daily_prices_skips_holiday_zero_close_but_keeps_suspended_ticker(monkeypatch, tmp_path):
    frames = {
        "20260922": _krx_ohlcv_frame(
            {"000001": (100, 110, 90, 105), "000002": (0, 0, 0, 1000), "000003": (0, 0, 0, 0)}
        ),
        "20260923": _krx_ohlcv_frame(_ZERO_DAY),
    }
    existing = [["2026-09-21", "000001", 100, 110, 90, 100, 100, 10000]]

    result, fallbacks, saved = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-23", frames, existing
    )

    assert result is True
    assert fallbacks == 0
    assert sorted(saved["date"].unique()) == ["2026-09-21", "2026-09-22"]
    day = saved[saved["date"] == "2026-09-22"].set_index("ticker")
    assert sorted(day.index) == ["000001", "000002", "000003"]
    assert day.loc["000003", "close"] == 0


def test_create_daily_prices_holiday_only_range_does_not_fall_back(monkeypatch, tmp_path):
    existing = [
        ["2026-09-23", "000001", 100, 110, 90, 105, 100, 10500],
        ["2026-09-23", "000002", 50, 55, 45, 52, 100, 5200],
    ]

    result, fallbacks, saved = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-24", {"20260924": _krx_ohlcv_frame(_ZERO_DAY)}, existing
    )

    assert result is True
    assert fallbacks == 0
    # 직전 거래일 행이 그대로 남고 휴장일 행은 생기지 않는다
    assert saved["date"].tolist() == ["2026-09-23", "2026-09-23"]
    assert saved["close"].tolist() == [105, 52]


def test_create_daily_prices_falls_back_when_holiday_mixes_with_empty_day(monkeypatch, tmp_path):
    existing = [["2026-09-22", "000001", 100, 110, 90, 105, 100, 10500]]
    frames = {"20260923": pd.DataFrame(), "20260924": _krx_ohlcv_frame(_ZERO_DAY)}

    result, fallbacks, _ = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-24", frames, existing
    )

    assert result is True
    assert fallbacks == 1


def test_create_daily_prices_falls_back_when_stopped_after_holiday(monkeypatch, tmp_path):
    # 휴장일 하나를 처리한 뒤 중단되면 뒤 평일을 보지 못했으므로 폴백 생략 대상이 아니다
    monkeypatch.setattr(init_data.shared_state, "STOP_REQUESTED", False)
    existing = [["2026-09-22", "000001", 100, 110, 90, 105, 100, 10500]]

    def _stop(_date_str):
        init_data.shared_state.STOP_REQUESTED = True

    _, fallbacks, _ = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-24", {"20260923": _krx_ohlcv_frame(_ZERO_DAY)}, existing, on_fetch=_stop
    )

    assert fallbacks == 1


def test_create_daily_prices_drops_stored_holiday_rows_on_next_save(monkeypatch, tmp_path):
    existing = [
        ["2026-09-21", "000001", 100, 110, 90, 100, 100, 10000],
        ["2026-09-22", "000001", 0, 0, 0, 0, 0, 0],
        ["2026-09-22", "000002", 0, 0, 0, 0, 0, 0],
    ]
    frames = {
        "20260922": _krx_ohlcv_frame(_ZERO_DAY),
        "20260923": _krx_ohlcv_frame({"000001": (100, 110, 90, 105), "000002": (50, 55, 45, 52)}),
    }
    fetched: list[str] = []

    result, fallbacks, saved = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-23", frames, existing, on_fetch=fetched.append
    )

    assert result is True
    assert fallbacks == 0
    assert sorted(saved["date"].unique()) == ["2026-09-21", "2026-09-23"]
    # 0원 날짜를 빼면 마지막 저장일이 09-21 로 돌아가 09-22 를 다시 조회한다
    assert fetched == ["20260922", "20260923"]


def test_create_daily_prices_handles_file_with_only_holiday_rows(monkeypatch, tmp_path):
    existing = [["2026-09-22", "000001", 0, 0, 0, 0, 0, 0]]
    fetched: list[str] = []
    frames = {"20260923": _krx_ohlcv_frame({"000001": (100, 110, 90, 105)})}

    result, fallbacks, saved = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-23", frames, existing, on_fetch=fetched.append
    )

    assert result is True
    assert fallbacks == 0
    assert saved["date"].tolist() == ["2026-09-23"]
    assert len(fetched) > 2  # 기존 자료가 없으므로 기본 90일 구간을 돈다


def test_create_daily_prices_keeps_rows_saved_by_overlapping_run(monkeypatch, tmp_path):
    # 수집하는 사이 다른 실행(스케줄러·Refresh VCP)이 저장한 행을 덮어 지우지 않는다([INFRA-091])
    existing = [["2026-09-21", "000001", 100, 110, 90, 100, 100, 10000]]
    frames = {"20260922": _krx_ohlcv_frame({"000001": (100, 110, 90, 105)})}
    file_path = tmp_path / "data" / "daily_prices.csv"

    def _other_run_saves(_date_str):
        other = pd.read_csv(file_path, dtype={"ticker": str})
        other.loc[len(other)] = ["2026-09-21", "000009", 10, 11, 9, 10, 1, 10]
        other.to_csv(file_path, index=False)

    result, _, saved = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-22", frames, existing, on_fetch=_other_run_saves
    )

    assert result is True
    assert sorted(zip(saved["date"], saved["ticker"])) == [
        ("2026-09-21", "000001"),
        ("2026-09-21", "000009"),
        ("2026-09-22", "000001"),
    ]


def test_create_daily_prices_keeps_existing_file_when_save_fails(monkeypatch, tmp_path):
    # 저장 도중 디스크 오류가 나도 기존 파일은 잘리지 않고 그대로 남는다([INFRA-091])
    existing = [["2026-09-21", "000001", 100, 110, 90, 100, 100, 10000]]
    frames = {"20260922": _krx_ohlcv_frame({"000001": (100, 110, 90, 105)})}
    file_path = tmp_path / "data" / "daily_prices.csv"
    before: dict[str, bytes] = {}

    def _disk_full(_fd):
        raise OSError(28, "No space left on device")

    def _capture(_date_str):
        before["bytes"] = file_path.read_bytes()
        monkeypatch.setattr(init_data.os, "fsync", _disk_full)

    result, fallbacks, _ = _run_daily_prices_with_fake_krx(
        monkeypatch, tmp_path, "2026-09-22", frames, existing, on_fetch=_capture
    )

    assert result is False
    assert fallbacks == 0  # 저장 실패를 yfinance 재수집으로 넘기지 않는다
    assert file_path.read_bytes() == before["bytes"]
    leftovers = [p.name for p in file_path.parent.iterdir() if p.name.startswith("daily_prices.csv.")]
    assert leftovers in ([], ["daily_prices.csv.lock"])


def test_all_zero_close_dates_handles_missing_columns():
    assert init_data._all_zero_close_dates(pd.DataFrame()) == []
    assert init_data._all_zero_close_dates(pd.DataFrame({"date": ["2026-09-22"], "open": [0]})) == []
    mixed = pd.DataFrame({"date": ["2026-09-22", "2026-09-22", "2026-09-23"], "close": [0, "x", 5]})
    assert init_data._all_zero_close_dates(mixed) == ["2026-09-22"]


def _fake_pykrx(monkeypatch, ohlcv):
    fake = types.ModuleType("pykrx")
    fake.stock = types.SimpleNamespace(get_index_ohlcv_by_date=ohlcv)
    monkeypatch.setitem(sys.modules, "pykrx", fake)


@pytest.mark.parametrize("fail", ["empty", "raise", "missing"])
def test_get_last_trading_date_warns_and_strict_raises_when_unconfirmed(monkeypatch, caplog, fail):
    # [INFRA-106] 지수 조회가 비거나 실패하거나 pykrx 가 없으면 WARNING 을 남기고 주말 처리 날짜를 돌려준다. strict 면 예외
    def _ohlcv(*_a, **_k):
        if fail == "raise":
            raise KeyError("지수명")
        return pd.DataFrame()

    if fail == "missing":
        monkeypatch.setitem(sys.modules, "pykrx", None)
    else:
        _fake_pykrx(monkeypatch, _ohlcv)
    ref = datetime.datetime(2026, 9, 27)  # 일요일 → 금요일 09-25

    with caplog.at_level("WARNING"):
        assert init_data.get_last_trading_date(reference_date=ref)[0] == "20260925"
    assert any(r.levelname == "WARNING" and "개장일 미확인" in r.getMessage() for r in caplog.records)
    with pytest.raises(RuntimeError):
        init_data.get_last_trading_date(reference_date=ref, strict=True)


def test_get_last_trading_date_strict_returns_confirmed_date(monkeypatch):
    # [INFRA-106] 지수로 확인되면 strict 여도 그 날짜를 돌려준다(추석 연휴 09-25 대신 09-24)
    _fake_pykrx(monkeypatch, lambda *_a, **_k: pd.DataFrame({"종가": [1.0]}, index=pd.DatetimeIndex(["2026-09-24"])))
    ref = datetime.datetime(2026, 9, 27)

    assert init_data.get_last_trading_date(reference_date=ref, strict=True)[0] == "20260924"


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

    class _EmptyTossCollector:
        def get_investor_trend(self, code, days=5):
            _ = code, days
            return {"details": []}

    fake_toss_module = types.ModuleType("engine.toss_collector")
    fake_toss_module.TossCollector = _EmptyTossCollector
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss_module)

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


def test_create_institutional_trend_uses_toss_backfill_when_pykrx_is_empty(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([{"ticker": "005930", "market": "KOSPI"}]).to_csv(
        data_dir / "korean_stocks_list.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [{"date": "2026-02-26", "ticker": "005930", "foreign_buy": 100, "inst_buy": 200}]
    ).to_csv(
        data_dir / "all_institutional_trend_data.csv",
        index=False,
        encoding="utf-8-sig",
    )

    class _EmptyStock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(*_args, **_kwargs):
            return pd.DataFrame()

    class _DummyTossCollector:
        def get_investor_trend(self, code, days=5):
            assert code == "005930"
            assert days == 5
            return {
                "foreign": 0,
                "institution": 0,
                "individual": 0,
                "days": 5,
                "details": [
                    {
                        "baseDate": "2026-03-06",
                        "close": 1000,
                        "netForeignerBuyVolume": 10,
                        "netInstitutionBuyVolume": 5,
                    },
                    {
                        "baseDate": "2026-03-05",
                        "close": 900,
                        "netForeignerBuyVolume": -2,
                        "netInstitutionBuyVolume": 4,
                    },
                ],
            }

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _EmptyStock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260306", datetime.datetime(2026, 3, 6)),
    )
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))

    fake_toss_module = types.ModuleType("engine.toss_collector")
    fake_toss_module.TossCollector = _DummyTossCollector
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss_module)

    result = init_data.create_institutional_trend(
        target_date="2026-03-06",
        force=True,
        lookback_days=1,
    )

    assert result is True

    updated = pd.read_csv(
        data_dir / "all_institutional_trend_data.csv",
        dtype={"ticker": str, "date": str},
    ).sort_values(["date", "ticker"])
    latest_rows = updated[updated["date"].isin(["2026-03-05", "2026-03-06"])]

    assert updated["date"].max() == "2026-03-06"
    assert latest_rows.to_dict("records") == [
        {
            "date": "2026-03-05",
            "ticker": "005930",
            "foreign_buy": -1800,
            "inst_buy": 3600,
            "source": "toss",
        },
        {
            "date": "2026-03-06",
            "ticker": "005930",
            "foreign_buy": 10000,
            "inst_buy": 5000,
            "source": "toss",
        },
    ]


def _run_trend_with_fake_krx(monkeypatch, tmp_path, on_fetch, toss_rows=None, frames=None):
    # 기존 파일(09-21)에 09-22 를 더하는 수급 수집 한 번. pykrx 가 빈 응답이면 Toss 백필로 간다
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [
            {"date": "2026-09-21", "ticker": t, "foreign_buy": 1, "inst_buy": 2}
            for t in ("000001", "069500")
        ]
    ).to_csv(file_path, index=False, encoding="utf-8-sig")

    class _Stock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(start, _end, _market, investor):
            if investor == "외국인":
                on_fetch()
            if frames is not None:
                return frames[investor]
            if toss_rows is not None:
                return pd.DataFrame()
            return pd.DataFrame({"순매수거래대금": [30, 40]}, index=["000001", "069500"])

    class _Toss:
        def get_investor_trend(self, code, days=5):
            return {"details": toss_rows if code == "000001" else []}

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _Stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    fake_toss = types.ModuleType("engine.toss_collector")
    fake_toss.TossCollector = _Toss
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260922", datetime.datetime(2026, 9, 22)),
    )
    result = init_data.create_institutional_trend(target_date="2026-09-22")
    return result, file_path


def _other_trend_run_saves(file_path):
    def _save():
        other = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
        other.loc[len(other)] = ["2026-09-21", "000009", 5, 6]
        other.to_csv(file_path, index=False)

    return _save


def test_create_institutional_trend_keeps_rows_saved_by_overlapping_run(monkeypatch, tmp_path):
    # 수집하는 사이 다른 실행이 저장한 수급 행을 덮어 지우지 않는다([INFRA-092])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"
    result, _ = _run_trend_with_fake_krx(monkeypatch, tmp_path, _other_trend_run_saves(file_path))

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert result is True
    assert sorted(zip(saved["date"], saved["ticker"])) == [
        ("2026-09-21", "000001"),
        ("2026-09-21", "000009"),
        ("2026-09-21", "069500"),
        ("2026-09-22", "000001"),
        ("2026-09-22", "069500"),
    ]


def test_toss_trend_backfill_keeps_rows_saved_by_overlapping_run(monkeypatch, tmp_path):
    # Toss 백필 경로도 잠금 안에서 파일을 다시 읽어 병합한다([INFRA-092])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"
    toss_rows = [
        {"baseDate": "2026-09-22", "close": 1000, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1}
    ]
    result, _ = _run_trend_with_fake_krx(
        monkeypatch, tmp_path, _other_trend_run_saves(file_path), toss_rows=toss_rows
    )

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert result is True
    assert ("2026-09-21", "000009") in set(zip(saved["date"], saved["ticker"]))
    assert ("2026-09-22", "000001") in set(zip(saved["date"], saved["ticker"]))


def test_toss_trend_backfill_does_not_overwrite_existing_rows(monkeypatch, tmp_path):
    # Toss 근사값은 빈 (date, ticker) 만 채우고 pykrx 로 저장된 값은 덮지 않는다([INFRA-093])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"

    def _other_run_saves_exact_value():
        other = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
        other.loc[len(other)] = ["2026-09-22", "000001", 30, 40]
        other.to_csv(file_path, index=False)

    toss_rows = [
        {"baseDate": d, "close": 1000, "netForeignerBuyVolume": 7, "netInstitutionBuyVolume": 9}
        for d in ("2026-09-22", "2026-09-21", "2026-09-18")
    ]
    result, _ = _run_trend_with_fake_krx(
        monkeypatch, tmp_path, _other_run_saves_exact_value, toss_rows=toss_rows
    )

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        (d, t): (f, i)
        for d, t, f, i in zip(saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"])
    }
    assert result is True
    assert values[("2026-09-21", "000001")] == (1, 2)
    assert values[("2026-09-22", "000001")] == (30, 40)
    assert values[("2026-09-18", "000001")] == (7000, 9000)


def _saved_rows_on(file_path, date):
    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    new = saved[saved["date"] == date]
    return list(zip(new["ticker"], new["foreign_buy"], new["inst_buy"]))


def test_create_institutional_trend_skips_tickers_missing_from_one_frame(monkeypatch, tmp_path):
    # [INFRA-095] 한쪽 프레임에만 있는 종목의 다른 쪽은 결측이다. 0 으로 저장하지 않는다
    frames = {
        "외국인": pd.DataFrame({"순매수거래대금": [30, 40]}, index=["000001", "069500"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50]}, index=["000001"]),
    }
    result, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)

    assert result is True
    assert _saved_rows_on(file_path, "2026-09-22") == [("000001", 30, 50)]


def test_create_institutional_trend_skips_nan_value_but_keeps_real_zero(monkeypatch, tmp_path):
    # [INFRA-095] 값이 빈 종목만 건너뛰고 그 날짜의 나머지는 저장한다. 실제 0 은 결측이 아니다
    frames = {
        "외국인": pd.DataFrame({"순매수거래대금": [0, float("nan")]}, index=["000001", "069500"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50, 60]}, index=["000001", "069500"]),
    }
    result, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)

    assert result is True
    assert _saved_rows_on(file_path, "2026-09-22") == [("000001", 0, 50)]


def test_create_institutional_trend_skips_date_without_value_column(monkeypatch, tmp_path):
    # [INFRA-095] 순매수거래대금 열이 없으면 그 날짜 전 종목이 0 이 되던 것을 저장하지 않는다
    frames = {
        "외국인": pd.DataFrame({"순매수거래량": [3]}, index=["000001"]),
        "기관합계": pd.DataFrame({"순매수거래대금": [50]}, index=["000001"]),
    }
    _, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)

    assert _saved_rows_on(file_path, "2026-09-22") == []


def test_create_institutional_trend_warns_when_one_frame_is_empty(monkeypatch, tmp_path):
    # [INFRA-095] 한쪽 조회만 비면 그 날짜는 저장되지 않는다. 휴장일 DEBUG 로 묻히지 않게 경고한다
    logged = []
    monkeypatch.setattr(init_data, "log", lambda message, level="INFO": logged.append((level, message)))
    frames = {
        "외국인": pd.DataFrame({"순매수거래대금": [30]}, index=["000001"]),
        "기관합계": pd.DataFrame(),
    }
    _, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)

    assert _saved_rows_on(file_path, "2026-09-22") == []
    assert any(level == "WARNING" and "2026-09-22" in message and "한쪽" in message for level, message in logged)


def test_create_institutional_trend_holiday_does_not_warn_one_frame_empty(monkeypatch, tmp_path):
    # 두 프레임이 모두 비면 휴장일이다. 한쪽 조회 실패 경고를 남기지 않는다([INFRA-095] 리뷰 low 2)
    logged = []
    monkeypatch.setattr(init_data, "log", lambda message, level="INFO": logged.append((level, message)))
    frames = {"외국인": pd.DataFrame(), "기관합계": pd.DataFrame()}
    _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, frames=frames)

    assert not any("한쪽" in message for _level, message in logged)


def test_toss_trend_backfill_reports_stale_when_latest_rows_are_all_missing(monkeypatch, tmp_path):
    # 최신일 행이 결측으로 모두 버려지면 과거 행만 채우고 성공으로 보고하지 않는다([INFRA-095] 심층 리뷰 M1)
    toss_rows = [
        {"baseDate": "2026-09-22", "close": None, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-18", "close": 1000, "netForeignerBuyVolume": 2, "netInstitutionBuyVolume": 3},
    ]
    result, file_path = _run_trend_with_fake_krx(monkeypatch, tmp_path, lambda: None, toss_rows=toss_rows)

    assert result is False
    assert _saved_rows_on(file_path, "2026-09-22") == []
    assert _saved_rows_on(file_path, "2026-09-18") == [("000001", 2000, 3000)]


def test_toss_trend_rows_drop_missing_fields_but_keep_real_zero(monkeypatch):
    # [INFRA-095] 빈 종가·순매수 수량을 0 으로 만들지 않는다. 실제 0 수량은 남긴다
    details = [
        {"baseDate": "2026-09-22", "close": 1000, "netForeignerBuyVolume": 0, "netInstitutionBuyVolume": 2},
        {"baseDate": "2026-09-21", "close": None, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-18", "close": "", "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-17", "close": 0, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-16", "close": 1000, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-15", "close": 1000, "netForeignerBuyVolume": "nan", "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-14", "close": 1000, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": ""},
        {"baseDate": "2026-09-11", "close": "inf", "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": 1},
        {"baseDate": "2026-09-10", "close": 1000, "netForeignerBuyVolume": 1, "netInstitutionBuyVolume": "nan"},
    ]

    class _Toss:
        def get_investor_trend(self, code, days=5):
            return {"details": details}

    fake_toss = types.ModuleType("engine.toss_collector")
    fake_toss.TossCollector = _Toss
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss)

    rows = init_data._collect_toss_trend_rows_for_ticker("1", datetime.datetime(2026, 9, 22))

    assert [(r["date"], r["ticker"], r["foreign_buy"], r["inst_buy"]) for r in rows] == [
        ("2026-09-22", "000001", 0, 2000)
    ]


def test_create_institutional_trend_refetches_approx_and_partial_dates_in_window(monkeypatch, tmp_path):
    # 창 안의 Toss 근사 날짜와 종목이 모자란 날짜는 pykrx 로 다시 받고, 나머지는 Skip 한다([INFRA-094])
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    rows = [
        ("2026-09-14", "000001", 1, 1, None),  # 창 밖 부분 날짜
        ("2026-09-17", "000001", 3, 4, None),  # 창 안 부분 날짜
        ("2026-09-18", "000001", 1, 2, None),
        ("2026-09-18", "069500", 1, 2, None),
        ("2026-09-21", "000001", 7000, 9000, "toss"),
        ("2026-09-21", "069500", 7000, 9000, "toss"),
        ("2026-09-22", "000001", 5, 6, None),
        ("2026-09-22", "069500", 5, 6, None),
    ]
    pd.DataFrame(rows, columns=["date", "ticker", "foreign_buy", "inst_buy", "source"]).to_csv(
        file_path, index=False, encoding="utf-8-sig"
    )
    called = []

    class _Stock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(start, _end, _market, investor):
            if investor == "외국인":
                called.append(start)
            value = 100 if investor == "외국인" else 200
            return pd.DataFrame({"순매수거래대금": [value, value]}, index=["000001", "069500"])

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _Stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260922", datetime.datetime(2026, 9, 22)),
    )

    result = init_data.create_institutional_trend(target_date="2026-09-22")

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        (d, t): (f, i, s)
        for d, t, f, i, s in zip(
            saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"], saved["source"].fillna("")
        )
    }
    assert result is True
    assert called == ["20260917", "20260921"]
    assert values[("2026-09-14", "000001")] == (1, 1, "")
    assert values[("2026-09-17", "000001")] == (100, 200, "")
    assert values[("2026-09-17", "069500")] == (100, 200, "")
    assert values[("2026-09-18", "000001")] == (1, 2, "")
    assert values[("2026-09-21", "000001")] == (100, 200, "")
    assert values[("2026-09-22", "069500")] == (5, 6, "")


def test_create_institutional_trend_backfills_latest_date_after_refetching_past_dates(monkeypatch, tmp_path):
    # 과거 근사 날짜는 pykrx 로 받았어도 최신일이 비었으면 Toss 백필로 채운다([INFRA-094] critic 지적 1)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [("2026-09-22", t, 7000, 9000, "toss") for t in ("000001", "069500")],
        columns=["date", "ticker", "foreign_buy", "inst_buy", "source"],
    ).to_csv(file_path, index=False, encoding="utf-8-sig")

    class _Stock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(start, _end, _market, _investor):
            if start == "20260923":
                return pd.DataFrame()
            return pd.DataFrame({"순매수거래대금": [100, 100]}, index=["000001", "069500"])

    class _Toss:
        def get_investor_trend(self, code, days=5):
            return {
                "details": [
                    {"baseDate": d, "close": 1000, "netForeignerBuyVolume": 7, "netInstitutionBuyVolume": 9}
                    for d in ("2026-09-23", "2026-09-22")
                ]
            }

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _Stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    fake_toss = types.ModuleType("engine.toss_collector")
    fake_toss.TossCollector = _Toss
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260923", datetime.datetime(2026, 9, 23)),
    )

    result = init_data.create_institutional_trend(target_date="2026-09-23")

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        (d, t): (f, i, s)
        for d, t, f, i, s in zip(
            saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"], saved["source"].fillna("")
        )
    }
    assert result is True
    assert values[("2026-09-22", "000001")] == (100, 100, "")
    assert values[("2026-09-23", "000001")] == (7000, 9000, "toss")


def test_create_institutional_trend_refetch_keeps_rows_missing_from_one_frame(monkeypatch, tmp_path):
    # 다시 받는 날짜에서 한쪽 프레임에 없는 종목은 0 으로 덮지 않고 기존 값을 둔다([INFRA-094] 심층 리뷰 M1)
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    pd.DataFrame(
        [("2026-09-22", t, 7000, 9000, "toss") for t in ("000001", "069500")],
        columns=["date", "ticker", "foreign_buy", "inst_buy", "source"],
    ).to_csv(file_path, index=False, encoding="utf-8-sig")

    class _Stock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(_start, _end, _market, investor):
            if investor == "외국인":
                return pd.DataFrame({"순매수거래대금": [100, 100]}, index=["000001", "069500"])
            return pd.DataFrame({"순매수거래대금": [200]}, index=["000001"])

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = _Stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: ("20260922", datetime.datetime(2026, 9, 22)),
    )

    result = init_data.create_institutional_trend(target_date="2026-09-22")

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    values = {
        t: (f, i, s)
        for t, f, i, s in zip(saved["ticker"], saved["foreign_buy"], saved["inst_buy"], saved["source"].fillna(""))
    }
    assert result is True
    assert values["000001"] == (100, 200, "")
    assert values["069500"] == (7000, 9000, "toss")


def _run_trend_refetch_case(monkeypatch, tmp_path, rows, stock, toss_calls, expected_date="2026-09-22"):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"ticker": "000001"}]).to_csv(data_dir / "korean_stocks_list.csv", index=False)
    file_path = data_dir / "all_institutional_trend_data.csv"
    pd.DataFrame(rows, columns=["date", "ticker", "foreign_buy", "inst_buy"]).to_csv(
        file_path, index=False, encoding="utf-8-sig"
    )

    class _TossMustNotRun:
        def get_investor_trend(self, code, days=5):
            toss_calls.append(code)  # 백필 쪽 예외 처리가 삼키므로 호출을 기록해 단언한다
            return {"details": []}

    fake_pykrx = types.ModuleType("pykrx")
    fake_pykrx.stock = stock
    monkeypatch.setitem(sys.modules, "pykrx", fake_pykrx)
    fake_toss = types.ModuleType("engine.toss_collector")
    fake_toss.TossCollector = _TossMustNotRun
    monkeypatch.setitem(sys.modules, "engine.toss_collector", fake_toss)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(init_data.time, "sleep", lambda _s: None)
    expected = datetime.datetime.strptime(expected_date, "%Y-%m-%d")
    monkeypatch.setattr(
        init_data,
        "get_last_trading_date",
        lambda reference_date=None: (expected.strftime("%Y%m%d"), expected),
    )
    return file_path, init_data.create_institutional_trend(target_date=expected_date)


def test_create_institutional_trend_refetch_without_source_column_keeps_file_on_empty_response(monkeypatch, tmp_path):
    # source 열이 없는 기존 파일도 행 수로 부분 날짜를 고르고, pykrx 가 또 비면 파일을 그대로 둔다([INFRA-094])
    called = []

    class _EmptyStock:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(start, _end, _market, _investor):
            called.append(start)
            return pd.DataFrame()

    monkeypatch.setattr(init_data, "shared_state", types.SimpleNamespace(STOP_REQUESTED=False))
    rows = [("2026-09-17", "000001", 3, 4)] + [("2026-09-22", t, 5, 6) for t in ("000001", "069500")]
    toss_calls = []
    file_path, result = _run_trend_refetch_case(monkeypatch, tmp_path, rows, _EmptyStock, toss_calls)
    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert result is True
    assert "20260917" in called
    assert sorted(zip(saved["date"], saved["ticker"], saved["foreign_buy"], saved["inst_buy"])) == sorted(rows)
    assert "source" not in saved.columns
    assert toss_calls == []


def test_create_institutional_trend_stop_request_skips_toss_backfill(monkeypatch, tmp_path):
    # 사용자 중단 뒤에는 최신일이 비어도 전 종목 Toss 백필을 시작하지 않고 False 로 끝난다([INFRA-094] 리뷰 지적 2)
    state = types.SimpleNamespace(STOP_REQUESTED=False)
    monkeypatch.setattr(init_data, "shared_state", state)

    class _StopAfterFirstDay:
        @staticmethod
        def get_market_net_purchases_of_equities_by_ticker(_start, _end, _market, _investor):
            state.STOP_REQUESTED = True
            return pd.DataFrame({"순매수거래대금": [100, 100]}, index=["000001", "069500"])

    rows = [("2026-09-18", t, 1, 2) for t in ("000001", "069500")]
    toss_calls = []
    file_path, result = _run_trend_refetch_case(monkeypatch, tmp_path, rows, _StopAfterFirstDay, toss_calls)

    saved = pd.read_csv(file_path, dtype={"ticker": str, "date": str})
    assert result is False
    assert saved["date"].max() == "2026-09-21"
    assert toss_calls == []


def test_create_institutional_trend_keeps_existing_file_when_save_fails(monkeypatch, tmp_path):
    # 저장 도중 디스크 오류가 나도 기존 수급 파일은 잘리지 않고 그대로 남는다([INFRA-092])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"
    before: dict[str, bytes] = {}

    def _disk_full(_fd):
        raise OSError(28, "No space left on device")

    def _capture():
        before["bytes"] = file_path.read_bytes()
        monkeypatch.setattr(init_data.os, "fsync", _disk_full)

    result, _ = _run_trend_with_fake_krx(monkeypatch, tmp_path, _capture)

    assert result is False
    assert file_path.read_bytes() == before["bytes"]
    leftovers = [p.name for p in file_path.parent.iterdir() if p.name.startswith(file_path.name + ".")]
    assert leftovers in ([], [file_path.name + ".lock"])


def test_create_institutional_trend_keeps_unreadable_file(monkeypatch, tmp_path):
    # 기존 파일을 읽지 못하면 새 행만으로 이력을 덮지 않고 파일을 그대로 둔다([INFRA-092])
    file_path = tmp_path / "data" / "all_institutional_trend_data.csv"
    before: dict[str, bytes] = {}

    def _corrupt():
        file_path.write_text("date,ticker,foreign_buy,inst_buy\n2026-09-21,000001,1,2\n2026-09-21,000002,1,2,3,4\n")
        before["bytes"] = file_path.read_bytes()

    result, _ = _run_trend_with_fake_krx(monkeypatch, tmp_path, _corrupt)

    assert result is False
    assert file_path.read_bytes() == before["bytes"]


def test_historical_vcp_analysis_keeps_latest_files(monkeypatch, tmp_path):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    for prefix in ['ai_analysis_results', 'kr_ai_analysis']:
        (data_dir / f'{prefix}.json').write_text('latest sentinel')
    monkeypatch.setattr(init_data, 'BASE_DIR', str(tmp_path))
    monkeypatch.setattr('engine.screener.SmartMoneyScreener', _DummyScreener)
    monkeypatch.setattr('engine.market_gate.MarketGate', _DummyMarketGate)
    class Analyzer:
        async def analyze_batch(self, signals):
            return {'005930': {'ticker': '005930', 'gemini_recommendation': {'action': 'HOLD', 'confidence': 75, 'reason': '실제 분석 경계 합성 응답'}}}
    class News:
        def __init__(self, *args):
            pass
        async def get_stock_news(self, *args, **kwargs):
            return []
    monkeypatch.setattr('engine.vcp_ai_analyzer.get_vcp_analyzer', Analyzer)
    monkeypatch.setattr('engine.collectors.EnhancedNewsCollector', News)
    monkeypatch.setattr('pykrx.stock.get_index_ohlcv', lambda *args: pd.DataFrame())
    assert init_data.create_signals_log('2026-02-19', run_ai=True) is True
    for prefix in ['ai_analysis_results', 'kr_ai_analysis']:
        assert (data_dir / f'{prefix}.json').read_text() == 'latest sentinel'
        assert json.loads((data_dir / f'{prefix}_20260219.json').read_text())['signals'][0]['gemini_recommendation']['confidence'] == 75


def test_vcp_no_provider_result_does_not_log_save_success(monkeypatch, tmp_path):
    (tmp_path/'data').mkdir()
    monkeypatch.setattr(init_data,'BASE_DIR',str(tmp_path))
    monkeypatch.setattr('engine.screener.SmartMoneyScreener',_DummyScreener)
    monkeypatch.setattr('engine.market_gate.MarketGate',_DummyMarketGate)
    class Analyzer:
        async def analyze_batch(self, stocks):
            return {'005930': {'ticker':'005930','gemini_recommendation':None}}
    class News:
        def __init__(self,*args): pass
        async def get_stock_news(self,*args,**kwargs): return []
    monkeypatch.setattr('engine.vcp_ai_analyzer.get_vcp_analyzer',Analyzer)
    monkeypatch.setattr('engine.collectors.EnhancedNewsCollector',News)
    monkeypatch.setattr('pykrx.stock.get_index_ohlcv',lambda *args:pd.DataFrame())
    logs=[]
    monkeypatch.setattr(init_data,'log',lambda message,level='INFO': logs.append((message,level)))
    assert init_data.create_signals_log('2026-02-19',run_ai=True) is True
    assert not any('분석 완료 및 저장' in message for message,level in logs)
    assert any('기존 캐시 유지' in message and level=='WARNING' for message,level in logs)
    assert not (tmp_path/'data/ai_analysis_results_20260219.json').exists()



def _run_vcp_collect_with(monkeypatch, tmp_path, results):
    """가짜 분석기가 주어진 결과를 돌려주는 VCP 수집을 돌리고 CSV 첫 행을 돌려준다."""
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    class Analyzer:
        async def analyze_batch(self, stocks):
            return results

    class News:
        def __init__(self, *args): pass
        async def get_stock_news(self, *args, **kwargs): return []

    monkeypatch.setattr("engine.vcp_ai_analyzer.get_vcp_analyzer", Analyzer)
    monkeypatch.setattr("engine.collectors.EnhancedNewsCollector", News)
    monkeypatch.setattr("pykrx.stock.get_index_ohlcv", lambda *args: pd.DataFrame())
    assert init_data.create_signals_log("2026-09-21", run_ai=True) is True
    return pd.read_csv(
        tmp_path / "data" / "signals_log.csv", dtype={"ticker": str}, keep_default_na=False
    ).iloc[0]


def test_create_signals_log_uses_gpt_verdict_when_gemini_is_missing(monkeypatch, tmp_path):
    """[VCP-040] Gemini 가 비고 GPT 가 성공하면 CSV 에 GPT 판정이 남는다."""
    gpt = {"action": "HOLD", "confidence": "72", "reason": "돌파 확인이 필요합니다."}
    row = _run_vcp_collect_with(
        monkeypatch, tmp_path,
        {"005930": {"gemini_recommendation": None, "gpt_recommendation": gpt}},
    )

    assert (row["ai_action"], int(row["ai_confidence"]), row["ai_reason"]) == (
        "HOLD", 72, "돌파 확인이 필요합니다.",
    )


def test_create_signals_log_leaves_confidence_blank_when_every_provider_failed(monkeypatch, tmp_path):
    """[VCP-040] 전부 실패하면 확신도는 0 이 아니라 결측이다."""
    row = _run_vcp_collect_with(
        monkeypatch, tmp_path,
        {"005930": {"gemini_recommendation": None, "gpt_recommendation": None}},
    )

    assert row["ai_reason"] == "분석 실패"
    assert row["ai_confidence"] == ""

# [VCP-029] 세 번째 줄의 열 수가 헤더와 달라 pd.read_csv 가 ParserError 를 낸다.
_RAGGED_LOG = (
    "ticker,signal_date,status,score,is_vcp\n"
    "005930,2026-09-19,OPEN,80,True\n"
    "000660,2026-09-21,OPEN,81,True,extra,extra,extra\n"
)


def test_create_signals_log_keeps_unreadable_log_when_merge_fails(monkeypatch, tmp_path):
    """[VCP-029] 기존 로그를 읽지 못해 병합에 실패하면 파일을 그대로 두고 실패를 돌려준다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    log_path.write_text(_RAGGED_LOG, encoding="utf-8")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    assert log_path.read_text(encoding="utf-8") == _RAGGED_LOG


def test_create_signals_log_keeps_unreadable_log_when_cleanup_fails(monkeypatch, tmp_path):
    """[VCP-029] 시그널이 없고 기존 로그를 읽지 못하면 빈 파일로 바꾸지 않고 실패를 돌려준다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    log_path.write_text(_RAGGED_LOG, encoding="utf-8")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _EmptyScreener)

    result = init_data.create_signals_log(target_date="2026-09-22", run_ai=False)

    assert result is False
    assert log_path.read_text(encoding="utf-8") == _RAGGED_LOG
    latest = json.loads((data_dir / "vcp_signals_latest.json").read_text(encoding="utf-8"))
    assert latest["date"] == "2026-09-22"
    assert latest["signals"] == []


def test_create_signals_log_recovers_from_empty_log_with_signals(monkeypatch, tmp_path):
    """[VCP-030] 0바이트 로그가 있어도 오늘 자 시그널을 저장한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_bytes(b"")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is True

    raw = (data_dir / "signals_log.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    df = pd.read_csv(data_dir / "signals_log.csv", dtype={"ticker": str})
    assert df["ticker"].tolist() == ["005930"]


def test_create_signals_log_recovers_from_empty_log_without_signals(monkeypatch, tmp_path):
    """[VCP-030] 0바이트 로그에서 시그널이 없으면 헤더만 있는 로그로 바꾸고 성공한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "signals_log.csv").write_bytes(b"")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _EmptyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-03-06", run_ai=False) is True

    df = pd.read_csv(data_dir / "signals_log.csv")
    assert df.empty
    assert "signal_date" in df.columns


@pytest.mark.parametrize("screener", [_DummyScreener, _EmptyScreener], ids=["merge", "cleanup"])
def test_create_signals_log_keeps_log_bytes_when_write_fails(monkeypatch, tmp_path, screener):
    """[VCP-030] 병합·당일 정리 쓰기가 도중에 실패해도 기존 로그가 잘리지 않는다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "signals_log.csv"
    pd.DataFrame(
        [{"ticker": "000660", "signal_date": "2026-02-18", "score": 70}]
    ).to_csv(log_path, index=False, encoding="utf-8-sig")
    before = log_path.read_bytes()

    def _failing_fsync(_fd):
        raise OSError("forced fsync failure")

    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", screener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)
    monkeypatch.setattr("services.kr_market_data_cache_core.os.fsync", _failing_fsync)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is False
    assert log_path.read_bytes() == before
    # signals_log.csv.lock 은 [VCP-035] 의 잠금 파일이라 계속 남는다. 임시 파일만 본다
    leftovers = [p.name for p in data_dir.iterdir() if p.name.startswith("signals_log.csv.")]
    assert [name for name in leftovers if name != "signals_log.csv.lock"] == []
