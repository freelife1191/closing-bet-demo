#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init_data 스케줄러 회귀 테스트
"""

import os
import sys
from typing import Dict
import json

import pandas as pd


sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from scripts import init_data


class _DummyScreener:
    """create_signals_log 테스트용 스크리너 더미"""

    def __init__(self, target_date=None):
        self.target_date = target_date

    def run_screening(self, max_stocks: int = 600) -> pd.DataFrame:
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
