import concurrent.futures,json,urllib.request
from pathlib import Path
p=Path(__file__).resolve().parent
ids=sorted({v['id'] for f in json.loads((p/'python-audit-before.json').read_text()) for v in f['vulns'] if v['id'].startswith('GHSA-')})
def fetch(i):
 with urllib.request.urlopen('https://api.osv.dev/v1/vulns/'+i,timeout=25) as r:return i,json.load(r)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:result=dict(pool.map(fetch,ids))
(p/'python-advisories.json').write_text(json.dumps(result,indent=2))
for i,d in result.items():
 for a in d.get('affected',[]):
  if a['package']['ecosystem']=='PyPI':print(json.dumps({'id':i,'package':a['package']['name'],'summary':d.get('summary'),'ranges':a.get('ranges')}))
