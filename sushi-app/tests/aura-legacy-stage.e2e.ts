import { expect, test, type Page } from '@playwright/test';

const legacy = 'grade1_semester1';
const midterm = 'grade1_semester1_midterm';
const final = 'grade1_semester1_final';

async function fixture(page: Page) {
	const start = new Date();
	start.setHours(16, 0, 0, 0);
	const end = new Date(start.getTime() + 60 * 60_000);
	const reports = [{ id: 71, status: 'draft', templateVersion: 4, submittedAt: null }];
	const rounds = [1, 2].map((number) => ({
		id: number,
		schoolId: 10,
		schoolName: '검증고',
		progressStage: legacy,
		parentFreeForThreePlus: false,
		eventId: number,
		roundNumber: number,
		roundNumbers: [number],
		roundLabel: `${number}회차`,
		startTime: start.toISOString(),
		endTime: end.toISOString(),
		description: '',
		attendanceStatus: 'scheduled',
		reportRequired: true,
		hourlyRate: 30000,
		amount: 30000,
		paymentStatus: 'pending',
		seriesGroupId: null,
		seriesIndex: null,
		targets: [{ id: number + 70, studentName: '테스트 학생', report: reports[0] }]
	}));
	const school = { id: 10, name: '검증고', admissionYear: 2024, schoolName: '검증고', memo: '', isActive: true, roundCount: 2, priority: 0, termStatus: 'active', currentStage: midterm, recommendedStage: midterm, freeForThreePlus: false };
	const patches: Record<string, unknown>[] = [];
	const creates: Record<string, unknown>[] = [];
	await page.route('**/auth/isjwt?key=mainauth', (route) => route.fulfill({ json: { sub: '1', data: { id: '1', name: '테스트', email: 'test@example.com' }, exp: 9999999999 } }));
	await page.route('**/api/personal/**', (route) => {
		const path = new URL(route.request().url()).pathname;
		if (path.endsWith('/aura/schools')) return route.fulfill({ json: [school, { ...school, id: 11, name: '이동고', currentStage: final }] });
		if (path.endsWith('/aura/rounds') && route.request().method() === 'GET') return route.fulfill({ json: rounds });
		if (path.endsWith('/aura/rounds') && route.request().method() === 'POST') {
			creates.push(route.request().postDataJSON());
			return route.fulfill({ json: rounds[0] });
		}
		if (/\/aura\/rounds\/\d+$/.test(path) && route.request().method() === 'PATCH') {
			const body = route.request().postDataJSON();
			patches.push(body);
			// Mirror the backend's side effects when a stage or round number is present.
			if ('progress_stage' in body) rounds[0].progressStage = body.progress_stage;
			if ('progress_stage' in body || 'round_number' in body) reports.splice(0);
			if ('start_time' in body) rounds[0].startTime = body.start_time;
			return route.fulfill({ json: rounds[0] });
		}
		return route.fulfill({ json: [] });
	});
	return { rounds, reports, patches, creates };
}

test('기존 학기 단계 열기·시간만 수정·저장 시 단계와 리포트 스냅샷을 보존한다', async ({ page }) => {
	const { rounds, reports, patches } = await fixture(page);
	await page.goto('/personal-project/aura');
	await page.locator('.week-scheduler .slot.busy').first().click();
	await expect(page.locator('#round-stage')).toHaveValue(legacy);
	await expect(page.locator('#round-stage option:checked')).toHaveText('1학년 · 1학기');
	await page.screenshot({ path: 'test-results/aura-legacy-stage-desktop.png', fullPage: true });
	await page.setViewportSize({ width: 390, height: 844 });
	await page.screenshot({ path: 'test-results/aura-legacy-stage-mobile.png', fullPage: true });
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
	await page.locator('#round-start').fill('2026-11-03T17:00');
	await page.locator('#round-end').fill('2026-11-03T18:00');
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(() => patches.length).toBe(1);
	expect(patches[0]).not.toHaveProperty('progress_stage');
	expect(patches[0]).not.toHaveProperty('school_id');
	expect(patches[0]).not.toHaveProperty('round_number');
	expect(patches[0]).not.toHaveProperty('round_numbers');
	expect(rounds[0].progressStage).toBe(legacy);
	expect(reports).toHaveLength(1);
	expect(reports[0].templateVersion).toBe(4);
});

test('구 학기 회차 다음 번호를 중간 단계에 제안하고 기말 단계는 독립 번호를 쓴다', async ({ page }) => {
	const { creates } = await fixture(page);
	await page.goto('/personal-project/aura');
	await page.getByRole('button', { name: '＋ 새 회차' }).click();
	await expect(page.locator('#round-stage')).toHaveValue(midterm);
	await expect(page.locator('#round-number')).toHaveValue('3');
	await page.locator('#round-stage').selectOption(final);
	await expect(page.locator('#round-number')).toHaveValue('1');
	await page.locator('#round-students').fill('테스트 학생');
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(() => creates.length).toBe(1);
	expect(creates[0]).toMatchObject({ progress_stage: final, round_number: 1 });
});

test('명시적으로 구 단계에서 기말로 변경하면 새 단계가 전송된다', async ({ page }) => {
	const { patches } = await fixture(page);
	await page.goto('/personal-project/aura');
	await page.locator('.week-scheduler .slot.busy').first().click();
	await page.locator('#round-stage').selectOption(final);
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(() => patches.length).toBe(1);
	expect(patches[0]).toHaveProperty('progress_stage', final);
});

test('학교를 명시적으로 옮겨도 선택하지 않은 단계가 학교 기본 단계로 바뀌지 않는다', async ({ page }) => {
	const { patches } = await fixture(page);
	await page.goto('/personal-project/aura');
	await page.locator('.week-scheduler .slot.busy').first().click();
	await page.locator('#round-school').selectOption('11');
	await expect(page.locator('#round-stage')).toHaveValue(legacy);
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(() => patches.length).toBe(1);
	expect(patches[0]).toMatchObject({ school_id: 11, progress_stage: legacy });
});
