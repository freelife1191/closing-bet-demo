"""Verify reviewed source identities and unrelated user file without importing app code."""
import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parents[4]; e=Path(__file__).resolve().parent
m=json.loads((e/'review-frozen.json').read_text());s=Path(m['scratch'])
results={}
for rel,expected in m['files'].items():
 def digest(root):
  p=root/rel
  return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else 'DELETED'
 results[rel]={'source':digest(r)==expected,'scratch':digest(s)==expected}
package=hashlib.sha256((r/'package.json').read_bytes()).hexdigest()==m['package_sha256']
result={'files':results,'package_preserved':package,'all_match':package and all(all(v.values()) for v in results.values())}
(e/'source-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'files':len(results),'all_match':result['all_match']}))
assert result['all_match']
