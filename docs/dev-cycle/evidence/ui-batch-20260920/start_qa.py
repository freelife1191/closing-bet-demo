#!/usr/bin/env python3
"""Parent-owned isolated UI QA process startup."""
from pathlib import Path
import json,os,socket,subprocess,shutil
E=Path(__file__).resolve().parent
S=Path(json.loads((E/'review-input.json').read_text())['scratch'])
for port in (57620,57621,57622):
 with socket.socket() as sock:sock.bind(('127.0.0.1',port))
D=S/'docs/dev-cycle/evidence/ui-batch-20260920';D.mkdir(parents=True,exist_ok=True)
for name in ('fixture.py','gateway.py'):shutil.copy2(E/name,D/name)
env={key:os.environ[key] for key in ('PATH','HOME','USER','LANG') if key in os.environ}
env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(S/'tmp'),PYTHONPATH=str(S),CI='true',API_URL='http://127.0.0.1:57622',NEXTAUTH_URL='http://127.0.0.1:57620',NEXTAUTH_SECRET='ui-qa-only-synthetic')
commands=[('fixture',[str(S/'venv/bin/python'),str(D/'fixture.py'),'--repo',str(S),'--port','57622','--reset-log'],S),('frontend',['node','node_modules/next/dist/bin/next','dev','--hostname','127.0.0.1','--port','57621'],S/'frontend'),('gateway',[str(S/'venv/bin/python'),str(D/'gateway.py')],S)]
started=[]
for name,cmd,cwd in commands:
 with (E/(name+'-runtime.log')).open('w') as log:
  child=subprocess.Popen(['sandbox-exec','-f',str(S/'qa.sb'),*cmd],env=env,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 started.append({'name':name,'pid':child.pid,'command':cmd,'cwd':str(cwd)})
(E/'processes.json').write_text(json.dumps(started,indent=2)+'\n');print(json.dumps(started))
