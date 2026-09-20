import importlib.util,json
from pathlib import Path
p=Path.cwd();f=p/'docs/dev-cycle/evidence/ui-batch-20260920/fixture.py'
s=importlib.util.spec_from_file_location('ui_fixture',f);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.build_app(p,reset_log=True);c=a.test_client()
for path in ['/api/auth/session','/api/admin/check','/api/system/env','/api/kr/user/quota','/api/kr/jongga-v2/latest','/api/kr/signals','/api/portfolio','/api/system/data-status']:
 r=c.get(path);assert r.status_code==200,(path,r.status_code);assert r.is_json,path
for path in ['/api/auth/signout','/api/auth/signin/google','/api/system/env','/api/portfolio/buy','/api/kr/chatbot']:
 r=c.post(path);assert r.status_code==405,(path,r.status_code)
assert c.post('/__qa/control',json={'mode':'normal'}).status_code==200
assert c.get('/api/admin/check').json['isAdmin'] is False
print('fixture required GET and mutation boundaries PASS')

assert c.post('/__qa/control',json={'mode':'d-only'}).status_code==200
r=c.get('/api/kr/jongga-v2/latest').json
assert len(r['signals'])==1 and r['signals'][0]['grade']=='D'
assert c.post('/__qa/control',json={'mode':'zero'}).status_code==200
r=c.get('/api/kr/stock-detail/005930').json
assert 'investorTrend5Day' not in r and r['investorTrend']=={'institution':0,'individual':0}
assert c.post('/__qa/control',json={'mode':'admin'}).status_code==200
assert len(c.get('/api/system/env').json)==12
print('D-only, zero/missing, editable env fixture contracts PASS')
