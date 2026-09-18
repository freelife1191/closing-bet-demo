import runpy,json,sys
namespace=runpy.run_path(sys.argv[1])
client=namespace['app'].test_client()
response=client.get('/api/kr/closing-bet/cumulative?limit=10&page=1')
payload=response.get_json()
print(json.dumps({'status':response.status_code,'payload':payload},ensure_ascii=False))
assert response.status_code == 200
assert payload['kpi']['totalSignals']==24 and payload['kpi']['totalRoi']==49
assert payload['kpi']['winRate']==66.7
assert len(payload['trades'])==10
assert payload['kpi']['roiByGrade']['D']['count']==6
assert payload['kpi']['roiByGrade']['D']['totalRoi']==9
assert payload['kpi']['recentWinRate']==30
assert payload['kpi']['recentClosedCount']==10
assert payload['kpi']['consecutiveLosses']==7
second=client.get('/api/kr/closing-bet/cumulative?limit=10&page=2').get_json()
assert second['kpi']==payload['kpi']
assert second['trades'] != payload['trades']
for mode in ['open','empty']:
 assert client.post('/__qa/control',json={'mode':mode}).status_code==200
 result=client.get('/api/kr/closing-bet/cumulative').get_json()
 assert result['kpi']['recentWinRate'] is None
 assert result['kpi']['recentClosedCount']==0
 assert result['kpi']['consecutiveLosses']==0
 assert result['kpi']['totalSignals']==(24 if mode=='open' else 0)
print('fixture product route/cache/metrics/page/open/empty PASS')
assert client.post('/__qa/control',json={'mode':'paginated'}).status_code==200
large=client.get('/api/kr/closing-bet/cumulative?limit=50&page=1').get_json()
last=client.get('/api/kr/closing-bet/cumulative?limit=50&page=2').get_json()
assert len(large['trades'])==50 and len(last['trades'])==10
assert large['kpi']==last['kpi']
assert large['kpi']['totalSignals']==60 and large['kpi']['totalRoi']==229
assert large['kpi']['recentWinRate']==30 and large['kpi']['consecutiveLosses']==7
print('native page sizes 50/10; full history recent 30/7 PASS')
assert client.post('/__qa/control',json={'mode':'small'}).status_code==200
small=client.get('/api/kr/closing-bet/cumulative').get_json()['kpi']
assert small['recentClosedCount']==2 and small['recentWinRate']==50 and small['consecutiveLosses']==1
print('small history sample2 /50%/loss1 PASS')
