"""Stop only a recorded process group whose current cwd still proves ownership."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
e=Path(__file__).resolve().parent
kind=sys.argv[1];meta=json.loads((e/f'{kind}-process.json').read_text());pid=meta['pid']
try:
 pgid=os.getpgid(pid)
except ProcessLookupError:
 print(json.dumps({'kind':kind,'pid':pid,'already_exited':True}));sys.exit(0)
cwd=subprocess.check_output(['lsof','-a','-p',str(pid),'-d','cwd','-Fn'],text=True)
assert f"n{meta['cwd']}\n" in cwd, 'PID cwd identity changed; refusing signal'
assert pgid==meta['pgid']==pid, 'Process group identity changed'
os.killpg(pgid,signal.SIGTERM)
for _ in range(30):
 try: os.killpg(pgid,0)
 except ProcessLookupError:break
 time.sleep(.1)
else:os.killpg(pgid,signal.SIGKILL)
result={'kind':kind,'pid':pid,'pgid':pgid,'cwd_verified':True,'terminated':True}
(e/f'{kind}-stop-{pid}.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
