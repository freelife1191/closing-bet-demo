"""Install only into the proven owned venv, offline from verified PyPI wheels."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,signal,subprocess,time
p=Path(__file__).resolve().parent;s=Path(json.loads((p/'review-input.json').read_text())['scratch']);python=s/'venv/bin/python'
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ}
env.update(PATH=str(s/'venv/bin')+os.pathsep+env['PATH'],TMPDIR=str(s/'tmp'),PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1')
commands=[('install',['-m','pip','install','--only-binary=:all:','--no-cache-dir','--no-index','--find-links',str(s/'wheelhouse'),'--report',str(s/'pip-report.json'),'-r',str(s/'requirements.txt')],'qa.sb',300),('pip-check',['-m','pip','check'],'qa.sb',60)]
for stage,args,policy,limit in commands:
 start=time.monotonic()
 with (p/(stage+'.log')).open('w') as output:
  proc=subprocess.Popen(['sandbox-exec','-f',str(s/policy),str(python),*args],cwd=s,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=proc.wait(timeout=limit)
  except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait();code=124
 result={'stage':stage,'command':[str(python),*args],'exit_code':code,'timeout_seconds':limit,'elapsed_seconds':round(time.monotonic()-start,2),'completed_at':datetime.now(timezone.utc).isoformat()}
 (p/(stage+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 if code:raise SystemExit(code)
code='import sys,json,numpy,importlib.metadata as m;print(json.dumps({"prefix":sys.prefix,"numpy_file":numpy.__file__,"numpy_version":numpy.__version__,"pykrx_version":m.version("pykrx"),"numpy_requires_python":m.metadata("numpy").get("Requires-Python"),"pykrx_requires_dist":m.metadata("pykrx").get_all("Requires-Dist")}))'
raw=subprocess.check_output(['sandbox-exec','-f',str(s/'qa.sb'),str(python),'-c',code],cwd=s,env=env,text=True);obj=json.loads(raw)
assert Path(obj['prefix']).resolve()==s/'venv' and Path(obj['numpy_file']).resolve().is_relative_to(s/'venv')
assert obj['numpy_version']=='2.4.6' and obj['pykrx_version']=='1.2.7'
(p/'installed-metadata.json').write_text(json.dumps(obj,indent=2)+'\n');print(json.dumps(obj))

report=json.loads((s/"pip-report.json").read_text())
urls=[item["download_info"]["url"] for item in report["install"]]
from urllib.parse import urlsplit,unquote
assert all(urlsplit(url).scheme == "file" and Path(unquote(urlsplit(url).path)).resolve().is_relative_to(s/"wheelhouse") for url in urls)
(p/"pip-report.json").write_text(json.dumps(report,indent=2)+"\n")
