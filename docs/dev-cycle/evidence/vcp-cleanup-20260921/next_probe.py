"""Owned Next MCP only; no discovery of original services."""
import json
from pathlib import Path
from urllib.request import Request,urlopen
p=Path(__file__).resolve().parent
req=Request('http://127.0.0.1:57961/_next/mcp',data=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list'}).encode(),headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'})
with urlopen(req,timeout=15) as r:body=r.read().decode()
(p/'next-tools-list.txt').write_text(body);print(body)
