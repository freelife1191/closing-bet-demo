#!/usr/bin/env python3
"""Synthetic transport; production parser executes only inside owned sandbox."""
import argparse, json
import numpy as np
import requests
from unittest.mock import patch
from numpy_json_encoder import NumpyEncoder
from pykrx import stock
from pykrx.website.comm import webio, auth
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, Blueprint, jsonify, request
import logging
from types import SimpleNamespace
from app.routes.kr_market_system_http_routes import _register_reanalyze_gemini_route
from app.routes.kr_market_data_ai_routes import _register_ai_analysis_route
from services.kr_market_ai_payload_service import build_ai_analysis_payload_for_target_date
from app.routes.kr_market_vcp_signal_helpers import _merge_ai_data_into_vcp_signals
from services.kr_market_ai_payload_service import _clone_payload_for_signal_normalization
from services import common_update_ai_analysis_service as svc
from engine import vcp_ai_analyzer as engine
from engine.kr_ai_templates import MockAnalysisTemplates
from engine.vcp_ai_analyzer_helpers import parse_json_response
ROOT=Path(__file__).resolve().parents[4]
assert not (ROOT/'.git').exists() and 'numpy-cookie-fix-20260921-' in str(ROOT)
transport_calls=[]
fake_auth=auth.KRXSession()
fake_auth.session.cookies.set('QA_SESSION','invented-nonsecret')
fake_auth.cookies={'QA_SESSION':{'value':'invented-nonsecret'}}
def naver_transport(adapter, prepared, **kwargs):
 assert prepared.url.startswith('http://fchart.stock.naver.com/sise.nhn')
 assert 'Cookie' not in prepared.headers and 'Authorization' not in prepared.headers
 transport_calls.append({'url':prepared.url,'cookie_present':False})
 response=requests.Response();response.status_code=200;response.url=prepared.url;response.request=prepared
 response._content=b'<protocol><chartdata><item data="20260901|70000|72000|69000|71000|1000"/></chartdata></protocol>'
 return response
with patch.object(webio,'get_session',return_value=fake_auth) as global_auth, patch.object(requests.adapters.HTTPAdapter,'send',naver_transport):
 frame=stock.get_market_ohlcv_by_date('20260901','20260901','005930')
 numpy_price=frame.iloc[0]['종가']
 assert int(numpy_price)==71000 and global_auth.call_count==0
(ROOT/'qa-numpy-flow.json').write_text(json.dumps({'numpy':np.__version__,'price':int(numpy_price),'price_type':type(numpy_price).__name__,'transport':transport_calls,'global_auth_calls':0,'external_requests':0}))
app=Flask('vcp-real-fixture'); state={'mode':'normal','chart_error':False}
bp=Blueprint('retired',__name__);_register_reanalyze_gemini_route(bp,logger=logging.getLogger('qa'),deps={});app.register_blueprint(bp,url_prefix='/api/kr')
log=ROOT/'qa-requests.jsonl'
@app.before_request
def boundary():
 if request.method!='GET' and request.path not in {'/__qa/control','/api/kr/realtime-prices','/api/kr/reanalyze/gemini'}:return jsonify(error='fixture mutation prohibited'),405
@app.after_request
def record(response):
 with log.open('a') as f:f.write(json.dumps({'method':request.method,'path':request.path,'status':response.status_code,'mode':state['mode']})+'\n')
 return response
@app.post('/__qa/control')
def control():
 data=request.get_json(); mode=data.get('mode',state['mode'])
 if mode not in {'normal','legacy','generated','raw'}:return jsonify(error='invalid mode'),400
 state.update(mode=mode,chart_error=bool(data.get('chart_error',False)));return jsonify(state)
calls=[]
model_reason='실측 검증용 합성 모델 응답입니다. 수급과 변동성 자료를 비교했으며 추가 거래량 확인이 필요합니다. 외부 모델은 호출하지 않았습니다.'
def generate_content(**kwargs):
 calls.append(kwargs['model']);return SimpleNamespace(text=json.dumps({'action':'HOLD','confidence':np.float32(75),'reason':model_reason},cls=NumpyEncoder))
engine.init_gemini_client=lambda *args:SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
engine.init_gpt_client=lambda *args:None
engine.init_zai_client=lambda *args:None
import os
os.environ['VCP_AI_PROVIDERS']='gemini';os.environ['VCP_SECOND_PROVIDER']=''
analyzer=engine.VCPMultiAIAnalyzer();svc.get_vcp_analyzer=lambda:analyzer
owned=ROOT/'qa-analysis';owned.mkdir(exist_ok=True)
today=datetime.now().strftime('%Y-%m-%d')
(owned/'signals_log.csv').write_text(f'signal_date,ticker,name,score,entry_price\n{today},005930,VCP 검증,85,71000\n')
result=svc.run_ai_analysis_step(target_date=today,selected_items=['AI Analysis'],vcp_df=None,update_item_status=lambda *args:None,shared_state=SimpleNamespace(STOP_REQUESTED=False),logger=logging.getLogger('qa'),data_dir=str(owned))
assert result['count']==1 and len(calls)==1
produced=json.loads((owned/'ai_analysis_results.json').read_text())['signals'][0]['gemini_recommendation']
before={p.name:p.read_bytes() for p in owned.glob('*.json')}
svc.run_async_analyzer_batch=lambda *args: {'005930': {'gemini_recommendation':None}}
failed=svc.run_ai_analysis_step(target_date=today,selected_items=['AI Analysis'],vcp_df=None,update_item_status=lambda *args:None,shared_state=SimpleNamespace(STOP_REQUESTED=False),logger=logging.getLogger('qa'),data_dir=str(owned))
assert failed['error'] and all(p.read_bytes()==before[p.name] for p in owned.glob('*.json'))
(ROOT/'qa-engine.json').write_text(json.dumps({'result':result,'model_transport_calls':len(calls),'external_requests':0,'failed_preserved':True,'failed':failed}))
def recommendation():
 if state['mode']=='generated':return produced
 if state['mode'] in {'legacy','raw'}:
  t=MockAnalysisTemplates;d=t.INVESTMENT_DRIVERS[0];r=t.RISK_FACTORS[0]
  h=t.HYPOTHESIS_TEMPLATES[0].format(name='VCP 검증',driver=d,risk=r)
  return {'action':'BUY','confidence':99,'reason':f'[핵심 투자 포인트]\n• {d}\n• {d}\n\n[리스크 요인]\n• {r}\n\n[종합 의견]\n{h}'}
 return {'action':'HOLD','confidence':np.float32(75),'reason':'K-칩스법과 수급 영향을 비교한 정상 분석입니다. 과거 템플릿의 전체 문장이 아닙니다.'}
def signal():
 row={'ticker':'005930','name':'VCP 검증','signal_date':datetime.now().strftime('%Y-%m-%d'),'score':85,'is_vcp':True,'entry_price':70000,'current_price':numpy_price,'return_pct':1.43,'contraction_ratio':0.6,'foreign_5d':1000,'inst_5d':500,'foreign_1d':100,'inst_1d':50,'market':'KOSPI','status':'ACTIVE','news':[]}
 row.update({f'{p}_recommendation':recommendation() for p in ['gemini','gpt','perplexity']});return json.loads(json.dumps(row,cls=NumpyEncoder))
@app.get('/api/kr/signals')
def signals():
 row=signal();source=dict(row)
 for p in ['gemini','gpt','perplexity']:row.pop(f'{p}_recommendation')
 if state['mode']!='raw':_merge_ai_data_into_vcp_signals([row],{'005930':source})
 return jsonify(signals=[row],total_scanned=1,source='synthetic',last_updated=datetime.now().isoformat())
ai_bp=Blueprint('ai_read',__name__)
_register_ai_analysis_route(ai_bp,logger=logging.getLogger('qa'),deps={
 'build_ai_analysis_payload_for_target_date':build_ai_analysis_payload_for_target_date,
 'load_json_file':lambda *a,**k:{},'build_ai_signals_from_jongga_results':lambda *a,**k:[],
 'normalize_ai_payload_tickers':lambda p:p,'should_use_jongga_ai_payload':lambda *a:False,
 'format_signal_date':str,
 'build_latest_ai_analysis_payload':lambda **k:_clone_payload_for_signal_normalization({'signals':[signal()],'signal_date':today,'generated_at':datetime.now().isoformat()})
})
app.register_blueprint(ai_bp,url_prefix='/api/kr')
@app.get('/api/kr/signals/dates')
def dates():return jsonify([datetime.now().strftime('%Y-%m-%d')])
@app.get('/api/kr/signals/status')
def status():return jsonify(running=False,is_running=False,progress=0,message='idle')
@app.get('/api/kr/market-gate')
def gate():return jsonify(score=70,label='중립',status='YELLOW',sectors=[])
@app.get('/api/kr/stock-chart/<ticker>')
def chart(ticker):
 if state['chart_error']:return jsonify(error='합성 차트 조회 실패'),503
 start=datetime(2026,8,1)
 return jsonify(ticker=ticker,data=[{'date':(start+timedelta(days=i)).strftime('%Y-%m-%d'),'open':70000+i*10,'high':72000+i*10,'low':69000+i*10,'close':71000+i*10,'volume':10000+i} for i in range(50)])
@app.get('/api/auth/session')
def session():return jsonify({})
@app.get('/api/admin/check')
def admin():return jsonify(isAdmin=False)
@app.get('/api/kr/user/quota')
@app.get('/api/kr/chatbot/quota')
def quota():return jsonify(usage=2,limit=10,remaining=8)
@app.get('/api/kr/config/interval')
def interval():return jsonify(interval=30)
@app.post('/api/kr/realtime-prices')
def prices():return jsonify(json.loads(json.dumps({'005930':numpy_price},cls=NumpyEncoder)))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True);parser.add_argument('--port',type=int,required=True);args=parser.parse_args()
 assert Path(args.repo).resolve()==ROOT and args.port==58012
 app.run(host='127.0.0.1',port=args.port,use_reloader=False,threaded=True)
