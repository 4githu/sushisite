import { expect, test } from '@playwright/test';

const user = {
	user_id: 'refresh-user',
	auth_id: 'refresh-user',
	recent_template: null,
	config: { preferences: { report_view_version: 'v3', show_timeline_video: false } },
	created_at: '2026-09-10T00:00:00Z',
	updated_at: '2026-09-10T00:00:00Z'
};

const report = {
	session_id: 'refresh-session',
	user_id: user.user_id,
	template_id: null,
	template: { type: 'presentation', environment: { title: '새로고침 검증 발표' }, files: {} },
	feedback: {
		score: { overall_score: 84 },
		score_card: { scores: { engagement: 84, clarity: 82, credibility: 86 } }
	},
	state: 'completed',
	started_at: '2026-09-10T00:00:00Z',
	ended_at: '2026-09-10T00:05:00Z',
	created_at: '2026-09-10T00:00:00Z',
	updated_at: '2026-09-10T00:05:00Z'
};

test('리포트 새로고침은 ODI 로그인 복구가 끝난 뒤 세션을 요청한다', async ({ page }) => {
	let loginReady = false;
	let sessionBeforeLogin = 0;

	await page.route('**/auth/isjwt?key=mainauth', (route) =>
		route.fulfill({
			json: {
				sub: user.user_id,
				data: { id: user.user_id, name: '새로고침 테스트', email: 'refresh@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/odi/db/login', async (route) => {
		loginReady = false;
		await new Promise((resolve) => setTimeout(resolve, 250));
		loginReady = true;
		await route.fulfill({ json: { user } });
	});
	await page.route('**/odi/db/sessions/refresh-session', (route) => {
		if (!loginReady) sessionBeforeLogin += 1;
		return route.fulfill({ status: loginReady ? 200 : 401, json: { session: report } });
	});

	await page.goto('/odi/report/refresh-session');
	await expect(page.getByRole('heading', { name: '새로고침 검증 발표' })).toBeVisible();

	loginReady = false;
	await page.reload();
	await expect(page.getByRole('heading', { name: '새로고침 검증 발표' })).toBeVisible();
	await expect(page.getByText('ODI 유저가 없습니다.')).toHaveCount(0);
	expect(sessionBeforeLogin).toBe(0);
});
