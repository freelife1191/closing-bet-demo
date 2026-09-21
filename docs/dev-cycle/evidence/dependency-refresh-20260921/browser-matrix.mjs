const task=await taskSpace(23),page=task.page('p1'),fs=await import('node:fs/promises');
const out='/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/dependency-refresh-20260921';
const results=[];
for(const mode of ['normal','legacy','raw','generated']) {
 await fetch('http://127.0.0.1:58002/__qa/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
 await page.goto('http://127.0.0.1:58000/dashboard/kr/vcp');
 await page.waitForSelector('text=VCP 검증',{timeout:30000});
 await page.snapshot();await page.click('text=VCP 검증',{label:'AI 상세 내용 확인'});
 await page.waitForSelector('text=AI 상세 분석',{timeout:10000});
 const tabs=[];
 for(const provider of (['legacy','raw'].includes(mode)?['Gemini']:['Gemini','GPT','Perplexity'])) {
  await page.snapshot();await page.click(`loc=role:button[name*="${provider}"]`,{label:`${provider} 분석 내용 확인`});
  const actual=await page.evaluate(()=>{const close=[...document.querySelectorAll('button[aria-label="차트 닫기"]')].find(e=>e.offsetParent!==null);const panel=close.parentElement.parentElement;return {text:panel.textContent,errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors};});
  if(actual.text.includes('주력 제품의 수출 호조세 지속')||actual.errors.length||actual.consoleErrors.length)throw Error(JSON.stringify({mode,provider,actual}));
  if(['legacy','raw'].includes(mode)&&!actual.text.includes('AI 분석 데이터 없음'))throw Error(JSON.stringify({mode,provider,actual}));
  if(['normal','generated'].includes(mode)&&!actual.text.includes('75%'))throw Error(JSON.stringify({mode,provider,actual}));
  tabs.push({provider,actual});
 }
 const raw=await page.fetch('/api/kr/ai-analysis'),merged=await page.fetch('/api/kr/signals');
 if(raw.status!==200||merged.status!==200||JSON.stringify([raw.body,merged.body]).includes('주력 제품의 수출 호조세 지속'))throw Error('API template leaked');
 await fs.writeFile(`${out}/ego-${mode}.txt`,await page.snapshot());await page.screenshot({path:`${out}/ego-${mode}.png`});
 results.push({mode,tabs,raw,merged});await fs.writeFile(`${out}/ego-matrix.json`,JSON.stringify(results,null,2));
}
const retired=await page.fetch('/api/kr/reanalyze/gemini',{method:'POST',headers:{'Content-Type':'application/json'},body:'{'});
if(retired.status!==410)throw Error(JSON.stringify(retired));
await fs.writeFile(`${out}/ego-retired.json`,JSON.stringify(retired,null,2));
console.log(results.map(r=>({mode:r.mode,tabs:r.tabs.length,passed:true})));console.log({retired:retired.status});console.log(await page.snapshot());

const invalidDates=[];
for(const date of ['../../../package','2026-02-30','','２０２６-０２-１１']) {
 const response=await page.fetch('/api/kr/ai-analysis?date='+encodeURIComponent(date));
 if(response.status!==400)throw Error(JSON.stringify(response));invalidDates.push({date,response});
}
await fs.writeFile(`${out}/ego-invalid-dates.json`,JSON.stringify(invalidDates,null,2));console.log({invalidDates:invalidDates.length,all400:true});
