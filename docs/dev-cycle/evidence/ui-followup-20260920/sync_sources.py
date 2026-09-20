#!/usr/bin/env python3
"""Sync only this round's frontend source changes to its isolated archive."""
from pathlib import Path
import json, subprocess, shutil, hashlib
r=Path(__file__).resolve().parents[4];e=Path(__file__).resolve().parent;m=json.loads((e/'review-input.json').read_text());s=Path(m['scratch'])
changed=subprocess.check_output(['git','diff','--name-only',m['base'],'--','frontend/src','app/routes','tests'],cwd=r,text=True).splitlines()
new=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--','frontend/src','app/routes','tests'],cwd=r,text=True).splitlines()
for name in sorted(set(changed+new)):
 src=r/name;dst=s/name
 if src.exists():
  dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);m['files'][name]=hashlib.sha256(src.read_bytes()).hexdigest()
 else:
  if dst.exists():dst.unlink()
  m['files'][name]=None
(e/'review-input.json').write_text(json.dumps(m,indent=2)+'\n')
print('synced',len(m['files']),'source files')
