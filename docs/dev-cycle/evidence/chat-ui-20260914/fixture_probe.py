#!/usr/bin/env python3
import importlib.util,json,sys
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
spec=importlib.util.spec_from_file_location('fixture_probe_app',repo/'docs/dev-cycle/evidence/chat-ui-20260914/fixture.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.validate_scratch_repo(str(repo));app=module.build_app(repo,reset_state=True);client=app.test_client()
owner='vcp_005930_probe';headers={'X-Session-Id':owner,'Accept':'text/event-stream'}
r=client.post('/api/kr/chatbot',json={'message':'합성 프로브'},headers=headers);assert r.status_code==200;r.get_data()
state=client.get('/__qa/state').get_json();sid=state['sessions'][0]['id']
r=client.post('/__qa/control',json={'seed_pairs':{'session_id':sid,'count':26},'next_chat_delay_ms':0});assert r.status_code==200,r.get_data()
url='/api/kr/chatbot/history?session_id='+sid
rows=client.get(url,headers=headers).get_json()['history'];assert len(rows)==50
assert client.post('/__qa/control',json={'next_delete_error':500}).status_code==200
assert client.delete(url+'&index=0',headers=headers).status_code==500
assert len(client.get(url,headers=headers).get_json()['history'])==50
assert client.delete(url+'&index=0',headers=headers).status_code==200
assert len(client.get(url,headers=headers).get_json()['history'])==49
print(json.dumps({'fixture':'pass','seed_limit':50,'injected_500_preserves':True,'actual_delete':49}))
