import {test,expect} from '@playwright/test';
test('WebGL unavailable keeps the API catalogue usable',async({page})=>{
 await page.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=()=>null});
 await page.goto('/apartments');await page.getByRole('button',{name:'3D majmuani ochish'}).click();
 await expect(page.getByRole('status')).toContainText('2D katalog');await expect(page.locator('.unit-card').first()).toBeVisible();
});
test('API failure never fabricates inventory',async({page})=>{
 await page.route('**/api/public/units',r=>r.fulfill({status:503,json:{detail:'Sinov xatosi'}}));await page.goto('/apartments');
 await expect(page.getByRole('alert')).toContainText('API');await expect(page.locator('.unit-card')).toHaveCount(0);
});
test('sold and reserved units block enquiries',async({page})=>{
 const response=await page.request.get('/api/public/units');const {units}=await response.json();
 await page.route('**/api/public/units',r=>r.fulfill({json:{units:[{...units[0],status:'sold'},{...units[0],id:'reserved-fixture',unit:999,status:'reserved'}]}}));
 await page.goto('/apartments');for(const card of await page.locator('.unit-card').all()){await card.click();await expect(page.getByRole('button',{name:'Murojaat yopiq'})).toBeDisabled()}
});
test('retry preserves idempotency key and prevents double submission',async({page})=>{
 let keys:(string|undefined)[]=[];await page.route('**/api/public/leads',async r=>{keys.push(r.request().headers()['idempotency-key']);await r.fulfill({status:keys.length===1?503:200,json:keys.length===1?{detail:'Qayta urining'}:{id:999}})});
 await page.goto('/apartments');await page.locator('.unit-card').filter({hasText:'Bo‘sh'}).first().click();await page.getByRole('button',{name:'Murojaat qoldirish'}).click();await page.getByLabel('Ism-familiyangiz').fill('Sinov xaridor');await page.getByLabel('Telefon raqamingiz').fill('+998900000001');await page.getByRole('button',{name:'Murojaat yuborish'}).click();await expect(page.locator('.form-error')).toBeVisible();await page.getByRole('button',{name:'Murojaat yuborish'}).dblclick();await expect(page.getByRole('status')).toContainText('#999');expect(keys).toHaveLength(2);expect(keys[0]).toBeTruthy();expect(keys[0]).toBe(keys[1]);
});
test('3D loads only on request, renders and settles',async({page})=>{

 await page.goto('/apartments');expect(await page.locator('canvas').count()).toBe(0);await page.getByRole('button',{name:'3D majmuani ochish'}).click();await expect(page.locator('canvas')).toBeVisible();await page.getByRole('button',{name:'A-bino',exact:true}).first().click();await expect(page.getByRole('button',{name:'Xonadon kesimi'})).toBeDisabled();await page.locator('.unit-card').filter({hasText:'Bo‘sh'}).first().click();await expect(page.locator('.scene-note').first()).toContainText('Konsept kesim');await page.getByRole('button',{name:'1-xona',exact:true}).focus();await page.keyboard.press('Enter');await expect(page.getByRole('button',{name:'1-xona',exact:true})).toHaveAttribute('aria-pressed','true');await page.waitForTimeout(5000);const before=await page.locator('.scene-canvas').getAttribute('data-frames');await page.waitForTimeout(1000);expect(await page.locator('.scene-canvas').getAttribute('data-frames')).toBe(before);
});
