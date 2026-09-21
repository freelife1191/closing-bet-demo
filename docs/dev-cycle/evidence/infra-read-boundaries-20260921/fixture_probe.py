from fixture import app,counters,audit
client=app.test_client()
assert client.get('/api/portfolio').get_json()['holdings'][0]['current_price']==71000
client.post('/__qa/control',json={'price':72000})
assert client.get('/api/portfolio').get_json()['holdings'][0]['current_price']==72000
assert counters['sync']==0 and counters['external']==0 and counters['constructors']==[False]
for mode,score in [('normal',73),('stale',73),('empty',50)]:
 client.post('/__qa/control',json={'gate':mode})
 for query in ['', '?date=2026-09-01']:
  response=client.get('/api/kr/market-gate'+query);assert response.status_code==200 and response.get_json()['score']==score
assert counters['updates']==0
assert client.post('/api/kr/market-gate/update',json={}).status_code==403
client.post('/__qa/control',json={'admin':True})
assert client.post('/api/kr/market-gate/update',json={}).status_code==200
assert counters['updates']==1
client.post('/__qa/control',json={'admin':False})
client.post('/api/system/log-event',json={'action':'QA_EVENT','details':{}},headers={'X-Forwarded-For':'198.51.100.77'})
client.post('/__qa/chat-log',json={},headers={'X-Forwarded-For':'198.51.100.77'})
assert all(x['ip']=='127.0.0.1' for x in audit)
assert any(x['action']=='CHAT_MESSAGE' for x in audit)
assert any(x['action']=='QA_EVENT' for x in audit)
assert any(x['action']=='API_ACCESS' for x in audit)
client.post('/__qa/control',json={'authenticated':False})
assert client.get('/api/portfolio').status_code==401
assert counters['sync']==0 and counters['external']==0
print({'counters':counters,'audit_records':len(audit),'result':'PASS'})
