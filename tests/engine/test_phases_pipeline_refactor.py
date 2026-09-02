#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SignalGenerationPipeline 계약 회귀 테스트

파이프라인이 결정하는 것은 세 가지이며 셋 다 조용히 어긋날 수 있다.

1. 각 페이즈가 넘겨받는 자료. 네 자리를 모두 확인한다. 예를 들어 Phase 3 나 Phase 4 가
   Phase 2 가 아니라 Phase 1 의 결과를 받으면 뉴스가 없어 탈락한 종목이 최종 시그널에
   섞인다. 픽스처 값을 단계마다 다르게 둔 것이 이 검사가 성립하는 조건이다.
2. 결과가 비었을 때 던지는 예외의 종류. 둘이 뒤바뀌면 generate() 가 "후보 없음" 과
   "전량 탈락" 을 구분하지 못한다.
3. phase1 통계를 꺼내는 키 경로. 이 키가 바뀌면 generator_runtime_mixin.generate() 와
   generator.run_screener() 가 조용히 기본값으로 떨어져 화면의 후보 수가 0 이 된다.
   나머지 세 키는 지금 읽는 곳이 없으나 같은 자리에서 함께 고정해 둔다.
"""

from __future__ import annotations

from datetime import date

import pytest

from engine.exceptions import AllCandidatesFilteredError, NoCandidatesError
from engine.phases_pipeline import SignalGenerationPipeline

TARGET_DATE = date(2026, 9, 2)

# 단계마다 값을 다르게 둔다. 같은 값을 돌려쓰면 페이즈 사이에서 자료가 뒤바뀌어도
# 단언이 우연히 통과한다.
CANDIDATES = [{"code": "005930"}, {"code": "000660"}, {"code": "035720"}]
PHASE1_RESULTS = [{"code": "005930", "pre_score": 18}, {"code": "000660", "pre_score": 15}]
PHASE2_RESULTS = [{"code": "005930", "news": ["수주 공시"]}]  # 000660 은 뉴스가 없어 탈락한다
LLM_RESULTS = {"005930": {"recommendation": "매수"}}
FINAL_SIGNALS = ["signal-005930"]


class _Phase1Stub:
    def __init__(self, results, calls):
        self._results = results
        self._calls = calls

    async def execute(self, candidates, target_date=None):
        self._calls.append(("phase1", candidates, target_date))
        return self._results

    def get_stats(self):
        return {"processed": len(CANDIDATES), "passed": len(self._results)}

    def get_drop_stats(self):
        return {"low_trading_value": 1, "no_news": 0}


class _Phase2Stub:
    def __init__(self, results, calls):
        self._results = results
        self._calls = calls

    async def execute(self, items):
        self._calls.append(("phase2", items))
        return self._results

    def get_stats(self):
        return {"processed": 2, "passed": len(self._results)}

    def get_no_news_count(self):
        return 1


class _Phase3Stub:
    def __init__(self, results, calls):
        self._results = results
        self._calls = calls

    async def execute(self, items, market_status=None):
        self._calls.append(("phase3", items, market_status))
        return self._results

    def get_stats(self):
        return {"processed": 1, "passed": 1}


class _Phase4Stub:
    def __init__(self, results, calls):
        self._results = results
        self._calls = calls

    async def execute(self, items, llm_results, target_date):
        self._calls.append(("phase4", items, llm_results, target_date))
        return self._results

    def get_stats(self):
        return {"processed": 1, "passed": len(self._results)}

    def get_final_stats(self):
        return {"S": 0, "A": 1}


def _build_pipeline(calls, phase1_results=PHASE1_RESULTS, phase2_results=PHASE2_RESULTS):
    """네 페이즈를 스텁으로 채운 파이프라인을 만든다. 호출은 calls 에 기록된다."""
    phase1 = _Phase1Stub(phase1_results, calls)
    phase2 = _Phase2Stub(phase2_results, calls)
    phase3 = _Phase3Stub(LLM_RESULTS, calls)
    phase4 = _Phase4Stub(FINAL_SIGNALS, calls)
    return SignalGenerationPipeline(phase1=phase1, phase2=phase2, phase3=phase3, phase4=phase4)


async def test_execute_wires_four_phases_in_order():
    calls = []
    pipeline = _build_pipeline(calls)

    signals = await pipeline.execute(
        candidates=CANDIDATES,
        market_status={"gate": "OPEN"},
        target_date=TARGET_DATE,
    )

    assert [call[0] for call in calls] == ["phase1", "phase2", "phase3", "phase4"]
    assert signals == FINAL_SIGNALS

    # 네 자리를 모두 확인한다. 한 자리라도 앞 단계의 자료를 받으면 이미 걸러낸 종목이
    # 뒤 단계로 새어 나간다.
    assert calls[0][1] == CANDIDATES        # phase1 은 원본 후보를 받는다
    assert calls[1][1] == PHASE1_RESULTS    # phase2 는 사전 선별을 통과한 종목만 받는다
    assert calls[2][1] == PHASE2_RESULTS    # phase3 는 뉴스가 있는 종목만 받는다
    assert calls[3][1] == PHASE2_RESULTS    # phase4 도 phase1 이 아니라 phase2 의 결과를 받는다
    assert calls[3][2] == LLM_RESULTS       # phase4 는 phase3 의 분석 결과를 받는다

    assert calls[0][2] == TARGET_DATE          # phase1 의 target_date
    assert calls[2][2] == {"gate": "OPEN"}     # phase3 의 market_status
    assert calls[3][3] == TARGET_DATE          # phase4 의 target_date


async def test_missing_target_date_falls_back_to_today():
    """target_date 를 주지 않아도 phase1 과 phase4 는 날짜를 받는다."""
    calls = []
    pipeline = _build_pipeline(calls)

    before = date.today()
    await pipeline.execute(candidates=CANDIDATES)
    after = date.today()

    # 실행 도중에 자정을 넘기면 두 날짜가 달라지므로 둘 중 하나면 통과로 본다.
    assert calls[0][2] in (before, after)   # phase1 의 target_date
    assert calls[3][3] in (before, after)   # phase4 의 target_date


async def test_empty_phase1_result_raises_no_candidates_error():
    calls = []
    pipeline = _build_pipeline(calls, phase1_results=[])

    with pytest.raises(NoCandidatesError):
        await pipeline.execute(candidates=CANDIDATES, target_date=TARGET_DATE)

    assert [call[0] for call in calls] == ["phase1"]


async def test_empty_phase2_result_raises_all_candidates_filtered_error():
    calls = []
    pipeline = _build_pipeline(calls, phase2_results=[])

    with pytest.raises(AllCandidatesFilteredError):
        await pipeline.execute(candidates=CANDIDATES, target_date=TARGET_DATE)

    assert [call[0] for call in calls] == ["phase1", "phase2"]


def test_pipeline_stats_keeps_the_key_paths_callers_read():
    """generate() 는 phase1.drops 를, run_screener() 는 phase1.stats.passed 를 직접 읽는다."""
    pipeline = _build_pipeline([])

    stats = pipeline.get_pipeline_stats()

    assert stats["phase1"]["stats"]["passed"] == len(PHASE1_RESULTS)
    assert stats["phase1"]["drops"] == {"low_trading_value": 1, "no_news": 0}
    assert stats["phase2"]["no_news"] == 1
    assert stats["phase4"]["grades"] == {"S": 0, "A": 1}
