"""Clone source/dependencies into a relocatable, owned NumPy probe environment."""
from pathlib import Path
import hashlib,json,os,subprocess,tarfile,tempfile
r=Path.cwd();e=r/'docs/dev-cycle/evidence/dependency-refresh-20260921';s=Path(tempfile.mkdtemp(prefix='dependency-refresh-20260921-')).resolve()
archive=s/'source.tar';subprocess.run(['git','archive','--format=tar','-o',str(archive),'HEAD'],check=True)
with tarfile.open(archive) as t:t.extractall(s,filter='data')
archive.unlink();(s/'tmp').mkdir();nv=s/'venv';nv.mkdir()
for name in ['bin','lib','include','pyvenv.cfg']:
 src=r/'venv'/name
 if src.exists():subprocess.run(['cp','-cR',str(src),str(nv/name)],check=True)
assert (nv/'lib/python3.11/site-packages').resolve().is_relative_to(nv)
# Relocate Python entrypoint shebangs so even incidental child tools stay in the owned env.
old=str(r/'venv').encode();new=str(nv).encode()
for f in (nv/'bin').iterdir():
 if f.is_file() and not f.is_symlink():
  raw=f.read_bytes()
  if raw.startswith(b'#!'+old):f.write_bytes(raw.replace(old,new,1))
subprocess.run(['cp','-cR',str(r/'frontend/node_modules'),str(s/'frontend/node_modules')],check=True)
base='(version 1)\n(allow default)\n'+f'(deny file-write* (subpath "{r}"))\n'
for name in ['.env','.env.production','.env.vertex','data','logs','venv']:base+=f'(deny file-read* (subpath "{r/name}"))\n'
network='(deny network*)\n(allow network* (local ip "localhost:*") (remote ip "localhost:*"))\n(deny network* (remote ip "localhost:3500") (remote ip "localhost:5501"))\n'
(s/'qa.sb').write_text(base+network)
env={k:os.environ[k] for k in ['PATH','HOME','USER','LANG'] if k in os.environ};env.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(s/'tmp'))
code='import sys,numpy,pip,json;print(json.dumps({"prefix":sys.prefix,"numpy_file":numpy.__file__,"pip_file":pip.__file__,"numpy_version":numpy.__version__}))'
raw=subprocess.check_output(['sandbox-exec','-f',str(s/'qa.sb'),str(nv/'bin/python'),'-c',code],cwd=s,env=env,text=True);probe=json.loads(raw)
assert Path(probe['prefix']).resolve()==nv
assert all(Path(probe[k]).resolve().is_relative_to(nv) for k in ['numpy_file','pip_file'])
(s/'install.sb').write_text(base+'(deny network* (remote ip \"localhost:3500\") (remote ip \"localhost:5501\"))\n')
info={'base':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'scratch':str(s),'root_package_sha256':hashlib.sha256((r/'package.json').read_bytes()).hexdigest(),'venv_probe':probe}
(e/'review-input.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info))
