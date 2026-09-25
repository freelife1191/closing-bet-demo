#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""[JONGGA-040] 종가베팅 최신 파일은 run_screener 의 원자적 저장 한 번으로만 쓰인다."""

from __future__ import annotations

import logging
import sys
import types
from datetime import date

import pytest

from scripts import init_data
from services import kr_market_jongga_runtime_service as runtime_service
from services import kr_market_route_service as route_service

LOGGER = logging.getLogger(__name__)


def _fake_result():
    return types.SimpleNamespace(
        date=date(2026, 9, 23), total_candidates=1, filtered_count=1, scanned_count=1,
        signals=[], by_grade={}, by_market={}, processing_time_ms=1,
        market_status={}, market_summary="", trending_themes=[],
    )


def _fake_generator(monkeypatch, save):
    async def _run_screener(*_a, **_k):
        return _fake_result()

    module = types.ModuleType("engine.generator")
    module.run_screener = _run_screener
    module.save_result_to_json = save
    monkeypatch.setitem(sys.modules, "engine.generator", module)


def test_create_jongga_v2_latest_does_not_rewrite_latest_file(monkeypatch, tmp_path):
    # BASE_DIR 과 cwd 를 모두 tmp_path 로 돌려, 어느 쪽 경로로 다시 써도 잡히게 한다.
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(init_data, "BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    saves = []
    _fake_generator(monkeypatch, saves.append)

    assert init_data.create_jongga_v2_latest() is True
    assert saves == []
    assert not (tmp_path / "data" / "jongga_v2_latest.json").exists()


@pytest.mark.parametrize("service", [route_service, runtime_service], ids=["route", "runtime"])
def test_background_pipeline_does_not_save_twice(monkeypatch, service):
    saves = []
    _fake_generator(monkeypatch, saves.append)
    monkeypatch.setattr(service, "_reload_engine_submodules", lambda: None)
    monkeypatch.setattr(service, "_send_jongga_notification_from_result", lambda *_a: None)

    service.run_jongga_v2_background_pipeline(
        capital=50_000_000, markets=None, target_date=None, logger=LOGGER,
    )

    assert saves == []
