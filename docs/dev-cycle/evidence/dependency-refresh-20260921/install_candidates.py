import json,os,signal,subprocess,sys,time
from pathlib import Path
p=Path(__file__).resolve().parent;info=json.loads((p/'review-input.json').read_text());s=Path(info['scratch']);kind=sys.argv[1]
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ}
env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(s/'tmp'),PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1',NPM_CONFIG_USERCONFIG='/dev/null',NPM_CONFIG_GLOBALCONFIG=str(s/'empty-npm-global'),NPM_CONFIG_CACHE=str(s/'npm-cache'),NPM_CONFIG_REGISTRY='https://registry.npmjs.org')
(s/'empty-npm-global').write_text('')
if kind=='python':
 candidate=s/'candidate-venv'
 subprocess.run(['sandbox-exec','-f',str(s/'qa.sb'),str(s/'venv/bin/python'),'-m','venv',str(candidate)],cwd=s,env=env,check=True,timeout=60)
 command=[str(candidate/'bin/python'),'-m','pip','install','--only-binary=:all:','--index-url','https://pypi.org/simple','--report',str(s/'python-install-report.json'),'-r','requirements.txt']
 cwd=s
else:command=['npm','update','--ignore-scripts','--no-audit','--no-fund'];cwd=s/'frontend'
start=time.monotonic()
with (p/(kind+'-install.log')).open('w') as out:
 proc=subprocess.Popen(['sandbox-exec','-f',str(s/'install.sb'),*command],cwd=cwd,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=proc.wait(timeout=300)
 except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=124
result={'command':command,'exit_code':code,'cwd':str(cwd),'seconds':round(time.monotonic()-start,2)}
(p/(kind+'-install.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if code==0 and kind=='python':
 info['execution_venv']=str(s/'candidate-venv');(p/'review-input.json').write_text(json.dumps(info,indent=2)+'\n')
 (p/'python-install-report.json').write_text((s/'python-install-report.json').read_text())
sys.exit(code)
