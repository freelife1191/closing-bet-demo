#!/usr/bin/env python3
"""Owned integration fixture: real Flask routes/services, synthetic storage/auth/providers."""
import argparse, base64, hashlib, hmac, importlib, json, logging, os, time, uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from flask import Flask, Blueprint, g, jsonify, request
from app import _register_activity_logging
from app.routes.common_portfolio_routes import register_common_portfolio_routes
from app.routes.common_update_routes import _register_event_log_route
from app.routes.kr_market_chatbot_http_routes import _build_chatbot_activity_logger
from app.routes.kr_market_system_http_routes import _register_market_gate_routes
from services.kr_market_market_gate_validity import resolve_market_gate_filename, evaluate_market_gate_validity, apply_market_gate_snapshot_fallback, build_market_gate_empty_payload, normalize_market_gate_payload
from services.identity_helpers import verify_identity_header
import services.paper_trading as paper_module
ROOT=Path(__file__).resolve().parents[4]
assert not (ROOT/'.git').exists() and 'infra-read-boundaries-20260921-' in str(ROOT)
assert os.environ.get('PYTHON_DOTENV_DISABLED')=='1'
app=Flask('infra-boundaries-fixture');logger=logging.getLogger(__name__)
state={'gate':'normal','authenticated':True,'admin':False,'portfolio_error':False}
counters={'sync':0,'external':0,'updates':0,'constructors':[]};audit=[]
data_dir=ROOT/('qa-infra-'+uuid.uuid4().hex);data_dir.mkdir();log=data_dir/'requests.jsonl'
(ROOT/'qa-infra-current.json').write_text(json.dumps({'data_dir':str(data_dir),'request_log':str(log)}))
secret=os.environ['INTERNAL_IDENTITY_SECRET'];owner='alice@example.test';os.environ['ADMIN_EMAILS']='admin@example.test'
real_service=paper_module.PaperTradingService
writer=real_service(db_path=str(data_dir/'paper.sqlite3'),auto_start_sync=False)
assert writer.buy_stock('005930','검증 종목',70000,1,owner_id=owner)['status']=='success'
writer._persist_price_cache({'005930':71000})
def forbidden(*args,**kwargs):
 counters['external']+=1;raise AssertionError('External provider prohibited')
for name in ['_fetch_prices_toss','_fetch_prices_naver','_fetch_prices_yfinance','_fetch_prices_pykrx']:setattr(real_service,name,forbidden)
class FixturePaper(real_service):
 def __init__(self,**kwargs):
  counters['constructors'].append(kwargs.get('auto_start_sync',True));super().__init__(db_path=str(data_dir/'paper.sqlite3'),**kwargs)
 def start_background_sync(self):
  counters['sync']+=1;raise AssertionError('GET started sync')
paper_module.PaperTradingService=FixturePaper;paper_module._paper_trading_instance=None
sink=SimpleNamespace(log_action=lambda **kw:audit.append({'action':kw['action'],'ip':kw['ip_address']}))
importlib.import_module('services.activity_logger').activity_logger=sink
importlib.import_module('app.routes.common_update_routes')._ACTIVITY_LOGGER=sink
chat_log=_build_chatbot_activity_logger(logger)
@app.before_request
def boundary():
 allowed={'/__qa/control','/__qa/chat-log','/api/system/log-event','/api/kr/market-gate/update'}
 if request.method!='GET' and request.path not in allowed:return jsonify(error='fixture mutation prohibited'),405
 if request.path=='/api/portfolio' and state['portfolio_error']:return jsonify(error='합성 포트폴리오 조회 실패'),503
 if state['authenticated']:
  email='admin@example.test' if state['admin'] else owner
  encoded=base64.urlsafe_b64encode(email.encode()).decode().rstrip('=');prefix=f'v2.{encoded}.{int(time.time())+120}'
  path=base64.urlsafe_b64encode(request.path.encode()).decode().rstrip('=');mac=hmac.new(secret.encode(),f'{prefix}.{request.method}.{path}'.encode(),hashlib.sha256).hexdigest()
  request.environ['HTTP_X_AUTH_IDENTITY']=f'{prefix}.{mac}'
 g.user_email=verify_identity_header(request.headers.get('X-Auth-Identity'),method=request.method,path=request.path)
 g.session_id='qa-infra-session'
_register_activity_logging(app)
@app.after_request
def record(response):
 with log.open('a') as f:f.write(json.dumps({'method':request.method,'path':request.path,'status':response.status_code,'gate':state['gate']})+'\n')
 return response
ctx=SimpleNamespace(logger=logger,paper_trading=paper_module.paper_trading)
bp=Blueprint('portfolio',__name__);register_common_portfolio_routes(bp,ctx=ctx);_register_event_log_route(bp,ctx);app.register_blueprint(bp,url_prefix='/api')
def load_json(filename,**kwargs):
 if filename.startswith('jongga') or state['gate']=='empty':return {}
 return {'total_score':73,'status':'GREEN','dataset_date':'2020-01-01' if state['gate']=='stale' else datetime.now().strftime('%Y-%m-%d'),'timestamp':'2020-01-01T09:00:00' if state['gate']=='stale' else datetime.now().isoformat(),'sectors':[],'indices':{'kospi':{'value':2600,'change_pct':0.5},'kosdaq':{'value':800,'change_pct':0.2}}}
def update(target_date,logger):
 counters['updates']+=1;return 200,{'status':'success','synthetic':True}
mg=Blueprint('market_gate',__name__);_register_market_gate_routes(mg,logger=logger,deps={'resolve_market_gate_filename':resolve_market_gate_filename,'load_json_file':load_json,'evaluate_market_gate_validity':evaluate_market_gate_validity,'apply_market_gate_snapshot_fallback':apply_market_gate_snapshot_fallback,'build_market_gate_empty_payload':build_market_gate_empty_payload,'normalize_market_gate_payload':normalize_market_gate_payload,'execute_market_gate_update':update});app.register_blueprint(mg,url_prefix='/api/kr')
@app.post('/__qa/control')
def control():
 body=request.get_json() or {}
 for k in state:
  if k in body:state[k]=body[k]
 if 'price' in body:writer._persist_price_cache({'005930':int(body['price'])})
 return jsonify(state=state,counters=counters)
@app.get('/__qa/evidence')
def evidence():return jsonify(state=state,counters=counters,audit=audit)
@app.post('/__qa/chat-log')
def chat():
 chat_log(owner,'qa-infra-session','synthetic','검증','검증',{},False);return jsonify(ok=True)
@app.get('/api/auth/session')
def session():return jsonify(user={'name':'검증 사용자','email':owner},expires='2099-01-01T00:00:00Z')
@app.get('/api/admin/check')
def admin():return jsonify(isAdmin=False)
@app.get('/api/kr/user/quota')
@app.get('/api/kr/chatbot/quota')
def quota():return jsonify(usage=2,limit=10,remaining=8)
@app.get('/api/kr/config/interval')
def interval():return jsonify(interval=30)
@app.get('/api/kr/signals')
def signals():return jsonify(signals=[],total_scanned=0)
@app.get('/api/kr/status')
def status():return jsonify(status='ok',data={'last_update':None,'collected_stocks':0,'signals_count':0,'market_status':'closed','files':{}})
@app.get('/api/kr/backtest-summary')
def backtest():return jsonify(vcp={'win_rate':0,'avg_return':0,'count':0,'status':'UNKNOWN'},closing_bet={'win_rate':0,'avg_return':0,'count':0,'status':'UNKNOWN'})
@app.get('/api/kr/ai-analysis')
def ai():return jsonify(signals=[])
@app.get('/api/kr/signals/dates')
def dates():return jsonify([])
@app.get('/api/kr/signals/status')
def vcp_status():return jsonify(running=False,is_running=False,progress=0,message='idle')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True);parser.add_argument('--port',type=int,required=True);args=parser.parse_args()
 assert Path(args.repo).resolve()==ROOT and args.port==57972
 app.run(host='127.0.0.1',port=args.port,use_reloader=False,threaded=True)
