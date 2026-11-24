// Read-only business flows on the actual demo; auth writes are intentional.
import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';

const results={};
let browser, phase='browser_start';
try{
  browser=await chromium.launch({channel:'chrome',headless:true});
  const context=await browser.newContext();
  const page=await context.newPage();
  phase='landing';
  await page.goto('http://127.0.0.1:5173/');
  await page.locator('h1').waitFor({state:'visible'});
  results.landing='passed';
  phase='apartments';
  const inventory=await page.request.get('http://127.0.0.1:5173/api/public/units');
  assert.equal(inventory.status(),200);
  const {units}=await inventory.json();
  assert.equal(units.length,84);
  const unit=units.find(u=>u.status==='available');
  assert.ok(unit);
  await page.goto('http://127.0.0.1:5173/apartments');
  await page.locator('.building-choices').getByRole('button',{name:`${unit.building}-bino`}).click();
  await page.locator('.floor-grid').getByRole('button',{name:String(unit.floor),exact:true}).click();
  await page.locator('.unit-card').filter({hasText:`№ ${unit.unit}`}).click();
  assert.equal(await page.getByRole('button',{name:'Murojaat qoldirish'}).isEnabled(),true);
  results.apartments='passed, 84 units';
  phase='anonymous_crm';
  assert.equal((await page.request.get('http://127.0.0.1:5173/api/crm/leads')).status(),401);
  await page.goto('http://127.0.0.1:5173/crm');
  await page.getByRole('button',{name:'Tizimga kirish'}).waitFor({state:'visible'});
  results.anonymous_crm='401 and login screen';
  if(process.env.DEMO_ADMIN_EMAIL&&process.env.DEMO_ADMIN_PASSWORD){
    phase='existing_admin_login';
    await page.getByLabel('Email manzil').fill(process.env.DEMO_ADMIN_EMAIL);
    await page.getByLabel('Parol',{exact:true}).fill(process.env.DEMO_ADMIN_PASSWORD);
    const accepted=page.waitForResponse(r=>r.url().endsWith('/api/auth/login'));
    await page.getByRole('button',{name:'Tizimga kirish'}).click();
    const response=await accepted;
    assert.equal(response.status(),200);
    const token=(await response.json()).access_token;
    results.existing_admin_login='passed';
    phase='dashboard_kanban';
    await page.getByRole('heading',{name:'Boshqaruv paneli'}).waitFor({state:'visible'});
    await page.locator('.kpi').first().waitFor({state:'visible'});
    await page.getByRole('button',{name:/Savdo Kanban/}).click();
    await page.locator('.kanban-grid').waitFor({state:'visible'});
    results.dashboard_kanban='passed, no business data changed';
    phase='refresh';
    const renewed=page.waitForResponse(r=>r.url().endsWith('/api/auth/refresh'));
    await page.reload();
    assert.equal((await renewed).status(),200);
    await page.getByRole('heading',{name:'Boshqaruv paneli'}).waitFor({state:'visible'});
    results.refresh='passed';
    phase='logout';
    const loggedOut=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
    await page.getByRole('button',{name:'Chiqish',exact:true}).click();
    assert.equal((await loggedOut).status(),200);
    const status=await page.evaluate(async token=>(await fetch('/api/crm/me',{headers:{Authorization:`Bearer ${token}`}})).status,token);
    assert.equal(status,401);
    results.logout='passed; old token 401';
  }else{
    results.existing_admin_login='NOT VERIFIED: private password file absent';
    results.dashboard_kanban_refresh_logout='actual admin credentials required; isolated tests are separate';
  }
  console.log(JSON.stringify({status:'completed',results}));
}catch(error){
  // Playwright diagnostics may contain filled values; print only the failed phase.
  console.log(JSON.stringify({status:'failed',phase,error_type:error.name,results}));
  process.exitCode=1;
}finally{
  await browser?.close();
}
