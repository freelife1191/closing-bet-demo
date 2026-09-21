"""Download only explicit, hash-verified PyPI wheels; never import project code."""
from pathlib import Path
from urllib.request import build_opener,ProxyHandler
from urllib.parse import urlsplit
import json,hashlib,platform
p=Path(__file__).resolve().parent;s=Path(json.loads((p/'review-input.json').read_text())['scratch']);dest=s/'wheelhouse';dest.mkdir(exist_ok=True)
assert platform.machine()=='arm64'
opener=build_opener(ProxyHandler({}))
def fetch(url):
 assert urlsplit(url).scheme=='https' and urlsplit(url).hostname in {'pypi.org','files.pythonhosted.org'}
 with opener.open(url,timeout=45) as response:
  assert urlsplit(response.url).hostname in {'pypi.org','files.pythonhosted.org'}
  return response.read()
records=[]
for name,version in [('numpy','2.4.6'),('pykrx','1.2.7')]:
 metadata=json.loads(fetch(f'https://pypi.org/pypi/{name}/{version}/json'))
 candidates=[x for x in metadata['urls'] if x['filename'].endswith('.whl') and (('cp311-cp311-macosx' in x['filename'] and 'arm64' in x['filename']) if name=='numpy' else 'py3-none-any' in x['filename'])]
 assert candidates, name
 item=sorted(candidates,key=lambda x:x['filename'])[0];raw=fetch(item['url']);sha=hashlib.sha256(raw).hexdigest();assert sha==item['digests']['sha256']
 (dest/item['filename']).write_bytes(raw)
 records.append({'name':name,'version':version,'filename':item['filename'],'url':item['url'],'sha256':sha,'requires_python':metadata['info']['requires_python'],'requires_dist':metadata['info']['requires_dist'],'bytes':len(raw)})
(p/'wheel-sources.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps([{k:r[k] for k in ['name','version','filename','bytes','sha256']} for r in records]))
