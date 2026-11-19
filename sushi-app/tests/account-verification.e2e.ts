import { expect, test, type Page } from '@playwright/test';

const initial = { id: '7', name: '처음', email: 'before@example.invalid', email_verified: true };
async function mockOdi(page: Page) {
 let profile = { ...initial };
 let nicknameFails = false;
 let offline = false;
 let expired = false;
 let sendStatus = 200;
 let confirmStatus = 200;
 const calls: Array<Record<string, unknown>> = [];
 await page.route('**/auth/isjwt?key=mainauth', route => route.fulfill({ json: { sub: '7', data: profile, exp: 9999999999 } }));
 await page.route('**/odi/db/login', route => route.fulfill({ json: { user: { user_id: '7', auth_id: '7', config: { profile: { nickname: '처음' } } } } }));
 await page.route('**/auth/user', async route => {
  const body = route.request().postDataJSON(); calls.push(body);
  if (offline) return route.abort();
  if (expired) return route.fulfill({ status: 401, json: { detail: 'expired' } });
  profile = { ...profile, name: body.name ?? profile.name, email: body.email ?? profile.email, email_verified: body.email && body.email !== profile.email ? false : profile.email_verified };
  return route.fulfill({ json: { success: true, data: profile, email_verification_required: !profile.email_verified } });
 });
 await page.route('**/odi/db/users/7/config', route => nicknameFails ? route.fulfill({ status: 503, json: { detail: 'unavailable' } }) : route.fulfill({ json: { user: { user_id: '7', auth_id: '7', config: { profile: { nickname: route.request().postDataJSON().config.profile.nickname } } } } }));
 await page.route('**/auth/user/email-verification/send', route => route.fulfill({ status: sendStatus, json: sendStatus === 200 ? { success: true } : { detail: 'retry limited' } }));
 await page.route('**/auth/user/email-verification/confirm', route => {
  if (confirmStatus !== 200) return route.fulfill({ status: confirmStatus, json: { detail: 'invalid or expired code' } });
  profile.email_verified = true; return route.fulfill({ json: { success: true, data: profile, email_verification_required: false } });
 });
 return { calls, setNicknameFailure: () => nicknameFails = true, setOffline: (value = true) => offline = value, setExpired: () => expired = true, setSendStatus: (value: number) => sendStatus = value, setConfirmStatus: (value: number) => confirmStatus = value, profile: () => profile };
}
async function openAccount(page: Page) {
 await page.goto('/odi');
 await page.locator('.my-page').click();
 await page.getByRole('button', { name: '회원정보 수정' }).click();
 await expect(page.getByRole('heading', { name: '회원정보 관리' })).toBeVisible();
}

test('이름만 저장하면 인증을 유지하고 재저장에 비밀번호가 필요하지 않다', async ({ page }) => {
 const api = await mockOdi(page); await openAccount(page);
 await page.getByRole('textbox', { name: '이름', exact: true }).fill('새 이름');
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText('프로필 저장 완료')).toBeVisible();
 await expect(page.getByRole('textbox', { name: '이메일', exact: true })).toHaveValue(initial.email);
 await page.getByRole('button', { name: '정보 수정' }).click();
 expect(api.calls.at(-1)?.password).toBeUndefined();
 expect(api.profile().name).toBe('새 이름');
 expect(api.profile().email_verified).toBe(true);
});

test('이메일 변경 뒤 확인·별도 ODI 닉네임 실패를 구분한다', async ({ page }) => {
 const api = await mockOdi(page); api.setNicknameFailure(); await openAccount(page);
 await page.getByRole('textbox', { name: '이메일', exact: true }).fill('after@example.invalid');
 await page.getByRole('textbox', { name: '이메일 변경 확인 비밀번호' }).fill('synthetic-secret');
 await page.getByRole('textbox', { name: 'ODI 닉네임' }).fill('새 닉네임');
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText(/프로필.*저장.*ODI 닉네임.*실패/)).toBeVisible();
 await expect(page.getByText(/새 이메일 확인 필요/)).toBeVisible();
 expect(api.calls.at(-1)?.password).toBe('synthetic-secret');
 await expect(page.getByLabel('이메일 변경 확인 비밀번호')).toHaveCount(0);
 await page.getByRole('button', { name: '정보 수정' }).click();
 expect(api.calls.at(-1)?.password).toBeUndefined();
 await page.getByRole('button', { name: /인증 메일 발송/ }).click();
 await page.getByLabel('인증 코드').fill('123456');
 await page.getByRole('button', { name: /코드 확인/ }).click();
 await expect(page.getByText(/이메일 확인 완료/)).toBeVisible();
 expect(api.profile().email_verified).toBe(true);
 await page.screenshot({ path: 'test-results/account-verification-desktop.png', fullPage: true });
});

test('발송 제한, 잘못된 코드, 만료 코드에서 입력과 접근을 유지한다', async ({ page }) => {
 const api = await mockOdi(page); await openAccount(page);
 await page.getByRole('textbox', { name: '이메일', exact: true }).fill('new@example.invalid');
 await page.getByRole('textbox', { name: '이메일 변경 확인 비밀번호' }).fill('synthetic-secret');
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText('새 이메일 확인 필요')).toBeVisible();
 api.setSendStatus(429);
 await page.getByRole('button', { name: /인증 메일 발송/ }).click();
 await expect(page.getByText(/재전송 제한/)).toBeVisible();
 api.setConfirmStatus(400);
 await page.getByLabel('인증 코드').fill('synthetic-code');
 await page.getByRole('button', { name: '코드 확인' }).click();
 await expect(page.getByText(/invalid or expired code/)).toBeVisible();
 await expect(page.getByLabel('인증 코드')).toHaveValue('synthetic-code');
 await expect(page.getByRole('heading', { name: '새 이메일 확인 필요' })).toBeVisible();
});

test('오프라인과 세션 만료를 구별하고 입력을 보존한다', async ({ page }) => {
 const api = await mockOdi(page); await openAccount(page);
 await page.getByRole('textbox', { name: '이름', exact: true }).fill('남겨둘 이름');
 api.setOffline();
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText(/네트워크 연결/)).toBeVisible();
 await expect(page.getByRole('textbox', { name: '이름', exact: true })).toHaveValue('남겨둘 이름');
 api.setOffline(false); api.setExpired();
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText(/로그인이 만료되었습니다/)).toBeVisible();
 await expect(page.getByRole('textbox', { name: '이름', exact: true })).toHaveValue('남겨둘 이름');
});

test('모바일 이메일 확인 안내가 보이고 서비스 접근을 막지 않는다', async ({ page }) => {
 await page.setViewportSize({ width: 390, height: 844 });
 await mockOdi(page);
 await page.goto('/odi');
 await page.getByRole('button', { name: '사이드바 열기' }).click();
 await page.locator('.my-page').click();
 await page.getByRole('button', { name: '회원정보 수정' }).click();
 await page.getByRole('textbox', { name: '이메일', exact: true }).fill('mobile@example.invalid');
 await page.getByRole('textbox', { name: '이메일 변경 확인 비밀번호' }).fill('synthetic-secret');
 await page.getByRole('button', { name: '정보 수정' }).click();
 await expect(page.getByText('새 이메일 확인 필요')).toBeVisible();
 await page.screenshot({ path: 'test-results/account-verification-mobile.png', fullPage: true });
 await page.keyboard.press('Escape');
 await expect(page.getByRole('heading', { name: /안녕하세요/ })).toBeVisible();
});

test('다른 탭 변경 후 메뉴를 다시 열면 30초 캐시 없이 최신 계정을 표시한다', async ({ page, context }) => {
 let profile = { ...initial };
 const setup = async (tab: Page) => {
  await tab.route('**/auth/isjwt?key=mainauth', route => route.fulfill({ json: { sub: '7', data: profile, exp: 9999999999 } }));
  await tab.route('**/api/personal/**', route => route.fulfill({ json: route.request().url().endsWith('/boards') ? { canAdmin: false } : [] }));
 };
 await setup(page);
 await page.goto('/personal-project/calendar');
 const button = page.locator('.account-button');
 await expect(button).toContainText('처음');
 await button.click();
 const second = await context.newPage();
 await setup(second);
 await second.goto('/personal-project/calendar');
 profile = { ...profile, name: '다른 탭 이름', email: 'another@example.invalid', email_verified: false };
 await second.locator('.account-button').click();
 await expect(second.locator('.account-button')).toContainText('다른 탭 이름');
 await button.click(); await button.click();
 await expect(button).toContainText('다른 탭 이름');
 await expect(page.getByText('이메일 확인이 필요합니다.')).toBeVisible();
 await second.close();
});

test('계정 카드의 401은 계정을 숨기고 오프라인은 오류로 표시한다', async ({ page }) => {
 let status = 200;
 await page.route('**/auth/isjwt?key=mainauth', route => status === 0 ? route.abort() : route.fulfill({ status, json: { sub: '7', data: initial, exp: 9999999999 } }));
 await page.route('**/api/personal/**', route => route.fulfill({ json: { canAdmin: false } }));
 await page.goto('/personal-project/calendar');
 await expect(page.locator('.account-button')).toContainText('처음');
 status = 0;
 await page.locator('.account-button').click();
 await expect(page.getByText(/연결을 확인해주세요/)).toBeVisible();
 status = 401;
 await page.locator('.account-button').click(); await page.locator('.account-button').click();
 await expect(page.getByText(/로그인이 만료되었습니다/)).toBeVisible();
 await expect(page.locator('.account-button')).not.toContainText('처음');
});
