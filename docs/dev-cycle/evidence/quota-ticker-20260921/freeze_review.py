"""Record exact review inputs, including new source and deleted modules."""
import hashlib,json,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[4]; e=Path(__file__).resolve().parent
paths=set(subprocess.check_output(['git','diff','--name-only','90c2256'],cwd=r,text=True).splitlines())
paths.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=r,text=True).splitlines())
paths=sorted(p for p in paths if p.startswith(('engine/','services/','app/','frontend/src/','tests/')))
info=json.loads((e/'review-input.json').read_text())
info['files']={p:hashlib.sha256((r/p).read_bytes()).hexdigest() if (r/p).exists() else 'DELETED' for p in paths}
info['plan_sha256']=hashlib.sha256((r/'docs/dev-cycle/plans/2026-09-21-quota-ticker-backtest.md').read_bytes()).hexdigest()
(e/'review-frozen.json').write_text(json.dumps(info,indent=2)+'\n')
(e/'review-diff.txt').write_bytes(subprocess.check_output(['git','diff','90c2256','--',*paths],cwd=r))
print(json.dumps({'source_files':len(paths),'evidence':str(e)}))
