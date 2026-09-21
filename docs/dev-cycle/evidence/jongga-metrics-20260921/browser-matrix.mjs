const task=await taskSpace(18),page=task.page('p1'),fs=await import('node:fs/promises');
const out='/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/jongga-metrics-20260921';
const results=[];
for (const [mode,bonus,total] of [['known',9,16],['legacy',8,15],['invalid',7,14]]) {
  await page.click('loc=css:button[aria-label="닫기"]',{label:'상세 모달 닫기'});
  await page.waitForSelector('[role="dialog"]',{state:'hidden'});
  const control=await fetch('http://127.0.0.1:57952/__qa/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode})});
  if(!control.ok)throw Error('Control failed');
  await page.snapshot();
  await page.click('loc=css:button[aria-label="선택한 날짜의 리포트 다시 불러오기"]',{label:'합성 리포트 다시 조회'});
  await page.waitForSelector(`text=+${bonus}${bonus>7?'점 (과거 저장값)':'/7'}`,{timeout:10000});
  const card=await page.evaluate(()=>{
    const caption=[...document.querySelectorAll('span')].find(e=>['저장 당시 총점','/ 19점'].includes(e.textContent.trim()));
    return {total:caption?.previousElementSibling.textContent,text:document.body.textContent};
  });
  if(card.total!==String(total))throw Error('Total changed '+JSON.stringify(card));
  await page.hover('text=보너스 (가산점)',{label:'보너스 기준 비교'});
  await page.waitForSelector('[role="tooltip"]',{timeout:5000});
  const bonusTooltip=await page.evaluate(()=>[...document.querySelectorAll('[role="tooltip"]')].map(e=>e.textContent).join(' '));
  if(bonus>7 && !bonusTooltip.includes('현재 항목별 상한을 적용하지 않습니다'))throw Error(bonusTooltip);
  await fs.writeFile(`${out}/ego-card-${mode}.txt`,await page.snapshot());
  await page.screenshot({path:`${out}/ego-card-${mode}.png`});
  await page.click('text=상세 분석 보기',{label:'기간과 부호 대조'});
  await page.waitForSelector('text=EPS 기준 기간 미확인',{timeout:10000});
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('[role="dialog"]')).opacity==='1',null,{timeout:5000});
  const snap=await page.snapshot();
  if(mode==='known') {
    const ref=snap.match(/text "PER"\s+container \[ref=(\d+)/)?.[1];
    if(!ref)throw Error('PER tooltip ref absent');
    await page.hover(ref,{label:'음수 PER 설명 확인'});
    await page.waitForFunction(()=>[...document.querySelectorAll('[role="tooltip"]')].some(e=>e.textContent.includes('음수 PER')),null,{timeout:5000});
  }
  const observed=await page.evaluate(()=>({text:document.querySelector('[role="dialog"]').textContent,tooltips:[...document.querySelectorAll('[role="tooltip"]')].map(e=>e.textContent),errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors}));
  const api=await page.fetch('/api/kr/stock-detail/005930');
  const body=typeof api.body==='string'?JSON.parse(api.body):api.body;
  if(api.status!==200||body.indicators.eps!==-266||body.financials.netIncome!==2600000000||!observed.text.includes('-266')||!observed.text.includes('26억')||observed.errors.length||observed.consoleErrors.length)throw Error(JSON.stringify({mode,observed,body}));
  if(mode==='known' && (body.financials.netIncomePeriod!=='2026Q1'||!observed.text.includes('기준: 2026Q1')||!observed.text.includes('기준: 2025')))throw Error('Period mismatch');
  if(mode!=='known' && (body.financials.netIncomePeriod!=null || (observed.text.match(/기준 기간 미확인/g)||[]).length!==4))throw Error('Unknown period mismatch');
  await fs.writeFile(`${out}/ego-detail-${mode}.txt`,await page.snapshot());
  await page.screenshot({path:`${out}/ego-detail-${mode}.png`});
  const row={mode,bonus,total,actualTotal:card.total,bonusTooltip,observed,api:{status:api.status,body}};
  results.push(row);await fs.writeFile(`${out}/ego-${mode}.json`,JSON.stringify(row,null,2));
}
await fs.writeFile(out+'/ego-matrix.json',JSON.stringify(results,null,2));
console.log(results.map(r=>({mode:r.mode,bonus:r.bonus,total:r.actualTotal,status:r.api.status,period:r.api.body.financials.netIncomePeriod,errors:r.observed.errors})));
