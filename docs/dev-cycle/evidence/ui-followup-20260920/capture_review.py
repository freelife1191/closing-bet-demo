#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,hashlib,gzip
E=Path(__file__).resolve().parent;R=E.parents[3]
M=json.loads((E/'review-input.json').read_text())
paths=set(subprocess.check_output(['git','diff','--name-only',M['base'],'--','frontend/src','app/routes','tests'],cwd=R,text=True).splitlines())
paths.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard','--','frontend/src','app/routes','tests'],cwd=R,text=True).splitlines())
M['files']={p:hashlib.sha256((R/p).read_bytes()).hexdigest() if (R/p).exists() else None for p in sorted(paths)}
M['requirements_sha256']=hashlib.sha256((E/'plan.md').read_bytes()).hexdigest()
(E/'review-input.json').write_text(json.dumps(M,ensure_ascii=False,indent=2)+'\n')
diff=subprocess.check_output(['git','diff','--no-ext-diff','-U5',M['base'],'--',*sorted(paths)],cwd=R,text=True)
for p in sorted(paths):
 if subprocess.run(['git','ls-files','--error-unmatch',p],cwd=R,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
  diff+='\nNEW FILE '+p+'\n'+(R/p).read_text()
(E/'review-diff.txt.gz').write_bytes(gzip.compress(diff.encode()))
(E/'review-diff.txt').write_text('\n'.join(line.rstrip() for line in diff.splitlines())+'\n')
print(json.dumps({'files':len(paths),'requirements_sha256':M['requirements_sha256']}))
