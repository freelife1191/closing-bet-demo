"""Re-verify restored sources with an owned copy of the unchanged original dependencies."""
from pathlib import Path
import json,subprocess,shutil
r=Path.cwd();p=r/'docs/dev-cycle/evidence/numpy-upgrade-20260921';info=json.loads((p/'review-input.json').read_text());s=Path(info['scratch']);nv=s/'baseline-venv';nv.mkdir()
for name in ['bin','lib','include','pyvenv.cfg']:
 src=r/'venv'/name
 if src.exists():subprocess.run(['cp','-cR',str(src),str(nv/name)],check=True)
for f in (nv/'bin').iterdir():
 if f.is_file() and not f.is_symlink():
  raw=f.read_bytes()
  if raw.startswith(b'#!'+str(r/'venv').encode()):f.write_bytes(raw.replace(str(r/'venv').encode(),str(nv).encode(),1))
assert (nv/'lib/python3.11/site-packages').resolve().is_relative_to(nv)
for name in ['requirements.txt','numpy_json_encoder.py']:shutil.copy2(r/name,s/name)
for name in ['tests/test_numpy_encoder_compat.py','tests/engine/test_pykrx_numpy2_contract.py','tests/fixtures/pykrx_contract_probe.py']:
 f=s/name
 if f.exists():f.unlink()
info['execution_venv']=str(nv);info['candidate_venv']=str(s/'venv');(p/'review-input.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps({'execution_venv':str(nv),'candidate_venv':str(s/'venv')}))
