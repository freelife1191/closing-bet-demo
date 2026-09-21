import json,os,subprocess,urllib.request,sys
from pathlib import Path
p=Path(__file__).resolve().parent;s=Path(json.loads((p/'review-input.json').read_text())['scratch'])
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ};env['PYTHON_DOTENV_DISABLED']='1';env['PYTHONDONTWRITEBYTECODE']='1'
r=subprocess.run(['sandbox-exec','-f',str(s/'qa.sb'),str(Path(json.loads((p/'review-input.json').read_text())['execution_venv'])/'bin/python'),'-m','pip','list','--format=json','--disable-pip-version-check'],cwd=s,env=env,capture_output=True,text=True,timeout=30);r.check_returncode()
deps=json.loads(r.stdout);(p/('python-installed-'+sys.argv[1]+'.json')).write_text(json.dumps(deps,indent=2))
req=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps({'queries':[{'package':{'name':d['name'],'ecosystem':'PyPI'},'version':d['version']} for d in deps]}).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(req,timeout=60) as response:body=json.load(response)
findings=[{'package':d,'vulns':r['vulns']} for d,r in zip(deps,body['results']) if r.get('vulns')]
(p/('python-audit-'+sys.argv[1]+'.json')).write_text(json.dumps(findings,indent=2));print(json.dumps(findings))
