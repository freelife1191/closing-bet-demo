#!/usr/bin/env python3
"""Observed UI actions only; HTTP writes are confined to synthetic fixture controls."""
import json,re,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
P=Path(__file__).resolve().parent
step=0
case=sys.argv[1]
scenario=case.removesuffix("-retry")

def ab(*args):
 global step
 step+=1
 label=f"vcp-{case}-{step:03d}"
 r=subprocess.run([sys.executable,str(P/'browser.py'),label,*args],text=True,capture_output=True,timeout=50)
 if r.returncode:raise RuntimeError(r.stdout+r.stderr)
 return r.stdout

def snap():return ab('snapshot','-i')
def ref(kind,name,last=False):
 lines=snap().splitlines(); matches=[]
 for line in lines:
  if re.match(r'\s*- '+kind+r' "',line) and name in line:
   m=re.search(r'ref=(e[0-9]+)',line)
   if m:matches.append('@'+m.group(1))
 assert matches,(kind,name,lines)
 return matches[-1] if last else matches[0]

def click(kind,name,last=False):ab('click',ref(kind,name,last))
def http(path,body=None,sid=None):
 headers={'Content-Type':'application/json'}
 if sid:headers['X-Session-Id']=sid
 request=urllib.request.Request('http://127.0.0.1:57602'+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
 try:
  with urllib.request.urlopen(request,timeout=15) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,json.load(e)

def control(**body):
 status,value=http('/__qa/control',body);assert status==200,value
 return value

def sid(ticker='005930'):
 return json.loads(ab('eval',f'localStorage.getItem("vcp_chat_session_id_{ticker}")').strip())

def history(session):return http('/api/kr/chatbot/history?session_id='+session,sid=session)
def idle():
 deadline=time.monotonic()+12
 while True:
  disabled=json.loads(ab('eval','document.querySelector(\'input[placeholder="AI에게 질문하기... (/ 명령어)"]\')?.disabled ?? true').strip())
  if not disabled:return
  assert time.monotonic()<deadline,'chat remains busy'
  time.sleep(.1)

def open_stock(name='삼성전자'):
 current=snap()
 if 'button "차트 닫기"' in current:
  click('button','차트 닫기');ab('wait','250')
 click('row',name);idle()

def begin_send(text):
 field=ref('textbox','AI에게 질문하기')
 ab('fill',field,text);ab('focus',ref('textbox','AI에게 질문하기'));ab('press','Enter')
def send(text):begin_send(text);idle();ab('snapshot')

def confirm():
 click('button','삭제',last=True);ab('wait','250');idle();ab('snapshot')

def delete_message(kind='질문',last=False):
 button=ref('button','이 '+kind+' 지우기',last)
 ab('hover',button);ab('click',ref('button','이 '+kind+' 지우기',last));confirm()

def delete_all():
 ab('focus',ref('button','대화 내역 비우기'));ab('press','Enter');ab('wait','250');confirm()
def ack_error():
 assert '대화 삭제 실패' in ab('snapshot')
 click('button','확인',last=True);ab('wait','250')

result={}
if scenario=='first-delete':
 open_stock();send('첫 질문 삭제 검수')
 session=sid();before=history(session);assert len(before[1]['history'])==2,before
 delete_message()
 after=history(session);assert [m['role'] for m in after[1]['history']]==['model'],after
 result={'before':before,'after':after,'session':session}
elif scenario=='message-errors':
 open_stock();send('메시지 오류 검수');session=sid();before=history(session)
 control(next_delete_error=500);delete_message();ack_error();assert history(session)==before
 control(stale_message_index={'session_id':session,'index':len(before[1]['history'])-1})
 delete_message('답변',True);assert sid()==session
 remaining=history(session);assert len(remaining[1]['history'])==len(before[1]['history'])-1
 control(real_session_missing=session);delete_message()
 assert sid() is None
 result={'preserved500':True,'valid404':remaining,'missing404_reset':True}
elif scenario=='conversation-errors':
 open_stock();send('대화 삭제 검수');session=sid();before=history(session)
 control(next_delete_error=500);delete_all();ack_error();assert history(session)==before
 control(real_session_missing=session);delete_all();assert sid() is None
 send('대화 삭제 성공 검수');session=sid();delete_all();assert sid() is None and history(session)[0]==404
 result={'preserved500':True,'reset404':True,'success200':True}
elif scenario=='clear-errors':
 open_stock();send('clear 오류 검수');session=sid();before=history(session)
 control(next_delete_error=500);send('/clear');ack_error();assert history(session)==before
 control(real_session_missing=session);send('/clear');assert sid() is None
 send('clear 성공 검수');session=sid();send('/clear');assert sid() is None and history(session)[0]==404
 result={'preserved500':True,'reset404':True,'success200':True}
elif scenario=='pending-repeat':
 open_stock();send('반복 삭제 검수');session=sid()
 scratch=Path(json.loads((P/'review-input.json').read_text())['scratch'])
 requests=scratch/'.qa-slash-fixture-state/requests-detailed.jsonl'
 def deletion_count():
  return sum(row.get('method')=='DELETE' and row.get('session_id')==session for row in (json.loads(line) for line in requests.read_text().splitlines()))
 before=deletion_count();control(delay_ms=3500);begin_send('/clear')
 observed=json.loads(ab('eval',"({inputDisabled:document.querySelector('input[placeholder=\"AI에게 질문하기... (/ 명령어)\"]').disabled,deleteDisabled:[...document.querySelectorAll('button[title*=\"지우기\"],button[title=\"대화 내역 비우기\"]')].every(b=>b.disabled)})"))
 assert observed['inputDisabled'] and observed['deleteDisabled'],observed
 ab('press','Enter');ab('press','Enter');idle();after=deletion_count()
 assert after-before==1,(before,after)
 assert sid() is None and history(session)[0]==404
 result={'pending':observed,'delete_count':after-before,'session_cleared':True}
elif scenario=='seed-50':
 open_stock();send('보관 한도 검수');session=sid()
 control(seed_pairs={'session_id':session,'count':26})
 open_stock();before=history(session);assert len(before[1]['history'])==50
 delete_message('답변',True)
 after=history(session);assert len(after[1]['history'])==49 and after[1]['history'][-1]['role']=='user'
 result={'before_count':50,'after_count':49,'last_role':'user','session':session}
elif scenario in ['delayed-post','delayed-clear','stream-switch']:
 open_stock('SK하이닉스');send('베타 보호 '+scenario);beta=sid('000660');before=history(beta)
 open_stock();send('알파 준비 '+scenario);alpha=sid()
 if scenario=='delayed-post':control(next_post_delay_ms=3500,post_session_id=alpha)
 elif scenario=='delayed-clear':control(delay_ms=3500)
 else:control(next_chat_delay_ms=3500)
 begin_send('/clear' if scenario=='delayed-clear' else '늦은 알파 '+scenario)
 if scenario=='stream-switch':
  ab('wait','200')
  observed=json.loads(ab('eval',"({inputDisabled:document.querySelector('input[placeholder=\"AI에게 질문하기... (/ 명령어)\"]').disabled,deleteDisabled:[...document.querySelectorAll('button[title*=\"지우기\"]')].every(b=>b.disabled)})"))
  assert observed['inputDisabled'] and observed['deleteDisabled'],observed
 open_stock('SK하이닉스');ab('wait','4000');idle()
 assert sid('000660')==beta and history(beta)==before
 rendered=ab('snapshot');assert '늦은 알파 '+scenario not in rendered
 alpha_after=history(alpha)
 if scenario=='delayed-clear':assert alpha_after[0]==404
 else:assert any('늦은 알파 '+scenario in str(row) for row in alpha_after[1]['history'])
 result={'beta_unchanged':True,'beta_session':beta,'alpha_completed':True,'alpha_status':alpha_after[0]}
else:raise RuntimeError('unknown case')
(P/('vcp-'+case+'-result.json')).write_text(json.dumps({'case':case,'pass':True,'evidence':result},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'case':case,'pass':True},ensure_ascii=False))
