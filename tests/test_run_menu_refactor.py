#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py 대화형 메뉴 회귀 테스트
"""

from __future__ import annotations

import asyncio
import builtins
import os

import pandas as pd

import engine.signal_tracker as signal_tracker_module


class _FakeTracker:
    def __init__(self, reasons):
        self.reasons = reasons
        self.saved = None

    def scan_today_signals(self):
        return pd.DataFrame({"name": ["가", "나"], "ticker": ["000001", "000002"], "score": [80, 70]})

    async def analyze_signals_with_ai(self, df):
        df = df.copy()
        df["ai_action"] = ["BUY", "HOLD"]
        df["ai_confidence"] = [80, 50]
        df["ai_reason"] = self.reasons
        return df

    def _append_to_log(self, df):
        self.saved = df.copy()


def test_menu2_saves_untruncated_ai_reason(monkeypatch):
    # run.py 는 import 할 때 저장소 루트로 chdir 한다. 테스트가 끝나면 원래 cwd 로 돌린다
    monkeypatch.chdir(os.getcwd())
    import run

    long_reason = "가" * 80
    tracker = _FakeTracker([long_reason, float("nan")])
    monkeypatch.setattr(signal_tracker_module, "create_tracker", lambda: tracker)
    answers = iter(["2", "y", ""])
    monkeypatch.setattr(builtins, "input", lambda *_: next(answers))

    run.main()

    # 출력용 50자 자르기가 저장본에 새지 않는다([VCP-038]). 원문과 NaN 을 포함해 분석 결과 그대로다
    expected = asyncio.run(tracker.analyze_signals_with_ai(tracker.scan_today_signals()))
    pd.testing.assert_frame_equal(tracker.saved, expected)
    assert tracker.saved["ai_reason"].iloc[0] == long_reason
