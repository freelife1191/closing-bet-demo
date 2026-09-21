const task=await taskSpace(25),page=task.page('p1');
await page.cdp('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
await page.cdp('Page.addScriptToEvaluateOnNewDocument',{source:`window.__qaErrors=[];window.__qaConsoleErrors=[];window.addEventListener('error',e=>window.__qaErrors.push(String(e.message)));window.addEventListener('unhandledrejection',e=>window.__qaErrors.push(String(e.reason)));const qaOriginalError=console.error;console.error=(...args)=>{window.__qaConsoleErrors.push(args.map(String).join(' '));qaOriginalError(...args);};`});
await page.goto('http://127.0.0.1:58010/dashboard/kr/vcp');
await page.waitForSelector('text=VCP 검증',{timeout:30000});
console.log(await page.snapshot());
