import {test, expect, type Page} from '@playwright/test';

async function login(page:Page, role='admin') {
  await page.goto('/crm');
  await page.getByLabel('Email manzil').fill(`${role}@e2e.test`);
  await page.getByLabel('Parol', {exact:true}).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button',{name:'Tizimga kirish'}).click();
  await expect(page.getByRole('heading',{name:'Boshqaruv paneli'})).toBeVisible();
}

async function chooseAvailableUnit(page:Page) {
  const response=await page.request.get('/api/public/units');
  const {units}=await response.json();
  expect(units.length).toBe(process.env.E2E_DEMO_COPY==='1'?84:1);
  const unit=units.find((u:{status:string})=>u.status==='available');
  expect(Boolean(unit)).toBe(true);
  await page.goto('/apartments');
  await page.locator('.building-choices').getByRole('button',{name:`${unit.building}-bino`}).click();
  await page.locator('.floor-grid').getByRole('button',{name:String(unit.floor),exact:true}).click();
  await page.locator('.unit-card').filter({hasText:`№ ${unit.unit}`}).click();
}

test('public landing, apartment selector and anonymous CRM',async({page})=>{
  await page.goto('/');
  await expect(page.locator('h1')).toBeVisible();
  await chooseAvailableUnit(page);
  await expect(page.getByRole('button',{name:'Murojaat qoldirish'})).toBeEnabled();
  const status=await page.evaluate(async()=> (await fetch('/api/crm/leads')).status);
  expect(status).toBe(401);
  await page.goto('/crm');
  await expect(page.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
});

test('wrong password, login, reload refresh, logout and token revocation',async({page,context})=>{
  await page.goto('/crm');
  await page.getByLabel('Email manzil').fill('admin@e2e.test');
  await page.getByLabel('Parol',{exact:true}).fill('incorrect-test-password');
  const rejected=page.waitForResponse(r=>r.url().endsWith('/api/auth/login'));
  await page.getByRole('button',{name:'Tizimga kirish'}).click();
  expect((await rejected).status()).toBe(401);
  await expect(page.getByRole('alert')).toBeVisible();
  const accepted=page.waitForResponse(r=>r.url().endsWith('/api/auth/login'));
  await login(page);
  const oldAccess=(await (await accepted).json()).access_token;
  const first=(await context.cookies()).find(c=>c.name==='qurlish_refresh')!;
  expect(first.httpOnly).toBe(true);
  expect(first.sameSite).toBe('Strict');
  expect(await page.evaluate(()=>document.cookie.includes('qurlish_refresh'))).toBe(false);
  expect(await page.evaluate(()=>localStorage.length+sessionStorage.length)).toBe(0);
  await page.reload();
  await expect(page.getByRole('heading',{name:'Boshqaruv paneli'})).toBeVisible();
  const rotated=(await context.cookies()).find(c=>c.name==='qurlish_refresh')!;
  expect(rotated.value!==first.value).toBe(true);
  const loggedOut=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
  await page.getByRole('button',{name:'Chiqish',exact:true}).click();
  expect((await loggedOut).status()).toBe(200);
  await expect(page.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
  const revoked=await page.evaluate(async(token)=> (await fetch('/api/crm/me',{headers:{Authorization:`Bearer ${token}`}})).status,oldAccess);
  expect(revoked).toBe(401);
  expect((await context.cookies()).some(c=>c.name==='qurlish_refresh')).toBe(false);
  await page.reload();
  await expect(page.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
});

test('Viewer controls and server permissions',async({page})=>{
  const accepted=page.waitForResponse(r=>r.url().endsWith('/api/auth/login'));
  await login(page,'viewer');
  const token=(await (await accepted).json()).access_token;
  await page.getByRole('button',{name:'Mijozlar',exact:true}).click();
  await expect(page.locator('.table-stage').first()).toBeDisabled();
  await page.getByRole('button',{name:'Batafsil'}).first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.locator('#staff-note')).toHaveCount(0);
  const status=await page.evaluate(async(token)=> (await fetch('/api/crm/leads/1/stage',{method:'PATCH',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({stage:'contacted'})})).status,token);
  expect(status).toBe(403);
});

test('two tabs serialize refresh and propagate logout',async({page,context})=>{
  await login(page);
  const second=await context.newPage();
  await second.goto('/crm');
  await expect(second.getByRole('heading',{name:'Boshqaruv paneli'})).toBeVisible();
  const responses:number[]=[];
  for(const tab of [page,second])tab.on('response',r=>{if(r.url().endsWith('/api/auth/refresh'))responses.push(r.status())});
  await Promise.all([page.reload(),second.reload()]);
  for(const tab of [page,second])await expect(tab.getByRole('heading',{name:'Boshqaruv paneli'})).toBeVisible();
  expect(responses).toEqual([200,200]);
  const done=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
  await page.getByRole('button',{name:'Chiqish',exact:true}).click();
  expect((await done).status()).toBe(200);
  for(const tab of [page,second])await expect(tab.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
});

test('pending refresh cannot restore a logged-out tab',async({page,context})=>{
  await login(page);
  const second=await context.newPage();
  let received!:()=>void, release!:()=>void;
  const waiting=new Promise<void>(resolve=>{received=resolve});
  const resume=new Promise<void>(resolve=>{release=resolve});
  await second.route('**/api/auth/refresh',async route=>{
    const response=await route.fetch();
    received();
    await resume;
    await route.fulfill({response});
  });
  await second.goto('/crm');
  await waiting;
  const invalidated=second.evaluate(()=>new Promise<void>(resolve=>window.addEventListener('crm:unauthorized',()=>resolve(),{once:true})));
  const done=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
  await page.getByRole('button',{name:'Chiqish',exact:true}).click();
  await invalidated;
  release();
  expect((await done).status()).toBe(200);
  await expect(second.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
  await second.reload();
  await expect(second.getByRole('button',{name:'Tizimga kirish'})).toBeVisible();
});

test('parallel API 401 responses share one refresh and retry',async({page})=>{
  await login(page);
  await expect(page.locator('.kpi').first()).toBeVisible();
  const rejected=new Set<string>();
  await page.route('**/api/crm/*?days=*',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(!rejected.has(path)){
      rejected.add(path);
      await route.fulfill({status:401,contentType:'application/json',body:'{"detail":"test expiry"}'});
    }else await route.continue();
  });
  let refreshes=0;
  page.on('request',r=>{if(r.url().endsWith('/api/auth/refresh'))refreshes++});
  await page.getByRole('button',{name:'Ma’lumotni yangilash'}).click();
  await expect(page.locator('.kpi').first()).toBeVisible();
  expect(rejected.size).toBe(2);
  expect(refreshes).toBe(1);
});

test('Vite proxy preserves the Origin security check',async({request})=>{
  const response=await request.post('/api/auth/logout',{headers:{Origin:'http://127.0.0.1:5999','Sec-Fetch-Site':'same-site'}});
  expect(response.status()).toBe(403);
});

test('legacy staff page keeps Viewer read-only and logs out',async({page})=>{
  await page.goto(new URL('/staff', process.env.E2E_API_URL || 'http://127.0.0.1:8000').href);
  await page.getByLabel('Email',{exact:true}).fill('viewer@e2e.test');
  await page.getByLabel('Parol',{exact:true}).fill(process.env.E2E_PASSWORD!);
  await page.getByRole('button',{name:'Kirish',exact:true}).click();
  await expect(page.locator('#workspace')).toBeVisible();
  await expect(page.locator('#who')).toContainText('viewer');
  await page.locator('#list-btn').click();
  await expect(page.locator('.stage-select').first()).toBeDisabled();
  await expect(page.locator('#note-form')).toBeHidden();
  const done=page.waitForResponse(r=>r.url().endsWith('/api/auth/logout'));
  await page.locator('#logout').click();
  expect((await done).status()).toBe(200);
  await expect(page.locator('#login')).toBeVisible();
});

test('public lead submission reaches dashboard and Kanban stage changes persist',async({page})=>{
  const name='E2E yakuniy murojaat';
  await chooseAvailableUnit(page);
  await page.getByRole('button',{name:'Murojaat qoldirish'}).click();
  await page.getByLabel('Ism-familiyangiz').fill(name);
  await page.getByLabel('Telefon raqamingiz').fill('+998900000002');
  const created=page.waitForResponse(r=>r.url().endsWith('/api/public/leads'));
  await page.getByRole('button',{name:'Murojaat yuborish'}).click();
  expect((await created).status()).toBe(201);
  await expect(page.locator('.success-message')).toBeVisible();
  await login(page,'seller');
  await expect(page.locator('.recent-list')).toContainText(name);
  await page.getByRole('button',{name:/Savdo Kanban/}).click();
  const tile=page.locator('.lead-tile').filter({hasText:name});
  await expect(tile).toBeVisible();
  const updated=page.waitForResponse(r=>r.url().includes('/stage')&&r.request().method()==='PATCH');
  await tile.locator('select').selectOption('contacted');
  expect((await updated).status()).toBe(200);
  await expect(page.locator('.kanban-column').filter({has:page.getByRole('heading',{name:/Bog‘lanilgan/})})).toContainText(name);
  await page.reload();
  await expect(page.getByRole('heading',{name:'Boshqaruv paneli'})).toBeVisible();
  await page.getByRole('button',{name:/Savdo Kanban/}).click();
  await expect(page.locator('.lead-tile').filter({hasText:name}).locator('select')).toHaveValue('contacted');
});
