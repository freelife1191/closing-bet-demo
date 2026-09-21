#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""통합 KRX의 실제 로컬 경로와 공개 캐시 계약."""
import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest

from engine.collectors import KRXCollector
from engine.collectors.krx_local_data_mixin import BASE_DIR


@pytest.mark.parametrize("directory", ["data", "custom-data"])
def test_relative_data_dir_resolves_from_project_root(directory):
    collector = KRXCollector(SimpleNamespace(DATA_DIR=directory))
    from pathlib import Path
    assert collector._get_data_dir() == str(Path(BASE_DIR) / directory)


def test_absolute_data_dir_is_not_rebased(tmp_path):
    assert KRXCollector(SimpleNamespace(DATA_DIR=str(tmp_path)))._get_data_dir() == str(tmp_path)


def test_local_prices_and_lookup_use_configured_directory(tmp_path):
    pd.DataFrame([{"ticker": "005930", "date": "2026-02-21", "open": 1000, "close": 1100,
                   "volume": 2_000_000}]).to_csv(tmp_path / "daily_prices.csv", index=False)
    pd.DataFrame([{"ticker": "005930", "name": "테스트", "market": "KOSPI"}]).to_csv(
        tmp_path / "korean_stocks_list.csv", index=False)
    collector = KRXCollector(SimpleNamespace(DATA_DIR=str(tmp_path), min_change_pct=0))
    result = collector._load_from_local_csv("KOSPI", 5, "20260221")
    assert [stock.code for stock in result] == ["005930"]
    assert result[0].name == "테스트"
    assert collector._load_from_local_csv("KOSPI", 5, "20260220") == []


def test_class_cache_shared_between_public_and_submodule():
    from engine.collectors.krx import KRXCollector as SubmoduleKRX
    assert KRXCollector._pykrx_supply_cache is SubmoduleKRX._pykrx_supply_cache
