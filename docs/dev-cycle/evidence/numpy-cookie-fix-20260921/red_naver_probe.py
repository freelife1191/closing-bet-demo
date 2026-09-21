"""No-network reproduction with an invented cookie and a captured request boundary."""
import json
from types import SimpleNamespace
from unittest.mock import patch
import requests

captured=[]
xml='<protocol><chartdata><item data="20260101|70000|72000|69000|70000|1000"/><item data="20260102|70000|72000|69000|71000|1000"/></chartdata></protocol>'
with patch.object(requests.sessions.Session,'request',side_effect=AssertionError('External request prohibited')) as network:
 from pykrx import stock
 from pykrx.website.comm import webio,auth
 session=auth.KRXSession()
 session.cookies={'QA_SESSION':{'value':'invented-nonsecret-cookie'}}
 session.session=SimpleNamespace(get=lambda url,**kwargs:captured.append({'url':url,**kwargs}) or SimpleNamespace(text=xml))
 with patch.object(webio,'get_session',return_value=session):
  frame=stock.get_market_ohlcv_by_date('20260102','20260102','005930')
 assert frame.iloc[0]['종가']==71000
 assert network.call_count==0
 assert captured[0]['url']=='http://fchart.stock.naver.com/sise.nhn'
 assert 'Cookie' not in captured[0]['headers'], 'KRX Cookie leaked to Naver HTTP'
 print(json.dumps({'finding':'cross-origin cookie forwarding confirmed at captured transport boundary','request':captured[0],'close':int(frame.iloc[0]['종가']),'external_requests':network.call_count},ensure_ascii=False))
