#!/usr/bin/env python3
"""Start only the manifest-owned, loopback, network-restricted QA processes."""
import json, os, socket, subprocess
from pathlib import Path
p=Path(__file__).resolve().parent
m=json.loads((p/'review-input.json').read_text()); scratch=Path(m['scratch'])
for port in (57501,57502):
 with socket.socket() as s: s.bind(('127.0.0.1',port))
env={k:os.environ[k] for k in ('PATH','HOME','USER','TMPDIR','LANG') if k in os.environ}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(scratch),PYTHON_DOTENV_DISABLED='1',TMPDIR=str(scratch/'tmp'),CI='true',API_URL='http://127.0.0.1:57502',NEXTAUTH_URL='http://127.0.0.1:57501',NEXTAUTH_SECRET='synthetic-local-qa-only')
commands=[('backend',[str(scratch/'venv/bin/python'),str(scratch/'docs/dev-cycle/evidence/slash-batch-20260909/fixture.py'),'--repo',str(scratch),'--reset-state','serve','--port','57502'],scratch),('frontend',['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','57501'],scratch/'frontend')]
started=[]
for name,cmd,cwd in commands:
 with (p/(name+'.log')).open('w') as log:
  child=subprocess.Popen(['sandbox-exec','-f',str(scratch/'qa.sb'),*cmd],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 started.append({'name':name,'pid':child.pid,'command':cmd,'cwd':str(cwd)})
(p/'processes.json').write_text(json.dumps(started,indent=2)+'\n')
print(json.dumps(started))
