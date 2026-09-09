#!/usr/bin/env python3
"""Repeat observed form interactions with fresh agent-browser refs, not direct API sends."""
import json,re,subprocess,sys,time,urllib.request
from pathlib import Path
p=Path(__file__).resolve().parent

def ab(stage,*args):
 result=subprocess.run([sys.executable,str(p/'browser.py'),stage,*args],text=True,capture_output=True,timeout=50)
 if result.returncode: raise RuntimeError(result.stdout+result.stderr)
 return result.stdout

def state():
 with urllib.request.urlopen('http://127.0.0.1:57502/__qa/state',timeout=5) as response:
  return json.load(response)

def send(stage,text,expected):
 before=ab(stage+'-before','snapshot','-i')
 found=re.findall(r'textbox "메시지 입력[.]{3}" \[ref=(e[0-9]+)\]',before)
 assert len(found)==1,before
 ab(stage+'-fill','fill','@'+found[0],text)
 ready=ab(stage+'-ready','snapshot','-i')
 found=re.findall(r'button "보내기" \[ref=(e[0-9]+)\]',ready)
 assert len(found)==1,ready
 ab(stage+'-send','click','@'+found[0])
 deadline=time.monotonic()+6
 while True:
  current=state(); usage=sum(current['usage'].values())
  if usage==expected: break
  assert time.monotonic()<deadline,current
  time.sleep(.1)
 deadline=time.monotonic()+6
 while True:
  after=ab(stage+'-after','snapshot')
  counter=re.search(r'무료 사용량"\s*\n\s*- StaticText "([0-9]+)"',after)
  if counter and int(counter.group(1))==10-expected:break
  assert time.monotonic()<deadline,('visible quota mismatch',expected,after)
  time.sleep(.15)
 (p/(stage+'-state.json')).write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n')
 return after,current

mode=sys.argv[1]
if mode=='normal':
 for i,text in enumerate(['/status','/help','/status','/clear']):
  after,current=send('v3-command'+str(i),text,0)
  assert current['model_calls']==0
 after,current=send('v3-q1','첫 일반 질문 검수',1)
 assert current['sessions'][0]['title']=='첫 일반 질문 검수'
 after,current=send('v3-q2','두 번째 일반 질문 검수',2)
 assert current['sessions'][0]['title']=='첫 일반 질문 검수'
elif mode=='exhaust':
 for count in range(3,11):
  send('v3-q'+str(count),'한도 검수 질문 '+str(count),count)
 after,current=send('v3-exhaust-status','/status',10)
 assert current['model_calls']==10
 after,current=send('v3-denied','한도 초과 질문',10)
 assert current['model_calls']==10
 assert '초과' in after,after
else: raise RuntimeError(mode)
print(json.dumps({'mode':mode,'result':'pass','state':current},ensure_ascii=False))
