const page=(await taskSpace(20)).page('p1'),fs=await import('node:fs/promises');
const out='/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/infra-read-boundaries-20260921';
const control=async body=>{const r=await fetch('http://127.0.0.1:57972/__qa/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error('control failed');return r.json();};
const parse=r=>typeof r.body==='string'?JSON.parse(r.body):r.body;
const close=async()=>{const snap=await page.snapshot();const id=snap.match(/button "닫기" \[ref=(\d+)/)?.[1];if(!id)throw Error('close ref');await page.click('@'+id,{label:'현재 포트폴리오 닫기'});await page.waitForSelector('loc=role:dialog[name="모의투자 포트폴리오"]',{state:'hidden'});};
await page.evaluate(()=>{window.__qaRequests=[];const original=window.fetch;window.fetch=async(...args)=>{const response=await original(...args);const url=String(args[0]);if(url.includes('/api/kr/market-gate')||url.includes('/api/portfolio'))response.clone().json().then(body=>window.__qaRequests.push({url,status:response.status,body}));return response;};});
const portfolio=[];
for (const [price,total] of [[71000,100001000],[72000,100002000]]) {
 if(price===72000){await control({price});await close();await page.snapshot();await page.click('loc=role:button[name*="모의투자"]',{label:'저장 가격 다시 조회'});}
 await page.waitForFunction(expected=>document.querySelector('[role="dialog"]')?.textContent.includes(expected),total.toLocaleString('en-US'),{timeout:10000});
 await page.snapshot();await page.click('loc=role:button[name*="보유 종목"]',{label:'실제 보유 가격 대조'});
 await page.waitForFunction(expected=>document.querySelector('[role="dialog"]')?.textContent.includes(expected),price.toLocaleString('en-US'),{timeout:10000});
 const api=await page.fetch('/api/portfolio'),body=parse(api);
 if(api.status!==200||body.holdings[0].current_price!==price||body.total_asset_value!==total)throw Error(JSON.stringify(body));
 const actual=await page.evaluate(()=>({text:document.querySelector('[role="dialog"]').textContent,errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors}));
 if(actual.errors?.length||actual.consoleErrors?.length)throw Error(JSON.stringify(actual));
 await fs.writeFile(`${out}/ego-portfolio-${price}.txt`,await page.snapshot());await page.screenshot({path:`${out}/ego-portfolio-${price}.png`});portfolio.push({price,total,api,actual});
}
await fs.writeFile(out+'/ego-portfolio.json',JSON.stringify(portfolio,null,2));await close();
const gates=[];
for(const [mode,score] of [['normal',73],['stale',73],['empty',50]]) {
 await control({gate:mode});const before=await page.evaluate(()=>window.__qaRequests.length);
 await page.snapshot();await page.click('loc=role:button[name*="날짜 지정"]',{label:'저장된 과거 자료 조회'});
 await page.waitForFunction(({before,score})=>window.__qaRequests.slice(before).some(r=>r.url.includes('/market-gate')&&r.body.score===score),{before,score},{timeout:10000});
 const second=await page.evaluate(()=>window.__qaRequests.length);
 await page.snapshot();await page.click('loc=role:button[name*="실시간"]',{label:'최신 저장 자료 조회'});
 await page.waitForFunction(({second,score})=>window.__qaRequests.slice(second).some(r=>r.url.includes('/market-gate')&&r.body.score===score),{second,score},{timeout:10000});
 const actual=await page.evaluate(()=>{const h=[...document.querySelectorAll('h3')].find(e=>e.offsetParent!==null&&e.textContent.includes('KR Market Gate'));return {text:h.parentElement.innerText,requests:window.__qaRequests,errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors};});
 if(!actual.text.includes(String(score))||actual.errors?.length||actual.consoleErrors?.length)throw Error(JSON.stringify(actual));
 const api=await page.fetch('/api/kr/market-gate');if(parse(api).score!==score)throw Error('gate score');
 await fs.writeFile(`${out}/ego-gate-${mode}.txt`,await page.snapshot());await page.screenshot({path:`${out}/ego-gate-${mode}.png`});gates.push({mode,score,api,actual});
}
await fs.writeFile(out+'/ego-gates.json',JSON.stringify(gates,null,2));
const before=parse(await page.fetch('/__qa/evidence'));if(before.counters.sync||before.counters.external||before.counters.updates||JSON.stringify(before.counters.constructors)!=='[false]')throw Error(JSON.stringify(before));
const bad=[];for(const date of ['../../../private','2026/09/21','2026-02-30','20260230','2026-9-21','','2026-09-21.json','２０２６０９２１']){const r=await page.fetch('/api/kr/market-gate?date='+encodeURIComponent(date));if(r.status!==400)throw Error('bad date accepted');bad.push({date,status:r.status,body:parse(r)});}
const event=await page.fetch('/api/system/log-event',{method:'POST',headers:{'Content-Type':'application/json','X-Forwarded-For':'198.51.100.77'},body:JSON.stringify({action:'QA_EVENT',details:{}})});
const chat=await page.fetch('/__qa/chat-log',{method:'POST',headers:{'Content-Type':'application/json','X-Forwarded-For':'198.51.100.77'},body:'{}'});
if(event.status!==200||chat.status!==200)throw Error('audit request');
const denied=await page.fetch('/api/kr/market-gate/update',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(denied.status!==403)throw Error('admin gate');
await control({admin:true});const allowed=await page.fetch('/api/kr/market-gate/update',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(allowed.status!==200)throw Error('admin preserved');await control({admin:false});
const after=parse(await page.fetch('/__qa/evidence'));if(after.counters.sync||after.counters.external||after.counters.updates!==1||after.audit.some(r=>r.ip!=='127.0.0.1'))throw Error(JSON.stringify(after));
for(const action of ['API_ACCESS','CHAT_MESSAGE','QA_EVENT'])if(!after.audit.some(r=>r.action===action))throw Error('missing audit '+action);
await fs.writeFile(out+'/ego-boundaries.json',JSON.stringify({before,bad,eventStatus:event.status,chatStatus:chat.status,deniedStatus:denied.status,allowedStatus:allowed.status,after},null,2));
console.log({portfolio:portfolio.map(p=>p.total),gates:gates.map(g=>[g.mode,g.score]),bad:bad.length,counters:after.counters,audit:after.audit.length});console.log(await page.snapshot());
