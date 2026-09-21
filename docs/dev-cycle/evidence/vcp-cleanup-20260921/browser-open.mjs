const task=await taskSpace(20),page=task.page('p1');
await page.cdp('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await page.goto('http://127.0.0.1:57960/dashboard/kr/vcp');
await page.waitForSelector('text=VCP 검증',{timeout:30000});
await page.evaluate(()=>{window.__qaErrors=[];window.__qaConsoleErrors=[];window.addEventListener('error',e=>window.__qaErrors.push(String(e.message)));window.addEventListener('unhandledrejection',e=>window.__qaErrors.push(String(e.reason)));const old=console.error;console.error=(...a)=>{window.__qaConsoleErrors.push(a.map(String).join(' '));old(...a);};});
console.log(await page.snapshot());
