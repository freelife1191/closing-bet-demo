#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
E=Path(__file__).resolve().parent; R=E.parents[3]
M=json.loads((E/'review-input.json').read_text()); S=Path(M['scratch'])
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
mismatches=[p for p,h in M['files'].items() if digest(R/p)!=h or digest(S/p)!=h]
result={'source_count':len(M['files']),'mismatches':mismatches,
        'package_unchanged':digest(R/'package.json')==M['root_package_sha256'],
        'scratch_env_absent':all(not (S/name).exists() for name in ('.env','.env.production','.env.vertex'))}
(E/'source-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));sys.exit(0 if not mismatches and result['package_unchanged'] and result['scratch_env_absent'] else 1)
