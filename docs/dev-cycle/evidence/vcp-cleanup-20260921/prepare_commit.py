"""Stage owned implementation/static evidence; preserve live runtime logs and user files."""
from pathlib import Path
import gzip, hashlib, json, subprocess
p=Path(__file__).resolve().parent;r=p.parents[3]
files=list(json.loads((p/'review-frozen.json').read_text()))
for f,sha in json.loads((p/'review-frozen.json').read_text()).items():
 path=r/f;assert (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'deleted')==sha
index=json.loads((p/'raw-index.json').read_text())
for f in p.glob('*.log'):
 if 'runtime' in f.name:continue
 raw=f.read_bytes();z=f.with_name(f.name+'.gz');z.write_bytes(gzip.compress(raw,mtime=0));index[f.name]={'raw_sha256':hashlib.sha256(raw).hexdigest(),'archive':z.name};f.unlink()
for f in p.glob('review-diff*.txt'):
 raw=f.read_bytes();z=f.with_name(f.name+'.gz');z.write_bytes(gzip.compress(raw,mtime=0));index[f.name]={'raw_sha256':hashlib.sha256(raw).hexdigest(),'archive':z.name};f.unlink()
(p/'raw-index.json').write_text(json.dumps(index,indent=2)+'\n')
owned=[*files,'docs/dev-cycle/TODO.md','docs/dev-cycle/qa/VCP-005.md','docs/dev-cycle/qa/INFRA-008.md','docs/dev-cycle/qa/batch-vcp-cleanup-2026-09-21.md']
owned += [str(f.relative_to(r)) for f in p.iterdir() if f.is_file() and 'runtime' not in f.name]
tracked=set(subprocess.check_output(['git','ls-files'],cwd=r,text=True).splitlines())
owned=[f for f in owned if (r/f).exists() or f in tracked]
subprocess.run(['git','add','--',*owned],cwd=r,check=True)
subprocess.run(['git','diff','--cached','--check'],cwd=r,check=True)
