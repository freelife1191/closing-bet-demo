import json,os,subprocess,sys,time,signal
from pathlib import Path
p=Path(__file__).resolve().parent;info=json.loads((p/'review-input.json').read_text());s=Path(info['scratch']);stage=sys.argv[1]
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ};env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(s/'tmp'),PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1',NPM_CONFIG_USERCONFIG='/dev/null',NPM_CONFIG_GLOBALCONFIG=str(s/'empty-npm-global'),NPM_CONFIG_CACHE=str(s/'npm-cache'),NPM_CONFIG_REGISTRY='https://registry.npmjs.org')
(s/'empty-npm-global').write_text('')
if stage=='upstream':
 cmd=[str(s/'venv/bin/python'),'-m','pip','install','--only-binary=:all:','--index-url','https://pypi.org/simple','numpy==2.4.6','pykrx==1.2.9'];cwd=s
elif stage=='candidate':
 v=s/'candidate-venv';subprocess.run(['sandbox-exec','-f',str(s/'qa.sb'),str(s/'venv/bin/python'),'-m','venv',str(v)],cwd=s,env=env,check=True,timeout=60)
 cmd=[str(v/'bin/python'),'-m','pip','install','--only-binary=:all:','--index-url','https://pypi.org/simple','--report',str(s/'install-report.json'),'-r','requirements.txt'];cwd=s
elif stage=='npm':cmd=['npm','ci','--ignore-scripts','--no-audit','--no-fund'];cwd=s/'frontend'
else:raise ValueError(stage)
start=time.monotonic()
with (p/(stage+'-install.log')).open('w') as f:
 proc=subprocess.Popen(['sandbox-exec','-f',str(s/'install.sb'),*cmd],cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=proc.wait(timeout=300)
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=124
(p/(stage+'-install.json')).write_text(json.dumps({'command':cmd,'exit_code':code,'elapsed':round(time.monotonic()-start,2)},indent=2)+'\n');print(stage,code)
if code==0 and stage=='candidate':
 info['execution_venv']=str(s/'candidate-venv');(p/'review-input.json').write_text(json.dumps(info,indent=2)+'\n');(p/'install-report.json').write_text((s/'install-report.json').read_text())
sys.exit(code)
