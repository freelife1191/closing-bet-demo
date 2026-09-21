import json,os,subprocess,sys
from pathlib import Path
p=Path(__file__).resolve().parent;s=Path(json.loads((p/'review-input.json').read_text())['scratch'])
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ}
env.update(NPM_CONFIG_USERCONFIG='/dev/null',NPM_CONFIG_GLOBALCONFIG=str(s/'empty-npm-global'),NPM_CONFIG_CACHE=str(s/'npm-cache'),NPM_CONFIG_REGISTRY='https://registry.npmjs.org',PYTHON_DOTENV_DISABLED='1')
r=subprocess.run(['sandbox-exec','-f',str(s/'install.sb'),'npm','audit','--package-lock-only','--ignore-scripts','--json'],cwd=s/'frontend',env=env,capture_output=True,text=True,timeout=120)
(p/('npm-audit-'+sys.argv[1]+'.json')).write_text(r.stdout)
(p/('npm-audit-'+sys.argv[1]+'.stderr')).write_text(r.stderr)
data=json.loads(r.stdout);print(json.dumps({'exit_code':r.returncode,'metadata':data.get('metadata'),'error':data.get('error'),'findings':[{k:v.get(k) for k in ['name','severity','range','fixAvailable','via']} for v in data.get('vulnerabilities',{}).values()]}))
