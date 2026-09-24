#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[VCP-035] signals_log.csv 를 쓰는 경로가 같은 파일 잠금을 지나는지 검사한다."""

import sys
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from engine.signal_tracker import SignalTracker
from scripts import init_data
from services import kr_market_vcp_reanalysis_service as reanalysis
from services.kr_market_vcp_reanalysis_service import signals_log_lock
from tests.scripts.test_init_data_vcp_scheduler import _DummyMarketGate, _DummyScreener


def _append_marker(path, ticker):
    frame = pd.read_csv(path, dtype={"ticker": str, "signal_date": str})
    marker = pd.DataFrame({"ticker": [ticker], "signal_date": ["2026-09-20"]})
    pd.concat([frame, marker], ignore_index=True).to_csv(path, index=False)


def _assert_waits_for_lock(signals_path, fn, while_locked=None):
    """잠금을 쥔 동안 fn 이 끝나지 않고, 풀면 끝나는지 본다.

    while_locked 는 잠금을 쥔 동안 본 스레드가 하는 쓰기다. fn 이 그 쓰기를 지우지 않았는지로
    fn 의 재읽기가 잠금 뒤에 일어났음을 확인한다.
    """
    errors = []

    def _run():
        try:
            fn()
        except Exception as error:  # 스레드 예외를 본 스레드로 옮긴다
            errors.append(error)

    with signals_log_lock(str(signals_path)):
        # daemon: 구현이 잠금을 중첩해 스스로 교착되면 pytest 가 멈추지 않고 실패하게 한다
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(0.3)
        assert worker.is_alive(), "잠금을 쥔 동안 쓰기가 끝났다"
        if while_locked is not None:
            while_locked()
    worker.join(5)
    assert not worker.is_alive()
    assert not errors, errors


def _tickers(path):
    return set(pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig")["ticker"])


def test_reanalysis_merge_refuses_rows_that_moved():
    """다시 읽은 파일의 같은 index 에 다른 종목이 있으면 덮지 않는다."""
    full = pd.DataFrame(
        {"ticker": ["000660", "005930"], "signal_date": ["2026-09-22", "2026-09-22"], "ai_action": ["", ""]}
    )
    updated = pd.DataFrame(
        {"ticker": ["005930"], "signal_date": ["2026-09-22"], "ai_action": ["BUY"]},
        index=[0],
    )
    with pytest.raises(ValueError, match="ticker"):
        reanalysis._merge_reanalysis_updates_into_full_signals_frame(
            updated_signals_df=updated,
            signals_path="signals_log.csv",
            load_csv_file=lambda *_a, **_k: full,
        )


def test_reanalysis_merge_applies_when_rows_match():
    """정수로 읽힌 티커(5930)도 같은 종목으로 본다."""
    full = pd.DataFrame({"ticker": [5930], "signal_date": ["2026-09-22"], "ai_action": [""]})
    updated = pd.DataFrame({"ticker": ["005930"], "signal_date": ["2026-09-22"], "ai_action": ["BUY"]})
    merged = reanalysis._merge_reanalysis_updates_into_full_signals_frame(
        updated_signals_df=updated,
        signals_path="signals_log.csv",
        load_csv_file=lambda *_a, **_k: full,
    )
    assert merged.loc[0, "ai_action"] == "BUY"


def test_reanalysis_write_keeps_leading_zero_of_ticker(tmp_path):
    """[VCP-042] 공유 로더가 티커를 정수(33530)로 읽어도 파일에는 033530 으로 쓴다."""
    path = tmp_path / "signals_log.csv"
    full = pd.DataFrame(
        {"ticker": pd.Series([33530, None], dtype=object), "signal_date": ["2026-09-22"] * 2, "ai_action": ["BUY"] * 2}
    )
    reanalysis.write_vcp_signals_csv_atomic(
        full.copy(),
        str(path),
        load_csv_file=lambda *_a, **_k: full,
        target_indexes=[],  # 갱신 0건이어도 파일 전체를 다시 쓴다
    )
    rows = path.read_text(encoding="utf-8-sig").splitlines()
    assert rows[1].startswith("033530,")
    assert rows[2].startswith(",")  # 결측 티커는 "000nan" 이 아니라 빈 칸


def test_reanalysis_merge_keeps_rows_it_did_not_reanalyze():
    """재분석하지 않은 행은 AI 호출 동안 다른 실행이 쓴 값을 유지한다."""
    snapshot = pd.DataFrame(
        {"ticker": ["005930", "000660"], "signal_date": ["2026-09-22"] * 2, "ai_action": ["BUY", "BUY"]}
    )
    full = snapshot.copy()
    full.loc[1, "ai_action"] = "SELL"  # 재분석 도중 다른 실행이 1번 행을 새로 분석했다
    updated = snapshot.copy()
    updated.loc[0, "ai_action"] = "HOLD"  # 재분석은 0번 행만 갱신했다

    merged = reanalysis._merge_reanalysis_updates_into_full_signals_frame(
        updated_signals_df=updated,
        signals_path="signals_log.csv",
        load_csv_file=lambda *_a, **_k: full,
        target_indexes=[0],
    )
    assert list(merged["ai_action"]) == ["HOLD", "SELL"]


def test_create_signals_log_waits_for_lock(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = data_dir / "signals_log.csv"
    pd.DataFrame({"ticker": ["000660"], "signal_date": ["2026-09-21"], "score": [1]}).to_csv(path, index=False)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    _assert_waits_for_lock(
        path,
        lambda: init_data.create_signals_log(target_date="2026-02-19", run_ai=False),
        while_locked=lambda: _append_marker(path, "111111"),
    )
    assert {"000660", "005930", "111111"} <= _tickers(path)


def test_recent_price_update_keeps_rows_added_during_fetch(monkeypatch, tmp_path):
    """시세 조회 중 다른 쓰기가 더한 행을 시세 갱신이 지우지 않는다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    path = data_dir / "signals_log.csv"
    columns = {"signal_date": ["2026-09-22"], "current_price": [100.0], "return_pct": [0.0]}
    pd.DataFrame({"ticker": ["005930"], "entry_price": [100.0], **columns}).to_csv(path, index=False)
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))

    def _ohlcv(_start, _end, _ticker):
        # 조회 도중 다른 경로가 행을 하나 더한 상황
        frame = pd.read_csv(path, dtype={"ticker": str})
        if "000660" not in set(frame["ticker"]):
            extra = pd.DataFrame({"ticker": ["000660"], "entry_price": [50.0], **columns})
            pd.concat([frame, extra], ignore_index=True).to_csv(path, index=False)
        return pd.DataFrame({"종가": [110]})

    monkeypatch.setitem(sys.modules, "pykrx", SimpleNamespace(stock=SimpleNamespace(get_market_ohlcv=_ohlcv)))
    init_data.update_vcp_signals_recent_price()

    frame = pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig").set_index("ticker")
    assert "000660" in frame.index
    assert frame.loc["005930", "current_price"] == 110
    assert frame.loc["005930", "return_pct"] == 10.0


def test_append_to_log_waits_for_lock(tmp_path):
    tracker = SignalTracker(data_dir=str(tmp_path))
    path = tmp_path / "signals_log.csv"
    pd.DataFrame({"ticker": ["000660"], "signal_date": ["2026-09-21"], "status": ["OPEN"]}).to_csv(path, index=False)
    new = pd.DataFrame({"ticker": ["005930"], "signal_date": ["2026-09-22"], "status": ["OPEN"]})

    _assert_waits_for_lock(
        path,
        lambda: tracker._append_to_log(new),
        while_locked=lambda: _append_marker(path, "111111"),
    )
    assert {"000660", "005930", "111111"} <= _tickers(path)


def test_update_open_signals_waits_for_lock(tmp_path):
    pd.DataFrame(
        [{"ticker": "000001", "date": "2026-02-20", "close": 110, "high": 111, "low": 109, "volume": 10_000}]
    ).to_csv(tmp_path / "daily_prices.csv", index=False, encoding="utf-8-sig")
    old_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    path = tmp_path / "signals_log.csv"
    pd.DataFrame(
        [{"signal_date": old_date, "ticker": "000001", "entry_price": 100, "status": "OPEN", "hold_days": 0}]
    ).to_csv(path, index=False, encoding="utf-8-sig")
    tracker = SignalTracker(data_dir=str(tmp_path))

    _assert_waits_for_lock(
        path,
        tracker.update_open_signals,
        while_locked=lambda: _append_marker(path, "111111"),
    )
    frame = pd.read_csv(path, dtype={"ticker": str}, encoding="utf-8-sig").set_index("ticker")
    assert "111111" in frame.index
    assert frame.loc["000001", "status"] == "CLOSED"


def test_create_signals_log_returns_false_when_lock_cannot_open(monkeypatch, tmp_path):
    """잠금 파일을 열지 못해도 실패는 예외가 아니라 False 다([VCP-028] 계약)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "signals_log.csv.lock").symlink_to(tmp_path / "elsewhere")  # O_NOFOLLOW 가 ELOOP 를 낸다
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr("engine.screener.SmartMoneyScreener", _DummyScreener)
    monkeypatch.setattr("engine.market_gate.MarketGate", _DummyMarketGate)

    assert init_data.create_signals_log(target_date="2026-02-19", run_ai=False) is False
