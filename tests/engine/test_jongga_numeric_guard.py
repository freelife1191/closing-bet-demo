#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI가 재서술한 금액/가격 대신 원자료 숫자만 표시한다."""
import pytest
from engine.exceptions import LLMResponseParseError
from engine.llm_analyzer_parsers import validate_jongga_results



def valid_reason():
    body = '원자재 가격과 정부 지원, 원전 수요를 확인하고 기업의 실적과 시장 환경을 함께 검토합니다. 단기 변동성과 추세 지속 여부를 살피며 확인되지 않은 정보로 성급하게 판단하지 않습니다.'
    return ' '.join(f'{marker} {label}: {body}' for marker,label in zip('①②③④⑤',['뉴스/재료 분석','거래대금/거래량 평가','수급 동향','리스크 요인','매매 전략']))

def inputs():
    return [{'stock':{'stock_name':'삼성전자','current_price':275000,'trading_value':9208918133058},'supply':{'foreign_buy_5d':1558400000000,'inst_buy_5d':3437200000000}}]


@pytest.mark.parametrize('reason', ['거래대금 92조 89억 원', '거래대금은구십이조원대', '수익률은오퍼센트대', '평가점수는십점대', '거래대금은삼백달러선', '수급은두배정도', '한조원', '거래대금은구십이조원', '수익률은오퍼센트', '수급은두배', '삼백 달러', '목표 ③만원', '80조 47억', '십억 원', '수십 퍼센트', '비중 %', '손절은 300,000원', '목표 삼십만원', '수익률 ５％', '외인 매수가 두 배'])
def test_unverified_numbers_are_rejected(reason):
    with pytest.raises(LLMResponseParseError):
        validate_jongga_results(results={'삼성전자':{'reason':valid_reason()+' '+reason}},items=inputs())


def test_qualitative_reason_gets_deterministic_input_facts():
    result=validate_jongga_results(results={'삼성전자':{'reason':valid_reason()}},items=inputs())
    text=result['삼성전자']['reason']
    assert '9조 2,089억원' in text and '9,208,918,133,058원' in text
    assert '현재가: 275,000원' in text
    assert '1,558,400,000,000원' in text
    assert '92조' not in text


@pytest.mark.parametrize('results',[{}, {'다른종목':{'reason':'정성 분석'}}])
def test_missing_or_extra_stock_fails_closed(results):
    with pytest.raises(LLMResponseParseError):validate_jongga_results(results=results,items=inputs())


def test_analyzer_retries_once_then_uses_checked_reason(monkeypatch):
    import asyncio,json
    from engine.llm_analyzer import LLMAnalyzer
    a=LLMAnalyzer.__new__(LLMAnalyzer)
    a.provider='gemini';a._client=object();a._retry_strategy=None
    a._client_init_attempted=True;a._api_key_source='test';a._last_loaded_key='test';a._missing_key_warned=False
    responses=iter(['거래대금 92조89억원',valid_reason()])
    calls=[]
    async def fake_execute(prompt,timeout):
        calls.append(prompt)
        return json.dumps([{'name':'삼성전자','reason':next(responses),'action':'HOLD','score':1,'confidence':70}])
    monkeypatch.setattr(a,'_execute_llm_call',fake_execute)
    result=asyncio.run(a.analyze_news_batch_jongga(inputs()))
    assert len(calls)==2 and '9조 2,089억원' in result['삼성전자']['reason']


def test_repeated_invalid_response_raises_and_phase3_cannot_swallow(monkeypatch):
    import asyncio,json
    from engine.llm_analyzer import LLMAnalyzer
    from engine.phases_news_llm import Phase3LLMAnalyzer
    a=LLMAnalyzer.__new__(LLMAnalyzer)
    a.provider='gemini';a._client=object();a._retry_strategy=None
    a._client_init_attempted=True;a._api_key_source='test';a._last_loaded_key='test';a._missing_key_warned=False
    calls=[]
    async def bad(prompt,timeout):
        calls.append(prompt)
        return json.dumps([{'name':'삼성전자','reason':'손절 300000원'}])
    monkeypatch.setattr(a,'_execute_llm_call',bad)
    with pytest.raises(LLMResponseParseError):asyncio.run(a.analyze_news_batch_jongga(inputs()))
    assert len(calls)==2
    async def fail(*a,**k):raise LLMResponseParseError('', 'unsafe numbers')
    monkeypatch.setattr(a,'analyze_news_batch_jongga',fail)
    with pytest.raises(LLMResponseParseError):asyncio.run(Phase3LLMAnalyzer(a,request_delay=0).execute(inputs()))


@pytest.mark.parametrize('reason',['짧은 분석', '① 뉴스: 호재 ② 거래: 거래 ③ 수급: 매수 ④ 위험: 과열 ⑤ 전략: 관망'])
def test_incomplete_sections_are_rejected(reason):
    with pytest.raises(LLMResponseParseError):validate_jongga_results(results={'삼성전자':{'reason':reason}},items=inputs())


def test_missing_client_stops_actual_screener_before_save(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import Mock
    from engine import generator as module
    from engine.phases_news_llm import Phase3LLMAnalyzer
    class FakeGenerator:
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def generate(self,**kwargs):
            return await Phase3LLMAnalyzer(SimpleNamespace(client=None),request_delay=0).execute(inputs())
    monkeypatch.setattr(module,'SignalGenerator',lambda **kw:FakeGenerator())
    save=Mock(side_effect=AssertionError('must not save'))
    monkeypatch.setattr(module,'save_result_to_json',save)
    with pytest.raises(LLMResponseParseError):asyncio.run(module.run_screener(target_date='2026-09-21'))
    save.assert_not_called()
