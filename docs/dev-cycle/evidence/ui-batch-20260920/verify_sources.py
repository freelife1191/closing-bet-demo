#!/usr/bin/env python3
"""Verify reviewed source identities and the user's pre-existing untracked file."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[3]
M=json.loads((E/'review-input.json').read_text());S=Path(M['scratch'])
for name,expected in M['files'].items():
 for base in (R,S):
  p=base/name
  assert (hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None)==expected,(base,name)
assert hashlib.sha256((R/'package.json').read_bytes()).hexdigest()==M['root_package_sha256']
print(json.dumps({'source_files':len(M['files']),'original_and_scratch_match':True,'user_package_preserved':True}))
