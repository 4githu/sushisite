import { expect, test } from '@playwright/test';

test('가입 약관은 선택 상태를 구분하고 필수 동의와 비밀번호 보기 동작을 유지한다', async ({
	page
}) => {
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({ status: 401, json: { detail: 'test guest' } })
	);
	await page.goto('/odi/register');
	await page.getByPlaceholder('이름을 입력해주세요').fill('아이콘 검사');
	await expect(page.getByText('사용할 수 있는 이름입니다')).toBeVisible();
	const checks = page.getByRole('checkbox');
	await expect(checks).toHaveCount(4);
	const all = page.getByRole('checkbox', { name: '모든 약관에 동의합니다.' });
	const service = page.getByRole('checkbox', { name: '[필수] 서비스 이용약관 동의', exact: true });
	const privacy = page.getByRole('checkbox', {
		name: '[필수] 개인정보 수집 및 이용 동의',
		exact: true
	});
	const marketing = page.getByRole('checkbox', {
		name: '[선택] 서비스 소식 및 혜택 알림 수신 동의',
		exact: true
	});
	await expect(all).toHaveAttribute('aria-checked', 'false');
	const uncheckedIcon = await all.locator('img').getAttribute('src');
	expect(decodeURIComponent(uncheckedIcon!)).toContain('check_box_outline_blank');
	await all.click();
	for (const item of [all, service, privacy, marketing])
		await expect(item).toHaveAttribute('aria-checked', 'true');
	expect(await all.locator('img').getAttribute('src')).not.toBe(uncheckedIcon);
	await marketing.press('Space');
	await expect(marketing).toHaveAttribute('aria-checked', 'false');
	await expect(all).toHaveAttribute('aria-checked', 'false');
	await expect(service).toHaveAttribute('aria-checked', 'true');
	await expect(privacy).toHaveAttribute('aria-checked', 'true');
	const fields = page.locator('.field-icon');
	expect(
		new Set(await fields.evaluateAll((imgs) => imgs.map((img) => (img as HTMLImageElement).src)))
			.size
	).toBe(3);
	await page.getByRole('button', { name: '비밀번호 보기', exact: true }).first().click();
	await expect(page.getByRole('button', { name: '비밀번호 숨기기', exact: true })).toHaveAttribute(
		'aria-pressed',
		'true'
	);
	await expect(page.getByPlaceholder('영문, 숫자, 특수문자 포함 8자리 이상')).toHaveAttribute(
		'type',
		'text'
	);
	await page.getByRole('button', { name: '비밀번호 숨기기', exact: true }).click();
	await expect(page.getByPlaceholder('영문, 숫자, 특수문자 포함 8자리 이상')).toHaveAttribute(
		'type',
		'password'
	);
	await page.screenshot({
		path: '/tmp/rehear-register-icons.png',
		fullPage: true,
		animations: 'disabled'
	});
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.locator('main.content')).toHaveCSS('margin-left', '0px');
	await page.getByRole('button', { name: '사이드바 접기', exact: true }).click();
	await expect(page.getByRole('button', { name: '사이드바 열기', exact: true })).toBeVisible();
	await page.evaluate(() => window.scrollTo(0, 0));
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.screenshot({
		path: '/tmp/rehear-register-mobile.png',
		fullPage: true,
		animations: 'disabled'
	});
});

test('훈련은 피그마의 세 가지 색상을 사용하고 준비 중 훈련은 시작되지 않는다', async ({ page }) => {
	const user = { user_id: 'icon-audit', auth_id: 'icon-audit', config: {}, recent_template: null };
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: user.auth_id,
				data: { id: user.auth_id, name: '아이콘 검사', email: 'icons@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/odi/db/login', (r) => r.fulfill({ json: { user } }));
	await page.route('**/odi/db/users/icon-audit/sessions?*', (r) =>
		r.fulfill({ json: { sessions: [] } })
	);
	const catalog = [
		['message_clarity', '메시지 명확성', 'content', true],
		['evidence_use', '근거 활용', 'content', true],
		['speech_rate', '발화 속도', 'delivery', true],
		['gaze', '시선 처리', 'delivery', false]
	].map(([id, title, group, available]) => ({
		id,
		title,
		group,
		available,
		task: '목표에 맞춰 연습하세요.'
	}));
	await page.route('**/odi/coaching/practice', (r) =>
		r.fulfill({
			json: {
				catalog,
				attempts: [],
				progress: { metrics: {}, weekly_successes: 0, completed_count: 0, total_seconds: 0 }
			}
		})
	);
	await page.goto('/odi/practice');
	await expect(page.locator('.practice-card')).toHaveCount(4);
	const srcs = await page
		.locator('.practice-card .practice-icon')
		.evaluateAll((imgs) => imgs.map((img) => (img as HTMLImageElement).src));
	expect(new Set(srcs.slice(0, 3)).size).toBe(3);
	expect(
		await page
			.locator('.practice-card .practice-icon')
			.evaluateAll((imgs) =>
				imgs.every(
					(img) => (img as HTMLImageElement).complete && (img as HTMLImageElement).naturalWidth > 0
				)
			)
	).toBe(true);
	await expect(page.getByRole('button', { name: /시선 처리/ })).toBeDisabled();
	await page.screenshot({
		path: '/tmp/rehear-practice-icons.png',
		fullPage: true,
		animations: 'disabled'
	});
	await page.locator('.my-page').click();
	await page.getByRole('button', { name: '회원정보 수정' }).click();
	await expect(page.getByLabel('이름', { exact: true })).toHaveValue('아이콘 검사');
	await expect(page.getByLabel('이메일', { exact: true })).toHaveValue('icons@example.com');
	await page.getByLabel('이름', { exact: true }).fill('수정 중인 이름');
	await page.getByLabel('이메일', { exact: true }).click();
	await expect(page.getByLabel('이름', { exact: true })).toHaveValue('수정 중인 이름');
});
