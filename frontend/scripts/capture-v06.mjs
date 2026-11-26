import {fileURLToPath} from 'node:url';
import {chromium} from '@playwright/test';
import fs from 'node:fs';
const phase=process.argv[2]||'before';
const base=process.env.CAPTURE_URL||'http://127.0.0.1:5173';
const dir=new URL(`../../docs/screenshots/v06/${phase}/`,import.meta.url);
fs.mkdirSync(dir,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  if(phase==='before'){
    const ref=await browser.newPage();
    try{await ref.goto('https://ux-ui-atlas-komiljon.komildjonxyz.chatgpt.site/',{waitUntil:'networkidle',timeout:25000});console.log('REFERENCE:',(await ref.locator('body').innerText()).slice(0,7000));}catch{console.log('REFERENCE: unreachable in Chrome');}
    await ref.close();
  }
  for(const width of [390,768,1440]){
    const context=await browser.newContext({viewport:{width,height:width===768?1024:900},reducedMotion:'reduce'});
    const page=await context.newPage();
    for(const [name,path] of [['landing','/'],['selector','/apartments']]){
      await page.goto(base+path,{waitUntil:'networkidle'});
      await page.screenshot({path:fileURLToPath(new URL(`${name}-${width}.jpg`,dir)),fullPage:true,type:'jpeg',quality:82});
      console.log(JSON.stringify({phase,name,width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)}));
    }
    // Synthetic display fixtures: no staff credentials or customer data captured.
    const leads=[{id:901,unit_id:'A-101',name:'Namuna xaridor',phone:'+998900000001',stage:'new',created_at:new Date().toISOString()}];
    await page.route('**/api/**',route=>{
      const path=new URL(route.request().url()).pathname;
      const user={id:901,email:'seller@visual.test',role:'seller'};
      const data=path.includes('/auth/')?{access_token:'visual-fixture',user,token_type:'bearer',expires_in:900}:path.endsWith('/me')?user:path.endsWith('/events')?[]:path.includes('metrics')?{days:30,count:1,stages:{new:1,contacted:0,qualified:0,closed_lost:0},bins:[0,0,0,0,0,0,1],unit_statuses:{available:64,reserved:10,sold:10},as_of:new Date().toISOString()}:{leads,days:30};
      return route.fulfill({json:data});
    });
    await page.goto(base+'/crm');
    await page.locator('.kpi').first().waitFor();
    await page.screenshot({path:fileURLToPath(new URL(`dashboard-${width}.jpg`,dir)),fullPage:true,type:'jpeg',quality:82});
    if(width===1440){
      await page.getByRole('button',{name:/Savdo Kanban/}).click();
      await page.screenshot({path:fileURLToPath(new URL(`kanban-${width}.jpg`,dir)),fullPage:true,type:'jpeg',quality:82});
      await page.locator('.lead-tile button').first().click();
      await page.getByRole('dialog').waitFor();
      await page.screenshot({path:fileURLToPath(new URL(`client-card-${width}.jpg`,dir)),fullPage:true,type:'jpeg',quality:82});
    }
    await context.close();
  }
}finally{await browser.close();}
