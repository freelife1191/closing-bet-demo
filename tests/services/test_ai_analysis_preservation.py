#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
from types import SimpleNamespace
import pytest
from services import common_update_ai_analysis_service as service

GOOD = {'action': 'HOLD', 'confidence': 75, 'reason': '매출 공시와 수급의 추가 확인이 필요합니다.'}


def invoke(tmp_path, monkeypatch, *, results=None, date='2026-02-11', combined=False, empty=False):
    (tmp_path / 'signals_log.csv').write_text('signal_date,ticker,name,score,entry_price\n' + ('' if empty else '2026-02-11,005930,삼성전자,88,71000\n'))
    calls = []
    def run(analyzer, stocks):
        calls.append(stocks)
        return results
    monkeypatch.setattr(service, 'get_vcp_analyzer', lambda: object(), raising=False)
    monkeypatch.setattr(service, 'run_async_analyzer_batch', run, raising=False)
    statuses = []
    outcome = service.run_ai_analysis_step(target_date=date, selected_items=['VCP Signals'] if combined else ['AI Analysis'], vcp_df=True if combined else None, update_item_status=lambda *args: statuses.append(args), shared_state=SimpleNamespace(STOP_REQUESTED=False), logger=logging.getLogger('test'), data_dir=str(tmp_path))
    return outcome, calls, statuses


@pytest.mark.parametrize('results', [None, {}, {'005930': {'gemini_recommendation': None}}, {'005930': {'gemini_recommendation': {'action': 'BUY', 'reason': 'VCP 패턴 및 외인 매집 추이 확인'}}}])
def test_failure_preserves_all_files(tmp_path, monkeypatch, results):
    sentinel = b'{"signals": [], "news": ["old"]}'
    files = ['ai_analysis_results.json', 'kr_ai_analysis.json', 'ai_analysis_results_20260211.json', 'kr_ai_analysis_20260211.json']
    for name in files:
        (tmp_path / name).write_bytes(sentinel)
    result, calls, statuses = invoke(tmp_path, monkeypatch, results=results)
    assert result['error'] and result['count'] == 0
    assert len(calls) == 1
    assert statuses[-1][1] == 'error'
    assert all((tmp_path / name).read_bytes() == sentinel for name in files)


def test_partial_success_preserves_news_other_provider_other_ticker_and_latest(tmp_path, monkeypatch):
    for prefix in ['ai_analysis_results', 'kr_ai_analysis']:
        (tmp_path / f'{prefix}.json').write_text('latest sentinel')
        (tmp_path / f'{prefix}_20260211.json').write_text(json.dumps({'market_indices': {'x': 1}, 'signals': [{'ticker': '5930', 'news': ['retained'], 'gpt_recommendation': GOOD}, {'ticker': '000660', 'gemini_recommendation': GOOD}]}))
    result, calls, _ = invoke(tmp_path, monkeypatch, results={'005930': {'gemini_recommendation': GOOD, 'gpt_recommendation': None}})
    assert result['count'] == 1
    assert calls[0][0]['current_price'] == 71000
    assert 'foreign_1d' not in calls[0][0]
    for prefix in ['ai_analysis_results', 'kr_ai_analysis']:
        assert (tmp_path / f'{prefix}.json').read_text() == 'latest sentinel'
        payload = json.loads((tmp_path / f'{prefix}_20260211.json').read_text())
        assert payload['market_indices'] == {'x': 1}
        assert payload['signals'][0]['gpt_recommendation'] == GOOD
        assert payload['signals'][0]['news'] == ['retained']
        assert payload['signals'][1]['ticker'] == '000660'


@pytest.mark.parametrize('empty', [False, True])
def test_combined_no_model_no_write(tmp_path, monkeypatch, empty):
    old = {'signal_date': '2026-02-11', 'signals': [{'ticker': '005930', 'gemini_recommendation': GOOD}]}
    path = tmp_path / 'ai_analysis_results_20260211.json'
    path.write_text(json.dumps(old))
    before = path.read_bytes()
    result, calls, statuses = invoke(tmp_path, monkeypatch, combined=True, empty=empty)
    assert result['count'] == (0 if empty else 1)
    assert calls == [] and statuses[-1][1] == 'done'
    assert path.read_bytes() == before
    assert not (tmp_path / 'kr_ai_analysis_20260211.json').exists()


def test_combined_wrong_ticker_is_error(tmp_path, monkeypatch):
    (tmp_path / 'ai_analysis_results_20260211.json').write_text(json.dumps({'signal_date': '2026-02-11', 'signals': [{'ticker': '000660', 'gemini_recommendation': GOOD}]}))
    result, calls, _ = invoke(tmp_path, monkeypatch, combined=True)
    assert result['error'] and calls == []


@pytest.mark.parametrize('date', ['../../bad', '2026-02-30', '', '２０２６-０２-１１'])
def test_invalid_date_rejected_without_analysis(tmp_path, monkeypatch, date):
    result, calls, _ = invoke(tmp_path, monkeypatch, date=date)
    assert result['error'] and calls == []
    assert not list(tmp_path.glob('*.json'))


def test_real_vcp_engine_with_synthetic_model_transport(tmp_path, monkeypatch):
    from engine import vcp_ai_analyzer as engine
    calls = []
    def generate_content(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text=json.dumps({'action': 'HOLD', 'confidence': 75, 'reason': '실측 검증용 합성 모델 응답입니다. 수급과 변동성 자료를 비교했으며 추가 거래량 확인이 필요합니다. 외부 모델은 호출하지 않았습니다.'}))
    monkeypatch.setenv('VCP_AI_PROVIDERS', 'gemini')
    monkeypatch.setenv('VCP_SECOND_PROVIDER', '')
    monkeypatch.setattr(engine, 'init_gemini_client', lambda *args: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    monkeypatch.setattr(engine, 'init_gpt_client', lambda *args: None)
    monkeypatch.setattr(engine, 'init_zai_client', lambda *args: None)
    analyzer = engine.VCPMultiAIAnalyzer()
    monkeypatch.setattr(service, 'get_vcp_analyzer', lambda: analyzer)
    (tmp_path / 'signals_log.csv').write_text('signal_date,ticker,name,score,entry_price\n2026-02-11,005930,삼성전자,88,71000\n')
    result = service.run_ai_analysis_step(target_date='2026-02-11', selected_items=['AI Analysis'], vcp_df=None, update_item_status=lambda *args: None, shared_state=SimpleNamespace(STOP_REQUESTED=False), logger=logging.getLogger('test'), data_dir=str(tmp_path))
    assert result == {'count': 1}
    assert len(calls) == 1 and 'contents' in calls[0]
    saved = json.loads((tmp_path / 'ai_analysis_results_20260211.json').read_text())
    assert saved['signals'][0]['gemini_recommendation']['confidence'] == 75


def test_memory_targets_respect_selected_date(monkeypatch):
    import pandas as pd
    frame = pd.DataFrame([{'signal_date': '2026-02-12', 'ticker': '000660'}, {'signal_date': '2026-02-11', 'ticker': '005930'}])
    selected, date = service._resolve_ai_target_dataframe(target_date='2026-02-11', selected_items=['VCP Signals'], vcp_df=frame, signals_path='not-read.csv', logger=logging.getLogger('test'))
    assert date == '2026-02-11'
    assert selected['ticker'].tolist() == ['005930']


@pytest.mark.parametrize('date,expected', [('20260211','005930'),(None,'000660')])
def test_mixed_signal_dates_use_calendar_order(tmp_path, date, expected):
    path=tmp_path/'signals_log.csv'
    path.write_text('signal_date,ticker,score\n20260211,005930,80\n2026-03-01,000660,85\n')
    frame, selected_date=service._resolve_ai_target_dataframe(target_date=date,selected_items=[],vcp_df=None,signals_path=str(path),logger=logging.getLogger('test'))
    assert [str(value).zfill(6) for value in frame['ticker']]==[expected]
    assert selected_date==('2026-02-11' if date else '2026-03-01')
