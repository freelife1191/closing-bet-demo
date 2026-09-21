"""Launch exactly this batch's owned sandbox services, never original services."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
root=Path(__file__).resolve().parents[4]
e=Path(__file__).resolve().parent
s=Path(json.loads((e/'review-input.json').read_text())['scratch'])
assert s.name.startswith('jongga-metrics-20260921-') and s != root and not (s/'.env').exists()
kind=sys.argv[1]
port={'next':57951,'gateway':57950,'fixture':57952}[kind]
with socket.socket() as sock:
    assert sock.connect_ex(('127.0.0.1',port)) != 0, 'Port already occupied; do not stop existing owner'
env={k:os.environ[k] for k in ('PATH','HOME','USER','TMPDIR','LANG') if k in os.environ}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1',PYTHONPATH=str(s),TMPDIR=str(s/'tmp'),API_URL='http://127.0.0.1:57952',NEXTAUTH_URL='http://127.0.0.1:57950',NEXTAUTH_SECRET='synthetic-quota-fixture-secret',NEXT_TELEMETRY_DISABLED='1')
commands={
 'next':['node',str(s/'frontend/node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1','--port','57951'],
 'gateway':[str(s/'venv/bin/python'),str(s/'docs/dev-cycle/evidence/jongga-metrics-20260921/gateway.py')],
 'fixture':[str(s/'venv/bin/python'),str(s/'docs/dev-cycle/evidence/jongga-metrics-20260921/fixture.py'),'--repo',str(s),'--port','57952'],
}
cwd=s/'frontend' if kind=='next' else s
with (e/f'{kind}-runtime.log').open('a') as output:
 p=subprocess.Popen(['sandbox-exec','-f',str(s/'qa.sb'),*commands[kind]],cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
meta={'kind':kind,'pid':p.pid,'pgid':p.pid,'port':port,'cwd':str(cwd),'command':commands[kind]}
(e/f'{kind}-process.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta))
