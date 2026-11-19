import { expect, test, type Page } from '@playwright/test';

const round = { id: 12, schoolId: 1, schoolName: '합성 학교', progressStage: 'grade1_semester1_midterm', eventId: 12, roundNumber: 1, roundNumbers: [1], roundLabel: '1회', startTime: '2026-10-10T10:00:00', endTime: '2026-10-10T11:00:00', amount: 30000, paymentStatus: 'paid', targets: [{ id: 15, studentName: '합성 학생 A', report: null }, { id: 16, studentName: '합성 학생 B', report: null }] };
const school = { id: 1, name: '합성 학교', currentStage: 'grade1_semester1_midterm', rounds: [round] };
const change = (newAmount: number) => ({ code: 'repricing_approval_required', changes: [{ roundId: 12, oldAmount: 30000, newAmount, delta: newAmount - 30000, paid: true, hasSnapshot: true }] });

async function fixture(page: Page, mode: 'add' | 'remove', variant: 'success' | 'stale' | 'report' | 'last' = 'success') {
 const writes: { url: string; body: unknown }[] = [];
 let reads = 0;
 await page.route('**/auth/isjwt?key=mainauth', route => route.fulfill({ json: { sub: '1', data: { id: '1', name: '테스트' }, exp: 9999999999 } }));
 await page.route('**/api/personal/**', route => {
  const url = new URL(route.request().url());
  if (url.pathname.endsWith('/aura/schools/1')) { reads++; return route.fulfill({ json: school }); }
  if ((mode === 'add' && url.pathname.endsWith('/aura/rounds/12/targets') && route.request().method() === 'POST') ||
      (mode === 'remove' && url.pathname.endsWith('/aura/targets/15') && route.request().method() === 'DELETE')) {
   const body = mode === 'add' ? route.request().postDataJSON() : null;
   writes.push({ url: url.toString(), body });
   if (variant === 'report' || variant === 'last') return route.fulfill({ status: 409, json: { detail: variant === 'report' ? '리포트가 있는 학생은 제거할 수 없습니다.' : '마지막 학생은 제거할 수 없습니다.' } });
   const approved = mode === 'add' ? Array.isArray((body as { approved_price_change?: number[] })?.approved_price_change) : url.searchParams.has('approved_old_amount');
   if (variant === 'stale' && approved && writes.length === 2) return route.fulfill({ status: 409, json: { detail: change(50000) } });
   if (!approved) return route.fulfill({ status: 409, json: { detail: change(40000) } });
   return route.fulfill(mode === 'add' ? { status: 201, json: { id: 17, studentName: '합성 학생 C' } } : { status: 204, body: '' });
  }
  return route.fulfill({ json: [] });
 });
 await page.goto('/personal-project/aura/schools/1');
 await expect(page.getByRole('heading', { name: '합성 학교' })).toBeVisible();
 return { writes, getReads: () => reads };
}

async function add(page: Page) {
 if (!await page.getByPlaceholder('학생 이름').isVisible()) await page.getByRole('button', { name: '＋ 학생 이름 추가' }).click();
 await page.getByPlaceholder('학생 이름').fill('합성 학생 C');
 await page.getByRole('button', { name: '추가', exact: true }).click();
}

test('추가 409 금액·지급·스냅샷을 보여주고 승인 전에는 변경하지 않는다', async ({ page }) => {
 const { writes, getReads } = await fixture(page, 'add');
 await add(page);
 const dialog = page.getByRole('dialog', { name: '대상학생 요금 변경 승인' });
 await expect(dialog).toContainText('30,000원');
 await expect(dialog).toContainText('40,000원');
 await expect(dialog).toContainText('+10,000원');
 await expect(dialog).toContainText('지급 완료');
 await expect(dialog).toContainText('월 스냅샷 있음');
 await page.screenshot({ path: 'test-results/aura-target-approval-desktop.png', fullPage: true });
 await page.setViewportSize({ width: 390, height: 844 });
 await expect(dialog).toBeVisible();
 expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
 await page.screenshot({ path: 'test-results/aura-target-approval-mobile.png', fullPage: true });
 await dialog.getByRole('button', { name: '취소' }).click();
 expect(writes).toHaveLength(1);
 expect(getReads()).toBe(1);
 await add(page);
 await dialog.getByRole('button', { name: '요금 변경 승인 후 추가' }).click();
 await expect(dialog).not.toBeVisible();
 expect(writes.at(-1)?.body).toEqual({ student_name: '합성 학생 C', approved_price_change: [30000, 40000] });
 expect(getReads()).toBeGreaterThan(1);
});

test('삭제 409은 confirm과 승인 금액을 query로 재전달한다', async ({ page }) => {
 const { writes } = await fixture(page, 'remove');
 page.on('dialog', dialog => dialog.accept());
 await page.getByRole('button', { name: '합성 학생 A 삭제' }).click();
 const dialog = page.getByRole('dialog', { name: '대상학생 요금 변경 승인' });
 await dialog.getByRole('button', { name: '요금 변경 승인 후 삭제' }).click();
 await expect(dialog).not.toBeVisible();
 expect(writes).toHaveLength(2);
 expect(new URL(writes[0].url).searchParams.get('confirm')).toBe('true');
 expect(new URL(writes[1].url).searchParams.get('approved_old_amount')).toBe('30000');
 expect(new URL(writes[1].url).searchParams.get('approved_new_amount')).toBe('40000');
});

test('stale 409은 변경된 금액으로 다시 명시 승인받고 취소 시 추가 쓰기가 없다', async ({ page }) => {
 const { writes } = await fixture(page, 'add', 'stale');
 await add(page);
 const dialog = page.getByRole('dialog', { name: '대상학생 요금 변경 승인' });
 await dialog.getByRole('button', { name: '요금 변경 승인 후 추가' }).click();
 await expect(dialog).toContainText('50,000원');
 await expect(dialog).toContainText('제안이 변경되었습니다');
 expect(writes).toHaveLength(2);
 await dialog.getByRole('button', { name: '취소' }).click();
 expect(writes).toHaveLength(2);
});

test('stale 409 최신 제안에 다시 명시 승인하면 최신 값만 전송한다', async ({ page }) => {
 const { writes } = await fixture(page, 'add', 'stale');
 await add(page);
 const dialog = page.getByRole('dialog', { name: '대상학생 요금 변경 승인' });
 await dialog.getByRole('button', { name: '요금 변경 승인 후 추가' }).click();
 await expect(dialog).toContainText('50,000원');
 await dialog.getByRole('button', { name: '요금 변경 승인 후 추가' }).click();
 await expect(dialog).not.toBeVisible();
 expect(writes).toHaveLength(3);
 expect(writes[1].body).toEqual({ student_name: '합성 학생 C', approved_price_change: [30000, 40000] });
 expect(writes[2].body).toEqual({ student_name: '합성 학생 C', approved_price_change: [30000, 50000] });
});

test('리포트 및 마지막 학생 409은 승인 미리보기를 열지 않는다', async ({ page }) => {
 page.on('dialog', dialog => dialog.accept());
 for (const variant of ['report', 'last'] as const) {
  const { writes } = await fixture(page, 'remove', variant);
  await page.getByRole('button', { name: '합성 학생 A 삭제' }).click();
  await expect(page.getByRole('dialog', { name: '대상학생 요금 변경 승인' })).not.toBeVisible();
  await expect(page.locator('.error-banner')).toContainText(variant === 'report' ? '리포트가 있는 학생' : '마지막 학생');
  expect(writes).toHaveLength(1);
 }
});
