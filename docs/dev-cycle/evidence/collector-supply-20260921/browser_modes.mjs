const task = await taskSpace(16);
const page = task.page("p1");
const fs = await import("node:fs/promises");
const out = "/Users/freelife/vibe/lecture/hodu/closing-bet-demo/docs/dev-cycle/evidence/collector-supply-20260921";
const prior = await page.evaluate(() => {
  const old = {errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors};
  window.__qaErrors=[];window.__qaConsoleErrors=[];
  return old;
});
await fs.writeFile(out+"/ego-cycle2-start.json",JSON.stringify(prior,null,2));
const results=[];
for (const [mode,expected,amount] of [["zero","0",0],["positive","+1억",100000000],["negative","-1억",-100000000],["missing","자료 없음",null],["invalid","자료 없음",null],["legacy","자료 없음",null]]) {
  await page.click('loc=css:button[aria-label="닫기"]',{label:"모달 닫고 조건 전환"});
  await page.waitForSelector('[role="dialog"]',{state:"hidden"});
  const control=await fetch("http://127.0.0.1:57942/__qa/control",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode})});
  if(!control.ok)throw new Error("Fixture control failed");
  await page.click("text=상세 분석 보기",{label:"수급 값 다시 조회"});
  await page.waitForFunction((expected)=>{
    const d=document.querySelector('[role="dialog"]');
    const label=d && [...d.querySelectorAll('div')].find(e=>e.textContent.trim()==="개인");
    return label?.parentElement.textContent.replace(/\s/g,"")===("개인"+expected.replace(/\s/g,"")) && getComputedStyle(d).opacity==="1";
  },expected,{timeout:10000});
  const observation=await page.evaluate(()=>{
    const d=document.querySelector('[role="dialog"]');
    const label=[...d.querySelectorAll('div')].find(e=>e.textContent.trim()==="개인");
    return {personal:label.parentElement.textContent.replace(/\s/g,""),errors:window.__qaErrors,consoleErrors:window.__qaConsoleErrors,foreignUnchanged:d.textContent.includes('+10억'),institutionUnchanged:d.textContent.includes('+5억')};
  });
  const api=await page.fetch("/api/kr/stock-detail/005930");
  const parsed=typeof api.body==="string"?JSON.parse(api.body):api.body;
  if(api.status!==200 || parsed.investorTrend.individual!==amount || !observation.foreignUnchanged || !observation.institutionUnchanged || !Array.isArray(observation.errors) || observation.errors.length || !Array.isArray(observation.consoleErrors) || observation.consoleErrors.length)throw new Error(JSON.stringify({mode,observation,api}));
  const screenshot=out+"/ego-"+mode+"-stable.png";
  await page.screenshot({path:screenshot});
  const row={mode,expected,amount,observation,httpStatus:api.status,actual:parsed.investorTrend.individual,screenshot};
  results.push(row);
  await fs.writeFile(out+"/ego-mode-"+mode+".json",JSON.stringify(row,null,2));
}
await fs.writeFile(out+"/ego-modes.json",JSON.stringify(results,null,2));
const snapshot=await page.snapshot();
await fs.writeFile(out+"/ego-final-modes-snapshot.txt",snapshot);
console.log(results);
console.log(snapshot);
