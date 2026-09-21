#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from flask import Flask, Blueprint
import pytest
from app.routes.kr_market_data_ai_routes import _register_ai_analysis_route
from services.kr_market_ai_payload_service import build_ai_analysis_payload_for_target_date


@pytest.mark.parametrize('value', ['../../../package','../../secret','2026-02-30','20260230','','２０２６-０２-１１','2026-02-11/../../../package'])
def test_invalid_analysis_date_rejected_before_any_loader(value):
    calls=[]
    def loader(*args,**kwargs):
        calls.append(args)
        return {'secret':'synthetic-only'}
    app=Flask(__name__);bp=Blueprint('test_ai_dates',__name__)
    _register_ai_analysis_route(bp,logger=logging.getLogger('test'),deps={
        'build_ai_analysis_payload_for_target_date':build_ai_analysis_payload_for_target_date,
        'load_json_file':loader,'build_ai_signals_from_jongga_results':lambda *a,**k:[],
        'normalize_ai_payload_tickers':lambda p:p,
        'build_latest_ai_analysis_payload':lambda **k:loader(),
        'should_use_jongga_ai_payload':lambda *a:False,'format_signal_date':str,
    });app.register_blueprint(bp,url_prefix='/api/kr')
    response=app.test_client().get('/api/kr/ai-analysis',query_string={'date':value})
    assert response.status_code==400
    assert calls==[] and 'secret' not in response.get_data(as_text=True)


@pytest.mark.parametrize('value',['2026-02-11','20260211'])
def test_valid_analysis_date_uses_only_fixed_basenames(value):
    calls=[]
    def loader(name,**kwargs):calls.append(name);return {}
    payload=build_ai_analysis_payload_for_target_date(value,loader,lambda *a,**k:[],lambda p:p,logging.getLogger('test'),now=datetime(2026,9,21))
    assert calls==['jongga_v2_results_20260211.json','kr_ai_analysis_20260211.json','ai_analysis_results_20260211.json']
    assert payload['signal_date']=='2026-02-11'
