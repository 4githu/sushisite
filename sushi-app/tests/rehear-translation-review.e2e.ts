import { test, expect } from '@playwright/test';

test('reviewer edits a phrase with preview and sees published state', async ({page}) => {
  let version = 0; let overrides: Record<string,string> = {}; let reviewers: string[] = [];
  const entries = [{id:'nav:home',korean:'홈',english:'Home',section:'메뉴',path:'/odi'}, {id:'copy:닫기',korean:'닫기',english:'Close',section:'공통',path:'/odi'}];
  await page.route('**/rehear-translations**', async route => {
    const request = route.request();
    if (request.method() === 'POST') { const body = request.postDataJSON(); if (body.action === 'add-reviewer') { reviewers.push(body.email); await route.fulfill({json:{reviewers}}); } else { expect(body.version).toBe(version); version++; overrides[body.id] = body.english; await route.fulfill({json:{version,overrides}}); } }
    else if (request.url().includes('review=1')) await route.fulfill({json:{entries,version,overrides,email:'reviewer@example.com',reviewers}});
    else await route.fulfill({json:{version,overrides}});
  });
  await page.route('**/odi?review_preview=en', route => route.fulfill({contentType:'text/html',body:'<html><body><h1>Preview</h1></body></html>'}));
  await page.setViewportSize({width:1440,height:900});
  await page.goto('/translation-review');
  await expect(page.getByText('reviewer@example.com')).toBeVisible();
  await expect(page.getByTitle('Re:hear 사이트 미리보기')).toBeVisible();
  const row = page.locator('article').filter({hasText:'홈'});
  await row.getByLabel('영어').fill('Start page');
  await expect(page.getByText(/저장하지 않은 수정 1개/)).toBeVisible();
  await page.screenshot({path:'test-results/rehear-review-desktop.png'});
  await row.getByRole('button',{name:'저장하고 반영'}).click();
  await expect(row.getByRole('status')).toHaveText('사이트에 반영됐어요');
  await expect(row.getByRole('button',{name:'저장하고 반영'})).toBeDisabled();
  await page.reload();
  await expect(page.locator('article').filter({hasText:'홈'}).getByLabel('영어')).toHaveValue('Start page');
  await page.getByRole('button',{name:'검수자 관리'}).click();
  await page.getByLabel('이메일').fill('another@example.com');
  await page.getByRole('button',{name:'검수자 추가'}).click();
  await expect(page.getByRole('status').filter({hasText:'검수자를 추가했습니다.'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  await page.reload();
  await expect(page.getByRole('button',{name:'사이트 미리보기'})).toBeVisible();
  await page.screenshot({path:'test-results/rehear-review-mobile.png',fullPage:true});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('published copy updates an open site without changing the selected language', async ({page}) => {
  let published: Record<string,string> = {};
  await page.route('**/rehear-translations**', route => route.fulfill({json:{version:1,overrides:published}}));
  await page.route('**/auth/isjwt?key=mainauth', route => route.fulfill({json:{sub:'test',data:{id:'test',name:'Tester',email:'test@example.com'},exp:9999999999}}));
  await page.route('**/odi/db/login', route => route.fulfill({json:{user:{user_id:'test',auth_id:'test',config:{},created_at:'2026-01-01',updated_at:'2026-01-01'}}}));
  await page.route('**/odi/db/users/test/sessions?*', route => route.fulfill({json:{sessions:[]}}));
  await page.addInitScript(() => localStorage.setItem('rehear.locale','en'));
  await page.goto('/odi');
  await expect(page.getByRole('button',{name:'Home',exact:true})).toBeVisible();
  published = {'nav:home':'Start page'};
  await page.evaluate(() => { const sender = new BroadcastChannel('rehear-translation-updates'); sender.postMessage('updated'); sender.close(); });
  await expect(page.getByRole('button',{name:'Start page',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'English',exact:true})).toHaveAttribute('aria-pressed','true');
});
