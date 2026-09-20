"""Copy only changed tracked files and this batch's explicitly allowed new sources."""
import json
from pathlib import Path
import shutil
import subprocess
root = Path(__file__).resolve().parents[4]
evidence = Path(__file__).resolve().parent
scratch = Path(json.loads((evidence/'review-input.json').read_text())['scratch'])
assert scratch.name.startswith('quota-ticker-20260921-') and not (scratch/'.git').exists()
changed = subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=root,text=True).splitlines()
new = subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
paths = changed + [p for p in new if p.startswith(('engine/','services/','frontend/src/','tests/','docs/dev-cycle/evidence/quota-ticker-20260921/','docs/dev-cycle/plans/2026-09-21-quota','docs/dev-cycle/qa/'))]
for relative in paths:
    assert not relative.startswith(('data/','.env'))
    src=root/relative; dst=scratch/relative
    if src.is_file():
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    elif dst.is_file(): dst.unlink()
print(json.dumps({'synced':len(paths),'scratch':str(scratch)}))
