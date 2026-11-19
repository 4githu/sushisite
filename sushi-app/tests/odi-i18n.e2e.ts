import { expect, test } from '@playwright/test';

test('language selection persists and presentation option values remain stable', async ({ page }) => {
  await page.route('**/auth/isjwt?key=mainauth', r => r.fulfill({json:{sub:'test',data:{id:'test',name:'Tester',email:'test@example.com'},exp:9999999999}}));
  await page.route('**/odi/db/login', r => r.fulfill({json:{user:{user_id:'test',auth_id:'test',config:{},created_at:'2026-01-01',updated_at:'2026-01-01'}}}));
  await page.goto('/odi/session/presentation', {waitUntil: 'networkidle'});
  await page.getByRole('button', {name:'English', exact:true}).click();
  await expect(page.getByRole('heading', {name:'Presentation details'}).first()).toBeVisible();
  const select = page.locator('select').first();
  await select.selectOption({label:'Share research'});
  await expect(select).toHaveValue('연구 결과 공유');
  await page.reload();
  await expect(page.getByRole('heading', {name:'Presentation details'}).first()).toBeVisible();
  await page.getByRole('button', {name:'Korean', exact:true}).click();
  await expect(page.getByRole('heading', {name:'발표 기본 정보'}).first()).toBeVisible();
});
