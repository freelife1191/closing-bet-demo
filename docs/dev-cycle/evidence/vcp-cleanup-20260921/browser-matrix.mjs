const task=await taskSpace(20),page=task.page('p1'),fs=await import('node:fs/promises');
const out='/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/vcp-cleanup-20260921';
const ready=await fetch('http://127.0.0.1:57962/api/kr/signals');if(ready.status!==200)throw Error('fixture not ready');
const results=[];
for(const [mode,expected] of [['normal','75%'],['invalid','미산출'],['zero','0%'],['raw','미산출']]) {
 await page.click('loc=role:button[name="차트 닫기"]',{label:'현재 상세 모달 닫기'});
 await page.waitForSelector('text=AI 상세 분석',{state:'hidden'});
 const c=await fetch('http://127.0.0.1:57962/__qa/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});if(!c.ok)throw Error('control');
 await page.snapshot();await page.click('loc=role:button[name="최신"]',{label:'합성 자료 다시 조회'});
 await page.waitForFunction(()=>[...document.querySelectorAll('td')].some(e=>e.textContent.includes('71,000')),null,{timeout:10000});
 await page.snapshot();await page.click('text=VCP 검증',{label:'세 AI 탭 비교'});
 await page.waitForSelector('text=AI 상세 분석',{timeout:10000});
 const tabs=[];
 for(const provider of ['GPT','Perplexity','Gemini']) {
  await page.snapshot();await page.click(`loc=role:button[name*="${provider}"]`,{label:`${provider} 확신도 확인`});
  await page.waitForFunction(expected=>[...document.querySelectorAll('span')].some(e=>e.textContent===expected),expected,{timeout:10000});
  const actual=await page.evaluate(()=>{const close=[...document.querySelectorAll('button[aria-label="차트 닫기"]')].find(e=>e.offsetParent!==null);const panel=close.parentElement.parentElement;return {text:panel.textContent,gauges:[...panel.querySelectorAll('span')].map(e=>e.textContent).filter(t=>/^(\d+%|미산출)$/.test(t)),errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors,timeOrigin:performance.timeOrigin};});
  if(!actual.gauges.includes(expected)||actual.errors.length||actual.consoleErrors.length)throw Error(JSON.stringify({mode,provider,expected,actual}));
  tabs.push({provider,expected,actual});
 }
 const api=await page.fetch('/api/kr/ai-analysis');if(api.status!==200)throw Error('api');
 await fs.writeFile(`${out}/ego-${mode}.txt`,await page.snapshot());await page.screenshot({path:`${out}/ego-${mode}.png`});
 results.push({mode,tabs,api});await fs.writeFile(`${out}/ego-matrix.json`,JSON.stringify(results,null,2));
}
console.log(results.map(r=>({mode:r.mode,tabs:r.tabs.map(t=>({provider:t.provider,gauges:t.actual.gauges})),status:r.api.status})));
console.log(await page.snapshot());
