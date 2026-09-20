#!/usr/bin/env python3
"""QA only: browser /api always reaches synthetic fixture, including auth."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import HTTPConnection
from urllib.parse import urlsplit
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[4]
assert not (ROOT/'.git').exists() and 'ui-qa-20260920-' in str(ROOT)
class Handler(BaseHTTPRequestHandler):
    def relay(self):
        path=urlsplit(self.path).path
        target=57622 if path.startswith('/api/') or path.startswith('/__qa/') else 57621
        body=self.rfile.read(int(self.headers.get('Content-Length',0)))
        headers={k:v for k,v in self.headers.items() if k.lower() not in ('host','cookie','authorization','connection','accept-encoding')}
        headers['Host']='127.0.0.1:57620'
        conn=HTTPConnection('127.0.0.1',target,timeout=60)
        try:
            conn.request(self.command,self.path,body,headers)
            res=conn.getresponse();payload=res.read()
            self.send_response(res.status)
            for key,value in res.getheaders():
                if key.lower() not in ('transfer-encoding','connection','content-length','set-cookie'):
                    self.send_header(key,value)
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            print(json.dumps({'method':self.command,'path':path,'status':res.status,'target':target}),flush=True)
        except (OSError,TimeoutError) as exc:
            self.send_error(502,'QA upstream unavailable')
            print(json.dumps({'path':path,'error':type(exc).__name__}),flush=True)
        finally:conn.close()
    do_GET=relay
    do_POST=relay
    do_DELETE=relay
    do_PUT=relay
    do_PATCH=relay
    def log_message(self,*args):pass
ThreadingHTTPServer(('127.0.0.1',57620),Handler).serve_forever()
