#!/usr/bin/env python3
"""Sync approved tracked changes plus explicit new batch tests into owned scratch."""
from pathlib import Path
import json,subprocess,hashlib,shutil
R=Path(__file__).resolve().parents[4];E=Path(__file__).resolve().parent
M=json.loads((E/'review-input.json').read_text());S=Path(M['scratch'])
files=subprocess.check_output(['git','diff','--name-only',M['base']],cwd=R,text=True).splitlines()
files=[f for f in files if not f.startswith('docs/')]
files += [str(p.relative_to(R)) for p in (R/'tests').rglob('*storage_memory_batch*.py')]
files=sorted(set(files));assert 'package.json' not in files
for f in files:
 assert (R/f).is_file(),f;(S/f).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/f,S/f)
M['files']={f:hashlib.sha256((R/f).read_bytes()).hexdigest() for f in files}
(E/'review-current.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'count':len(files),'files':files}))
