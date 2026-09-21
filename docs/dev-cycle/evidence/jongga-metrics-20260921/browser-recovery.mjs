const task=await taskSpace(18),page=task.page('p1'),fs=await import('node:fs/promises');
const out='/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/jongga-metrics-20260921';
const before=await page.evaluate(()=>performance.timeOrigin);
const results=[];
for(const mode of ['error','known']) {
 await page.click('loc=css:button[aria-label="닫기"]',{label:'상세 닫고 응답 전환'});
 await page.waitForSelector('[role="dialog"]',{state:'hidden'});
 const control=await fetch('http://127.0.0.1:57952/__qa/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});if(!control.ok)throw Error('Control');
 await page.snapshot();
 await page.click('text=상세 분석 보기',{label:mode==='error'?'조회 실패 표시 확인':'재조회 복구 확인'});
 await page.waitForSelector(mode==='error'?'text=합성 조회 실패':'text=EPS 기준 기간 미확인',{timeout:10000});
 await page.waitForFunction(()=>getComputedStyle(document.querySelector('[role="dialog"]')).opacity==='1',null,{timeout:5000});
 const observed=await page.evaluate(()=>({text:document.querySelector('[role="dialog"]').textContent,errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors,timeOrigin:performance.timeOrigin}));
 const api=await page.fetch('/api/kr/stock-detail/005930');
 if(api.status!==(mode==='error'?503:200)||observed.timeOrigin!==before||observed.errors.length||observed.consoleErrors.length)throw Error(JSON.stringify({mode,observed,status:api.status}));
 if(mode==='known'&&(!observed.text.includes('기준: 2026Q1')||!observed.text.includes('-266')))throw Error('Recovery mismatch');
 await fs.writeFile(`${out}/ego-recovery-${mode}.txt`,await page.snapshot());
 await page.screenshot({path:`${out}/ego-recovery-${mode}.png`});
 results.push({mode,status:api.status,observed});
}
await fs.writeFile(out+'/ego-recovery.json',JSON.stringify(results,null,2));console.log(results);
