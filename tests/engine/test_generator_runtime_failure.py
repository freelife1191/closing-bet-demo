#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""실제 파이프라인 실패는 빈 스크리닝 성공으로 바뀌지 않는다."""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

from engine.generator_runtime_mixin import SignalGeneratorRuntimeMixin


class _Collector:
    async def get_top_gainers(self, market, *_args):
        return [SimpleNamespace(ticker=market)]


class _Phase:
    def get_stats(self):
        return {"passed": 0}


class _Pipeline:
    phase1 = _Phase()
    phase2 = _Phase()

    def __init__(self):
        self.calls = 0

    async def execute(self, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return ["first-market-signal"]
        raise RuntimeError("news transport failed")

    def get_pipeline_stats(self):
        return {"phase1": {"drops": {}}}


class _Generator(SignalGeneratorRuntimeMixin):
    def __init__(self):
        self.config = SimpleNamespace()
        self._collector = _Collector()
        self._pipeline = _Pipeline()

    async def _sync_toss_data(self, *_args):
        return None

    async def _get_market_status(self, *_args):
        return {}


def test_second_market_failure_propagates_instead_of_returning_first_market_partial_result():
    generator = _Generator()

    with pytest.raises(RuntimeError, match="news transport failed"):
        asyncio.run(generator.generate(target_date=date(2026, 9, 1), markets=["KOSPI", "KOSDAQ"]))


def test_failed_run_does_not_replace_existing_daily_or_latest(monkeypatch, tmp_path):
    from engine import generator as module
    from unittest.mock import Mock

    class ContextGenerator(_Generator):
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

    monkeypatch.chdir(tmp_path)
    data = tmp_path / 'data'
    data.mkdir()
    files = [data / 'jongga_v2_latest.json', data / 'jongga_v2_results_20260901.json']
    for p in files:
        p.write_bytes(b'{"signals":["existing"]}')
    before = [p.read_bytes() for p in files]
    monkeypatch.setattr(module, 'SignalGenerator', lambda **k: ContextGenerator())
    save = Mock(side_effect=AssertionError('failed runs must not save'))
    monkeypatch.setattr(module, 'save_result_to_json', save)
    with pytest.raises(RuntimeError, match='news transport failed'):
        asyncio.run(module.run_screener(target_date='2026-09-01'))
    save.assert_not_called()
    assert [p.read_bytes() for p in files] == before


def test_normal_no_candidates_is_still_empty_success():
    from engine.exceptions import NoCandidatesError
    generator = _Generator()

    async def no_candidates(**kwargs):
        raise NoCandidatesError('All', 'below threshold')

    generator._pipeline.execute = no_candidates
    assert asyncio.run(generator.generate(target_date=date(2026, 9, 1))) == []


def test_no_news_for_all_eligible_candidates_is_failure_not_empty_success():
    from engine.exceptions import AllCandidatesFilteredError
    generator = _Generator()

    async def no_news(**kwargs):
        raise AllCandidatesFilteredError(3, 'No candidates with news')

    generator._pipeline.execute = no_news
    with pytest.raises(AllCandidatesFilteredError):
        asyncio.run(generator.generate(target_date=date(2026, 9, 1)))
