#!/usr/bin/env python3
"""Synthetic transport; production parser executes only inside owned sandbox."""
import argparse, json
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request
from engine.vcp_ai_analyzer_helpers import parse_json_response
ROOT=Path(__file__).resolve().parents[4]
assert not (ROOT/'.git').exists() and 'vcp-cleanup-20260921-' in str(ROOT)
app=Flask('vcp-cleanup-fixture'); state={'mode':'normal','chart_error':False}
log=ROOT/'qa-requests.jsonl'
@app.before_request
def boundary():
 if request.method!='GET' and request.path not in {'/__qa/control','/api/kr/realtime-prices'}:return jsonify(error='fixture mutation prohibited'),405
@app.after_request
def record(response):
 with log.open('a') as f:f.write(json.dumps({'method':request.method,'path':request.path,'status':response.status_code,'mode':state['mode']})+'\n')
 return response
@app.post('/__qa/control')
def control():
 data=request.get_json(); mode=data.get('mode',state['mode'])
 if mode not in {'normal','invalid','zero','raw'}:return jsonify(error='invalid mode'),400
 state.update(mode=mode,chart_error=bool(data.get('chart_error',False)));return jsonify(state)
def recommendation():
 value={'normal':'75%','invalid':'bad','zero':0,'raw':float('inf')}[state['mode']]
 return parse_json_response(json.dumps({'action':'HOLD','confidence':value,'reason':'합성 회귀 검증: 수급 흐름과 가격 변동을 비교한 결과입니다. 외부 AI를 호출하지 않은 화면 검사 자료입니다.'}))
def signal():
 row={'ticker':'005930','name':'VCP 검증','signal_date':datetime.now().strftime('%Y-%m-%d'),'score':85,'is_vcp':True,'entry_price':70000,'current_price':71000,'return_pct':1.43,'contraction_ratio':0.6,'foreign_5d':1000,'inst_5d':500,'foreign_1d':100,'inst_1d':50,'market':'KOSPI','status':'ACTIVE','news':[]}
 row.update({f'{p}_recommendation':recommendation() for p in ['gemini','gpt','perplexity']});return row
@app.get('/api/kr/signals')
def signals():
 row=signal()
 if state['mode']=='raw':
  for p in ['gemini','gpt','perplexity']:row.pop(f'{p}_recommendation')
 return jsonify(signals=[row],total_scanned=1,source='synthetic',last_updated=datetime.now().isoformat())
@app.get('/api/kr/ai-analysis')
def ai():return jsonify(signals=[signal()],signal_date=datetime.now().strftime('%Y-%m-%d'),generated_at=datetime.now().isoformat())
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
def prices():return jsonify({'005930':{'price':71000,'change_pct':1.43}})
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True);parser.add_argument('--port',type=int,required=True);args=parser.parse_args()
 assert Path(args.repo).resolve()==ROOT and args.port==57962
 app.run(host='127.0.0.1',port=args.port,use_reloader=False,threaded=True)
