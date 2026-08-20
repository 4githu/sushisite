import { expect, test, type Page } from '@playwright/test';

const presentationTemplate = {
	type: 'presentation',
	environment: {
		title: '브라우저 검증 발표',
		purpose: '프로젝트 목적',
		language: '한국어',
		place: '강의실',
		duration_minutes: 2,
		question_count: 2
	},
	files: { slide: null, paper: null, script: null, script_content: '' },
	audience: {
		audience_type: '대학생',
		audience_count: 6,
		expertise_level: '중간',
		interest_level: '중간'
	}
};

const odiUser = {
	user_id: '7',
	auth_id: '7',
	recent_template: presentationTemplate,
	config: {},
	created_at: '2026-08-15T00:00:00Z',
	updated_at: '2026-08-15T00:00:00Z'
};

async function mockSessionApi(page: Page) {
	await page.route('**/auth/isjwt?key=mainauth', (route) => route.fulfill({
		json: { sub: '7', data: { id: '7', name: '테스트', email: 'xrealrehear@gmail.com' }, exp: 9999999999 }
	}));
	await page.route('**/odi/db/login', (route) => route.fulfill({ json: { user: odiUser } }));
	await page.route('**/odi/db/users/7/recent-template', (route) => route.fulfill({
		json: { user: { ...odiUser, recent_template: presentationTemplate } }
	}));
	await page.route('**/odi/db/pre-sessions/start-from-recent', (route) => route.fulfill({
		json: {
			pin_code: '9876',
			pre_session: {
				pin_code: '9876', template_id: 'template-test', session_id: null,
				state: 'waiting', expires_at: '2026-08-15T10:00:00Z', created_at: '2026-08-15T09:00:00Z'
			},
			// 일반 세션의 화면 전환/PIN 표시를 Firebase 네트워크와 독립적으로 검증한다.
			template: null,
			file_bundle: null
		}
	}));
	await page.route('**/odi/db/pre-sessions/9876/finish', (route) => route.fulfill({
		json: {
			pre_session: {
				pin_code: '9876', template_id: 'template-test', session_id: 'session-test',
				state: 'finished', expires_at: '2026-08-15T10:00:00Z', created_at: '2026-08-15T09:00:00Z'
			},
			session: { session_id: 'session-test', feedback: {}, state: 'completed' }
		}
	}));
	await page.route('**/odi/db/pre-sessions/9876', (route) => route.fulfill({
		json: {
			pre_session: {
				pin_code: '9876', template_id: 'template-test', session_id: null,
				state: 'waiting', expires_at: '2026-08-15T10:00:00Z', created_at: '2026-08-15T09:00:00Z'
			}
		}
	}));
}

async function enterWaitVrFromConfirm(page: Page) {
	const browserErrors: string[] = [];
	page.on('pageerror', (error) => browserErrors.push(error.message));
	await page.goto('/odi/session/presentation/confirm');
	await expect(page.getByText('테스트', { exact: true })).toBeVisible();
	await page.getByRole('link', { name: '시작하기' }).click();
	await page.waitForTimeout(300);
	if (!page.url().includes('/odi/waitvr')) {
		const visibleError = await page.locator('[role="alert"]').allTextContents();
		throw new Error(`확인 화면 이동 실패: alerts=${JSON.stringify(visibleError)}, browserErrors=${JSON.stringify(browserErrors)}`);
	}
	await expect(page).toHaveURL(/\/odi\/waitvr\?choose=1$/);
}

test.beforeEach(async ({ page }) => {
	await mockSessionApi(page);
});

test('Wait VR 진입 즉시 체험/일반 세션 선택창을 연다', async ({ page }) => {
	await enterWaitVrFromConfirm(page);

	const dialog = page.getByRole('dialog', { name: '진행할 세션을 선택해 주세요' });
	await expect(dialog).toBeVisible();
	await expect(dialog.getByText('체험 세션', { exact: true })).toBeVisible();
	await expect(dialog.getByText('일반 세션', { exact: true })).toBeVisible();
});

test('체험 세션은 선택 후 1234 PIN을 표시한다', async ({ page }) => {
	await enterWaitVrFromConfirm(page);
	await page.getByRole('button', { name: /체험 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page.getByText('1234', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toBeVisible();
});

test('일반 세션은 선택 후 백엔드가 생성한 PIN을 표시한다', async ({ page }) => {
	await enterWaitVrFromConfirm(page);
	await page.getByRole('button', { name: /^일반 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toHaveCount(0);
});

test('Wait VR을 새로 열어 store가 비어 있어도 일반 세션 설정을 서버에서 복구한다', async ({ page }) => {
	await page.goto('/odi/waitvr?choose=1');
	await page.getByRole('button', { name: /^일반 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
});
