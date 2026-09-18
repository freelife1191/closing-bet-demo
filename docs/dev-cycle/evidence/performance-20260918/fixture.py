#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated market inputs; cumulative route, calculation, pagination and cache stay real."""
from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
ORIGINAL = Path('/Users/freelife/vibe/lecture/hodu/closing-bet-demo').resolve()
assert ROOT != ORIGINAL and not (ROOT / '.git').exists(), 'scratch archive only'
assert not (ROOT / '.env').exists(), 'no real env files'
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['SCHEDULER_ENABLED'] = 'false'

import pandas as pd
from flask import Blueprint, Flask, jsonify, request
from app.routes.kr_market_data_ai_routes import _register_cumulative_performance_route
from services.kr_market_backtest_kpi_helpers import aggregate_cumulative_kpis, paginate_items
from services.kr_market_backtest_trade_helpers import (
    build_cumulative_trade_record, build_ticker_price_index,
    extract_stats_date_from_results_filename, prepare_cumulative_price_dataframe,
)

STATE = ROOT / '.qa-performance'
STATE.mkdir(exist_ok=True)
(ROOT / 'data').mkdir(exist_ok=True)
logger = logging.getLogger('qa-performance')
control = {'mode': 'normal', 'status': 'GOOD', 'error': False}


def seed(mode: str) -> None:
    folder = STATE / mode
    folder.mkdir(exist_ok=True)
    prices = []
    count = 0 if mode == 'empty' else 60 if mode == 'paginated' else 2 if mode == 'small' else 24
    for i in range(count):
        day = date(2026, 6 if mode == 'paginated' else 8, 1) + timedelta(days=i)
        ticker = f'{100001+i:06d}'
        outcome = 'OPEN' if mode == 'open' or i >= count - 3 else 'WIN' if i < count - 10 else 'LOSS'
        if mode == 'small':
            outcome = 'WIN' if i == 0 else 'LOSS'
        high, low, close = (106, 99, 105) if outcome == 'WIN' else (101, 96, 97) if outcome == 'LOSS' else (101, 99, 100)
        prices.append({'ticker': ticker, 'date': (day+timedelta(days=1)).isoformat(), 'open':100, 'high':high, 'low':low, 'close':close})
        payload = {'date':day.isoformat(), 'signals':[{'ticker':ticker,'name':f'합성종목{i+1:02d}', 'entry_price':100,'grade':'SABD'[i%4], 'market':'KOSPI','score':{'total':70}, 'themes':[]}]}
        (folder / f'jongga_v2_results_{day:%Y%m%d}.json').write_text(json.dumps(payload,ensure_ascii=False))
    pd.DataFrame(prices,columns=['ticker','date','open','high','low','close']).to_csv(folder/'daily_prices.csv',index=False)


for mode in ('normal','open','empty','paginated','small'):
    seed(mode)


def folder() -> Path:
    return STATE / control['mode']


def load_results() -> list:
    return [(str(f),json.loads(f.read_text())) for f in sorted(folder().glob('jongga_v2_results_*.json'))]


def load_prices(*_args, **_kwargs) -> pd.DataFrame:
    return pd.read_csv(folder()/'daily_prices.csv',dtype={'ticker':str})


app = Flask(__name__)
bp = Blueprint('qa_cumulative',__name__)
_register_cumulative_performance_route(bp,logger=logger,deps={
    'get_data_path':lambda name:str(folder()/name),
    'data_dir_getter':lambda:str(folder()),
    'load_jongga_result_payloads':load_results,
    'load_csv_file':load_prices,
    'prepare_cumulative_price_dataframe':prepare_cumulative_price_dataframe,
    'build_ticker_price_index':build_ticker_price_index,
    'extract_stats_date_from_results_filename':extract_stats_date_from_results_filename,
    'build_cumulative_trade_record':build_cumulative_trade_record,
    'aggregate_cumulative_kpis':aggregate_cumulative_kpis,
    'paginate_items':paginate_items,
})
app.register_blueprint(bp,url_prefix='/api/kr')


@app.before_request
def synthetic_error():
    if request.path.startswith('/api/') and request.method != 'GET':
        return jsonify(error='fixture prohibits product mutation'),405
    if control['error'] and request.path == '/api/kr/closing-bet/cumulative':
        return jsonify(error='synthetic unavailable'),503


@app.get('/api/kr/backtest-summary')
def summary():
    status=control['status']
    rate={'EXCELLENT':70,'GOOD':50,'BAD':0}.get(status,0)
    item={'status':status,'win_rate':rate,'avg_return':2 if rate else 0,'count':24,'candidates':[]}
    return jsonify(vcp=item,closing_bet=item)


safe = {
    '/api/kr/market-gate':{'status':'GREEN','score':70,'message':'합성 시장','sectors':[]},
    '/api/kr/signals':{'signals':[{'ticker':'005930','name':'합성VCP','market':'KOSPI','signal_date':'2026-09-18','entry_price':100,'current_price':100,'stop_price':97,'target_price':105,'return_pct':0,'foreign_5d':1000,'inst_5d':500,'score':80,'vcp_score':17,'contraction_ratio':0.5}], 'count':1,'total_scanned':24,'generated_at':'2026-09-18T12:00:00'},
    '/api/kr/signals/dates':['2026-09-18'],
    '/api/kr/signals/status':{'is_running':False},
    '/api/kr/ai-analysis':{'signals':[]},
    '/api/kr/status':{'status':'success','data':{}},
    '/api/kr/config/interval':{'interval':60},
    '/api/kr/user/quota':{'remaining':10,'limit':10,'used':0},
    '/api/kr/chatbot/quota':{'remaining':10,'limit':10,'used':0},
    '/api/kr/chatbot/sessions':{'sessions':[]},
}
for i,(path,payload) in enumerate(safe.items()):
    app.add_url_rule(path,f'safe_{i}',lambda payload=payload:jsonify(payload))


@app.post('/__qa/control')
def qa_control():
    payload=request.get_json(silent=True) or {}
    if set(payload)-set(control):
        return jsonify(error='unknown fixture field'),400
    if 'mode' in payload and payload['mode'] not in ('normal','open','empty','paginated','small'):
        return jsonify(error='invalid fixture mode'),400
    if 'status' in payload and payload['status'] not in ('Accumulating','OK (New)','PENDING','EXCELLENT','GOOD','BAD','UNKNOWN'):
        return jsonify(error='invalid fixture status'),400
    if 'error' in payload and not isinstance(payload['error'],bool):
        return jsonify(error='invalid fixture error'),400
    control.update(payload)
    return jsonify(control)


@app.after_request
def record(response):
    with (STATE/'requests.jsonl').open('a') as output:
        output.write(json.dumps({'method':request.method,'path':request.path,'query':request.query_string.decode(),'status':response.status_code,'mode':control['mode'],'state':control['status']})+'\n')
    return response


if __name__ == '__main__':
    app.run(host='127.0.0.1',port=57612,threaded=True,use_reloader=False)
