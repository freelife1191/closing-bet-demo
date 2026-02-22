#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_sources_provider_strategies 리팩토링 회귀 테스트
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pandas as pd

from engine.data_sources_provider_strategies import YFinanceSource


def test_yfinance_source_fetch_index_data_restores_logger_level_on_failure():
    source = YFinanceSource()
    source._available = True
    source._yf = SimpleNamespace(
        download=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    yf_logger = logging.getLogger("yfinance")
    original_level = yf_logger.level
    yf_logger.setLevel(logging.INFO)

    try:
        df = source.fetch_index_data("KS11", "2026-01-01", "2026-01-10")
        assert df.empty
        assert yf_logger.level == logging.INFO
    finally:
        yf_logger.setLevel(original_level)


def test_yfinance_source_fetch_fx_rate_restores_logger_level_and_passes_threads_disabled():
    call_kwargs = {}

    def _fake_download(*_args, **kwargs):
        call_kwargs.update(kwargs)
        return pd.DataFrame(
            {"Close": [1300.0, 1310.5]},
            index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
        )

    source = YFinanceSource()
    source._available = True
    source._yf = SimpleNamespace(download=_fake_download)

    yf_logger = logging.getLogger("yfinance")
    original_level = yf_logger.level
    yf_logger.setLevel(logging.WARNING)

    try:
        df = source.fetch_fx_rate("USD/KRW", days=7)
        assert not df.empty
        assert set(df.columns) == {"date", "close"}
        assert call_kwargs["threads"] is False
        assert call_kwargs["progress"] is False
        assert yf_logger.level == logging.WARNING
    finally:
        yf_logger.setLevel(original_level)
