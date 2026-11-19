import { expect, test, type Page } from '@playwright/test';

test.use({ hasTouch: true });

const stage = 'grade1_semester1_midterm';
const school = (id: number, name: string, termStatus: 'active' | 'ended', priority: number) => ({
	id,
	name,
	admissionYear: 2025,
	schoolName: name,
	memo: '',
	isActive: true,
	roundCount: 0,
	priority,
	termStatus,
	currentStage: stage,
	recommendedStage: stage,
	freeForThreePlus: false
});

async function fixture(page: Page) {
	let schools = [
		school(1, '첫 학교', 'active', 1),
		school(2, '둘 학교', 'active', 2),
		school(3, '셋 학교', 'active', 3),
		school(4, '종료 학교', 'ended', 4)
	];
	const requests: number[][] = [];
	let fail = false;
	await page.route('**/auth/isjwt?key=mainauth', (route) =>
		route.fulfill({ json: { sub: '1', data: { id: '1', name: '테스트' }, exp: 9999999999 } })
	);
	await page.route('**/api/personal/**', (route) => {
		const path = new URL(route.request().url()).pathname;
		if (path.endsWith('/aura/schools') && route.request().method() === 'GET')
			return route.fulfill({ json: schools });
		if (path.endsWith('/aura/schools/reorder')) {
			const ids = route.request().postDataJSON().school_ids as number[];
			requests.push(ids);
			if (fail) return route.fulfill({ status: 503, json: { detail: '순서 저장 실패' } });
			schools = ids.map((id, index) => ({
				...schools.find((item) => item.id === id)!,
				priority: index + 1
			}));
			return route.fulfill({ json: schools });
		}
		return route.fulfill({ json: [] });
	});
	return {
		requests,
		failNext: () => {
			fail = true;
		},
		getSchools: () => schools
	};
}

test('모바일 터치 버튼과 키보드로 학교를 이동하고 저장된 우선순위를 반영한다', async ({ page }) => {
	const { requests, getSchools } = await fixture(page);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/personal-project/aura/schools');
	const cards = page.locator('.school-card');
	await expect(cards).toHaveCount(4);
	await expect(cards.nth(0)).toContainText('첫 학교');
	const up = page.getByRole('button', { name: '둘 학교 위로 이동' });
	await expect(up).toBeEnabled();
	await up.tap();
	await expect(cards.nth(0)).toContainText('둘 학교');
	await expect.poll(() => requests.length).toBe(1);
	expect(requests[0]).toEqual([2, 1, 3, 4]);
	expect(getSchools().map((item) => item.priority)).toEqual([1, 2, 3, 4]);
	await expect(page.getByRole('button', { name: '둘 학교 위로 이동' })).toBeDisabled();
	const down = page.getByRole('button', { name: '둘 학교 아래로 이동' });
	await down.focus();
	await page.keyboard.press('Enter');
	await expect.poll(() => requests.length).toBe(2);
	expect(requests[1]).toEqual([1, 2, 3, 4]);
	await expect(page.getByRole('button', { name: '종료 학교 위로 이동' })).toBeDisabled();
	await expect(page.getByRole('button', { name: '셋 학교 아래로 이동' })).toBeDisabled();
	expect(
		await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
	).toBeTruthy();
	await page.screenshot({ path: 'test-results/aura-school-order-mobile.png', fullPage: true });
});

test('순서 저장 실패 시 서버 순서를 복구하고 재시도할 수 있다', async ({ page }) => {
	const { requests, failNext } = await fixture(page);
	await page.goto('/personal-project/aura/schools');
	failNext();
	await page.getByRole('button', { name: '둘 학교 위로 이동' }).click();
	await expect(page.locator('.error-banner')).toContainText('순서 저장 실패');
	await expect(page.locator('.school-card').first()).toContainText('첫 학교');
	expect(requests).toEqual([[2, 1, 3, 4]]);
});

test('기존 마우스 드래그로도 같은 순서 저장 경로를 사용한다', async ({ page }) => {
	const { requests } = await fixture(page);
	await page.goto('/personal-project/aura/schools');
	await page.locator('.school-card').nth(0).dragTo(page.locator('.school-card').nth(2));
	await expect.poll(() => requests.length).toBe(1);
	expect(requests[0]).toEqual([2, 3, 1, 4]);
});
