import { test, expect } from '@playwright/test';

test('시작 전 과제 분리, 일반 기한 입력, 중앙 모달과 모바일 키보드 접근', async ({page}) => {
  await page.clock.install({time:new Date('2026-09-22T10:00:00+09:00')});
  await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'1',data:{id:'1'},exp:9999999999}}));
  const tasks = [
    {id:1,title:'진행할 과제',startTime:'2026-09-21T09:00:00+09:00',endTime:'2026-09-21T10:00:00+09:00',taskAvailableFrom:'2026-09-21T09:00:00+09:00',taskDueAt:'2026-09-24T09:00:00+09:00',status:'todo',type:'personal',completionSource:'manual'},
    {id:2,title:'시작 전 과제',startTime:'2026-09-24T09:00:00+09:00',taskAvailableFrom:'2026-09-24T09:00:00+09:00',taskDueAt:'2026-09-27T09:00:00+09:00',status:'todo',type:'integration',completionSource:'external'},
    {id:3,title:'이미 제출한 과제',startTime:'2026-09-21T09:00:00+09:00',taskDueAt:'2026-09-24T09:00:00+09:00',status:'done',type:'integration',completionSource:'external'}
  ];
  await page.route('**/api/personal/**',r=> {
    const path=new URL(r.request().url()).pathname;
    return r.fulfill({json:path.endsWith('/tasks')?tasks:path.includes('/daily-notes/')?{content:'',drawing:''}:[]});
  });
  await page.goto('/personal-project/calendar/day');
  await expect(page.getByRole('button',{name:/진행할 과제/})).toBeVisible();
  await expect(page.getByRole('button',{name:/시작 전 과제/})).not.toBeVisible();
  await expect(page.getByRole('button',{name:/이미 제출한 과제/})).toHaveCount(0);
  await page.getByText('아직 시작할 수 없는 할 일').click();
  await expect(page.getByRole('button',{name:/시작 전 과제/})).toBeVisible();
  await page.getByRole('button',{name:/진행할 과제/}).click();
  const box=(await page.getByRole('dialog').boundingBox())!;
  const viewport=page.viewportSize()!;
  expect(Math.abs(box.x+box.width/2-viewport.width/2)).toBeLessThan(2);
  await expect(page.getByLabel('할 일 마감')).toHaveValue('2026-09-24T09:00');
  await page.getByRole('dialog').getByRole('button',{name:'닫기',exact:true}).last().click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button',{name:'시간표',exact:true}).click();
  const slot=page.locator('.cw-slot').first();
  await slot.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toBeVisible();
});

test('주간 드래그 생성은 선택한 기간이며 새벽 범위는 02시에 끝난다', async ({page}) => {
  await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'1',data:{id:'1'},exp:9999999999}}));
  await page.route('**/api/personal/**',r=>r.fulfill({json:[]}));
  await page.goto('/personal-project/calendar/week');
  await expect(page.locator('.cw-slot')).toHaveCount(252);
  const slots=page.locator('.cw-column').first().locator('.cw-slot');
  const a=(await slots.nth(2).boundingBox())!, b=(await slots.nth(5).boundingBox())!;
  await page.mouse.move(a.x+20,a.y+10); await page.mouse.down();
  await page.mouse.move(b.x+20,b.y+10,{steps:8}); await page.mouse.up();
  await expect(page.getByRole('dialog')).toBeVisible();
  const start=await page.getByLabel('시작',{exact:true}).inputValue();
  const end=await page.getByLabel('종료',{exact:true}).inputValue();
  expect(+new Date(end)-+new Date(start)).toBe(2*3600000);
});
