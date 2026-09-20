#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""티커 공통 정규화 계약 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from engine.ticker_utils import normalize_ticker


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (5930, "005930"),
        (5930.0, "005930"),
        ("0007c0", "0007C0"),
        ("A005930", "005930"),
        ("005930.KS", "005930"),
        (None, ""),
        (pd.NA, ""),
        (True, ""),
        (0, ""),
        (-5930, ""),
        ("-5930", ""),
        (float("nan"), ""),
        (float("inf"), ""),
        (5930.5, ""),
        (10**400, ""),
        ("5930.0", ""),
        (date(2026, 2, 11), ""),
        ("20260211", ""),
        ("１２３４５６", ""),
        (Path("/tmp/005930"), ""),
    ],
)
def test_normalize_ticker_preserves_only_canonical_market_codes(value, expected):
    """결측·날짜·비정수는 다른 종목 키로 변환되면 안 된다."""
    assert normalize_ticker(value) == expected
