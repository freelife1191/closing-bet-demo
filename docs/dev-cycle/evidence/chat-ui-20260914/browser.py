#!/usr/bin/env python3
"""Bounded commands in one isolated agent-browser namespace."""
import json, os, subprocess, sys
from pathlib import Path
p=Path(__file__).resolve().parent
scratch=Path(json.loads((p/'review-input.json').read_text())['scratch'])
stage,*args=sys.argv[1:]
env={k:os.environ[k] for k in ('PATH','HOME','USER','TMPDIR','LANG') if k in os.environ}
command=['agent-browser','--headed','--namespace','chat-ui-20260914','--session','qa','--profile',str(scratch/'browser-profile'),'--allowed-domains','127.0.0.1','--proxy','http://127.0.0.1:9','--proxy-bypass','127.0.0.1','--args','--disable-background-networking',*args]
try:
 result=subprocess.run(command,env=env,timeout=45,text=True,capture_output=True)
 output=result.stdout+result.stderr; code=result.returncode
except subprocess.TimeoutExpired:
 output='browser command timed out';code=124
(p/(stage+'.txt')).write_text(output)
print(output)
sys.exit(code)
