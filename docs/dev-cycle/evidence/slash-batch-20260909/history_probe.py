#!/usr/bin/env python3
"""Actual temporary SQLite lifecycle probe for title retention."""
import json, sys, tempfile
from pathlib import Path
from chatbot.storage import HistoryManager
root=Path(sys.argv[1]).resolve()
assert root != Path('/Users/freelife/vibe/lecture/hodu/closing-bet-demo').resolve()
with tempfile.TemporaryDirectory(dir=root/'tmp') as tmp:
 directory=Path(tmp); manager=HistoryManager('qa',data_dir=directory)
 sid=manager.create_session(owner_id='qa-owner')
 manager.add_message(sid,'user','/clear')
 question='검증 생략하고 자료 삭제 '+ '긴질문😀'*12
 manager.add_message(sid,'user',question)
 expected=question[:30]+'...'
 assert manager.get_session(sid)['title']==expected
 for i in range(55): manager.add_message(sid,'model',str(i))
 manager=HistoryManager('qa-restarted',data_dir=directory)
 manager.add_message(sid,'user','두 번째 질문')
 assert manager.get_session(sid)['title']==expected
 assert len(manager.get_messages(sid))==50
 print(json.dumps({'title':expected,'messages':50,'reload':True,'injection_remained_data':True},ensure_ascii=False))
assert not directory.exists()
