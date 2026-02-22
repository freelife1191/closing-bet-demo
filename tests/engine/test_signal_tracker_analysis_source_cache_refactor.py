#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Tracker analysis source cache 리팩토링 테스트
"""

from __future__ import annotations

import os

import pandas as pd

import engine.signal_tracker_analysis_source_cache as source_cache


def test_load_csv_with_signature_cache_normalizes_relative_and_absolute_path(monkeypatch, tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame([{"ticker": "005930", "score": 90}]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    monkeypatch.chdir(tmp_path)
    calls = {"count": 0}
    original_read_csv = source_cache.pd.read_csv

    def _counted_read_csv(*args, **kwargs):
        calls["count"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(source_cache.pd, "read_csv", _counted_read_csv)

    cache: dict[str, tuple[tuple[int, int, int], pd.DataFrame]] = {}
    first = source_cache.load_csv_with_signature_cache(
        path="sample.csv",
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )
    second = source_cache.load_csv_with_signature_cache(
        path=str(csv_path),
        usecols_filter=None,
        cache=cache,
        sqlite_cache_kind=None,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert calls["count"] == 1
    assert list(cache.keys()) == [os.path.abspath(str(csv_path))]
