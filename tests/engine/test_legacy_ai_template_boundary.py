#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy content is excluded without guessing provenance from vocabulary."""
import copy
import pytest
from engine.kr_ai_templates import MockAnalysisTemplates
from engine.kr_ai_strategies import GeminiStrategy, GPTStrategy
from app.routes.kr_market_signal_common import _is_meaningful_ai_reason
from services.kr_market_ai_payload_service import _clone_payload_for_signal_normalization


@pytest.mark.parametrize('index', range(3))
@pytest.mark.parametrize('same_driver', [True, False])
def test_complete_legacy_templates_filtered_without_mutating_cache(index, same_driver):
    t = MockAnalysisTemplates
    driver, risk = t.INVESTMENT_DRIVERS[0], t.RISK_FACTORS[0]
    second = driver if same_driver else t.INVESTMENT_DRIVERS[1]
    hypothesis = t.HYPOTHESIS_TEMPLATES[index].format(name='삼성전자', driver=driver, risk=risk)
    reason = f'[핵심 투자 포인트]\n• {driver}\n• {second}\n\n[리스크 요인]\n• {risk}\n\n[종합 의견]\n{hypothesis}'
    original = {'signals': [{'ticker': '005930', 'gemini_recommendation': {'action': 'BUY', 'reason': reason}, 'gpt_recommendation': {'action': 'HOLD', 'reason': 'K-칩스법 영향은 수주 자료와 함께 검토해야 합니다.'}}]}
    saved = copy.deepcopy(original)
    assert not _is_meaningful_ai_reason(reason)
    cloned = _clone_payload_for_signal_normalization(original)
    assert cloned['signals'][0]['gemini_recommendation'] is None
    assert cloned['signals'][0]['gpt_recommendation'] == original['signals'][0]['gpt_recommendation']
    assert original == saved
    assert _is_meaningful_ai_reason(reason + '!')
    assert _is_meaningful_ai_reason(reason + 'x' * 4096)


def test_fixed_gpt_template_is_not_real_analysis():
    assert not _is_meaningful_ai_reason('VCP 패턴 및 외인 매집 추이 확인')


@pytest.mark.parametrize('strategy', [GeminiStrategy, GPTStrategy])
def test_legacy_producer_disabled_even_with_key(strategy):
    instance = strategy('synthetic-unused-key')
    assert instance.is_available is False
    assert instance.analyze({'name': 'T', 'price': 100}, []) is None
