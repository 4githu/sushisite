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

async function mockSessionApi(page: Page, email = 'xrealrehear@gmail.com') {
	await page.route('**/auth/isjwt?key=mainauth', (route) => route.fulfill({
		json: { sub: '7', data: { id: '7', name: '테스트', email }, exp: 9999999999 }
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

async function openSessionFromConfirm(page: Page) {
	const browserErrors: string[] = [];
	page.on('pageerror', (error) => browserErrors.push(error.message));
	await page.goto('/odi/session/presentation/confirm');
	// Store가 비어 있는 새 세션에서는 서버의 recent_template를 잠깐이라도 보여주지 않는다.
	await expect(page.getByText('발표 제목 없음', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: '시작하기' }).click();
	return browserErrors;
}

test('연습 계정은 Confirm의 시작하기에서 체험/일반 선택창을 연다', async ({ page }) => {
	await mockSessionApi(page);
	const browserErrors = await openSessionFromConfirm(page);

	const dialog = page.getByRole('dialog', { name: '진행할 세션을 선택해 주세요' });
	await page.waitForTimeout(300);
	if (await dialog.count() === 0) {
		const alerts = await page.locator('[role="alert"]').allTextContents();
		throw new Error(`Confirm 선택창 미표시: url=${page.url()}, alerts=${JSON.stringify(alerts)}, browserErrors=${JSON.stringify(browserErrors)}`);
	}
	await expect(dialog).toBeVisible();
	const experienceCard = dialog.getByRole('button', { name: /체험 세션/ });
	const regularCard = dialog.getByRole('button', { name: /^일반 세션/ });
	const submitButton = dialog.getByRole('button', { name: '선택한 세션으로 시작하기' });
	await expect(experienceCard).toBeVisible();
	await expect(regularCard).toBeVisible();

	const [dialogBox, experienceBox, regularBox, submitBox] = await Promise.all([
		dialog.boundingBox(), experienceCard.boundingBox(), regularCard.boundingBox(), submitButton.boundingBox()
	]);
	expect(dialogBox).not.toBeNull();
	expect(experienceBox).not.toBeNull();
	expect(regularBox).not.toBeNull();
	expect(submitBox).not.toBeNull();
	expect(experienceBox!.y + experienceBox!.height).toBeLessThan(submitBox!.y);
	expect(regularBox!.y + regularBox!.height).toBeLessThan(submitBox!.y);
	expect(Math.abs(experienceBox!.height - regularBox!.height)).toBeLessThanOrEqual(1);
	expect(dialogBox!.y).toBeGreaterThanOrEqual(0);
	expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
	await expect(page).toHaveURL(/\/odi\/session\/presentation\/confirm$/);
});

test('체험 세션은 선택 후 1234 PIN을 표시한다', async ({ page }) => {
	await mockSessionApi(page);
	await openSessionFromConfirm(page);
	await page.getByRole('button', { name: /체험 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=experience$/);
	await expect(page.getByText('1234', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toBeVisible();
});

test('일반 세션은 선택 후 백엔드가 생성한 PIN을 표시한다', async ({ page }) => {
	await mockSessionApi(page);
	await openSessionFromConfirm(page);
	await page.getByRole('button', { name: /^일반 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=regular$/);
	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toHaveCount(0);
});

test('Wait VR을 새로 열어 store가 비어 있어도 일반 세션 설정을 서버에서 복구한다', async ({ page }) => {
	await mockSessionApi(page);
	await page.goto('/odi/waitvr?mode=regular');

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
});

test('일반 계정은 선택창 없이 바로 일반 세션으로 이동한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await openSessionFromConfirm(page);

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=regular$/);
	await expect(page.getByRole('dialog', { name: '진행할 세션을 선택해 주세요' })).toHaveCount(0);
	await expect(page.getByText('9876', { exact: true })).toBeVisible();
});

test('일반 계정이 체험 URL로 직접 들어와도 일반 세션으로 시작한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.goto('/odi/waitvr?mode=experience');

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByText('1234', { exact: true })).toHaveCount(0);
});

test('모바일 프로필 드롭다운은 본문 텍스트가 비치거나 카드 밖으로 새지 않는다', async ({ page }) => {
	await page.setViewportSize({ width: 280, height: 520 });
	await mockSessionApi(page);
	await page.goto('/odi/session/presentation/confirm');

	const openSidebar = page.getByRole('button', { name: '사이드바 열기' });
	await expect(openSidebar).toBeVisible();
	await openSidebar.click();
	await expect(page.locator('.sidebar')).toHaveClass(/open/);
	await page.waitForTimeout(250);

	const profileButton = page.getByRole('button', { name: /테스트 새싹 보이스/ });
	const profileBox = await profileButton.boundingBox();
	expect(profileBox).not.toBeNull();
	expect(profileBox!.x).toBeGreaterThanOrEqual(0);
	expect(profileBox!.y + profileBox!.height).toBeLessThanOrEqual(520);
	await profileButton.click({ force: true });

	const dropdown = page.locator('.profile-dropdown .dropdown');
	await expect(dropdown).toBeVisible();
	await expect(page.getByText(/지금화면순서/)).toHaveCount(0);

	const backgroundColor = await dropdown.evaluate((element) => getComputedStyle(element).backgroundColor);
	expect(backgroundColor).toBe('rgb(96, 94, 191)');

	const box = await dropdown.boundingBox();
	expect(box).not.toBeNull();
	expect(box!.x).toBeGreaterThanOrEqual(0);
	expect(box!.x + box!.width).toBeLessThanOrEqual(280);
	expect(box!.y).toBeGreaterThanOrEqual(0);
	expect(box!.y + box!.height).toBeLessThanOrEqual(520);
});
