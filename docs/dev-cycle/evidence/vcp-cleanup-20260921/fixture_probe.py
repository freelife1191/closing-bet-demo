from fixture import app
client=app.test_client()
for mode,expected in [('normal',75),('invalid',None),('zero',0),('raw',None)]:
 assert client.post('/__qa/control',json={'mode':mode}).status_code==200
 data=client.get('/api/kr/ai-analysis').get_json()['signals'][0]
 assert all(data[p+'_recommendation']['confidence']==expected for p in ['gemini','gpt','perplexity'])
 print(mode,expected)
assert client.post('/api/system/env',json={}).status_code==405
