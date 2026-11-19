import { expect, test, type Page } from '@playwright/test';

type GenerateResponse = { status?: number; detail?: unknown; body?: unknown };

const old = {
	id: 11, schoolId: 1, schoolName: '기존 학교', progressStage: 'grade1_semester1_midterm',
	parentFreeForThreePlus: false, eventId: 11, roundNumber: 1, roundNumbers: [1],
	roundLabel: '1회', startTime: '2026-10-10T10:00:00', endTime: '2026-10-10T11:00:00',
	description: '', attendanceStatus: 'completed', reportRequired: true,
	hourlyRate: 30000, amount: 30000, paymentStatus: 'pending', seriesGroupId: null,
	seriesIndex: null, targets: [{ id: 1, studentName: '합성 학생 A', report: null }]
};
const changed = { ...old, schoolName: '변경 학교', targets: [{ id: 2, studentName: '합성 학생 B', report: null }] };
const added = { ...old, id: 12, schoolName: '추가 학교', amount: 12000, hourlyRate: 12000 };

const snapshot = (items: typeof old[], totalAmount: number) => ({
	year: 2026,
	month: 10,
	totalAmount,
	completedCount: items.length,
	settlementCount: items.length,
	generatedAt: '2026-10-10T12:00:00',
	items
});

const approval = (digest: string, newTotal: number) => ({
	code: 'snapshot_regeneration_approval_required',
	snapshotDigest: digest,
	proposedDigest: `proposal-${digest}`,
	oldTotal: 39000,
	newTotal,
	delta: newTotal - 39000,
	roundChanges: []
});

async function fixture(page: Page, responses: GenerateResponse[]) {
	const posts: { url: string; body: unknown }[] = [];
	let responseIndex = 0;
	let currentSnapshot = snapshot([old], 39000);
	await page.route('**/auth/isjwt?key=mainauth', (route) =>
		route.fulfill({ json: { sub: '1', data: { id: '1', name: '테스트' }, exp: 9999999999 } })
	);
	await page.route('**/api/personal/**', async (route) => {
		const url = new URL(route.request().url());
		if (url.pathname.endsWith('/aura/settlements/generate') && route.request().method() === 'POST') {
			posts.push({ url: `${url.pathname}${url.search}`, body: route.request().postDataJSON() ?? null });
			const response = responses[Math.min(responseIndex++, responses.length - 1)];
			if (response.status === 409) {
				return route.fulfill({ status: 409, json: { detail: response.detail } });
			}
			currentSnapshot = (response.body ?? snapshot([changed, added], 42000)) as typeof currentSnapshot;
			return route.fulfill({ json: currentSnapshot });
		}
		if (url.pathname.endsWith('/aura/settlements') && route.request().method() === 'GET') {
			return route.fulfill({ json: currentSnapshot, headers: { 'cache-control': 'no-store' } });
		}
		if (url.pathname.endsWith('/aura/settlements/parents')) return route.fulfill({ json: { items: [] } });
		return route.fulfill({ json: [] });
	});
	await page.clock.install({ time: new Date('2026-10-15T12:00:00') });
	await page.goto('/personal-project/aura/settlements');
	await expect(page.getByRole('heading', { name: '학교별 월 정산' })).toBeVisible();
	return { posts };
}

test('409 approval detail is submitted once automatically and updates the settlement without an approval dialog', async ({ page }) => {
	const { posts } = await fixture(page, [
		{ status: 409, detail: approval('digest-a', 42000) },
		{ status: 200, body: snapshot([changed, added], 42000) }
	]);
	await page.getByRole('button', { name: /월별 정산 다시 생성/ }).click();
	await expect.poll(() => posts.length).toBe(2);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(page.getByText('42,000원').first()).toBeVisible();
	expect(posts[0].body).toBeNull();
	expect(posts[1].body).toEqual({
		snapshotDigest: 'digest-a',
		newTotal: 42000,
		proposedDigest: 'proposal-digest-a'
	});
});

test('second regeneration conflict stops after one automatic retry and asks for a fresh click', async ({ page }) => {
	const { posts } = await fixture(page, [
		{ status: 409, detail: approval('digest-a', 42000) },
		{ status: 409, detail: approval('digest-b', 43000) },
		{ status: 200, body: snapshot([changed, added], 43000) }
	]);
	const generateButton = page.getByRole('button', { name: /월별 정산 다시 생성/ });
	await generateButton.click();
	await expect.poll(() => posts.length).toBe(2);
	await expect(page.getByText('정산 내용이 계속 변경되어 생성하지 못했습니다. 버튼을 다시 눌러 최신 내용으로 시도해주세요.')).toBeVisible();
	await expect(page.getByRole('dialog')).toHaveCount(0);
	expect(posts.map((post) => post.body)).toEqual([
		null,
		{ snapshotDigest: 'digest-a', newTotal: 42000, proposedDigest: 'proposal-digest-a' }
	]);
	await generateButton.click();
	await expect.poll(() => posts.length).toBe(3);
	expect(posts[2].body).toBeNull();
	await expect(page.getByText('43,000원').first()).toBeVisible();
});

test('mobile regeneration performs a single 409 retry without horizontal overflow or approval UI', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	const { posts } = await fixture(page, [
		{ status: 409, detail: approval('mobile-digest', 42000) },
		{ status: 200, body: snapshot([changed, added], 42000) }
	]);
	await page.getByRole('button', { name: /월별 정산 다시 생성/ }).click();
	await expect.poll(() => posts.length).toBe(2);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
	await page.screenshot({ path: 'test-results/aura-settlement-regeneration-mobile.png', fullPage: true });
});
