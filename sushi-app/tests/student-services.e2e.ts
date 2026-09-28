import { test, expect, type Page } from '@playwright/test';
const api = process.env.STUDENT_TEST_API_URL || '';
test.skip(
	!api,
	'Run with the isolated tests/support/student_test_server.py server and STUDENT_TEST_API_URL.'
);
const term = '2026_U000200002U000300001';
const artifacts = process.env.STUDENT_REVIEW_DIR || 'test-results/student-review';
import { mkdirSync } from 'node:fs';
test.beforeAll(() => mkdirSync(artifacts, { recursive: true }));
test.describe.configure({ mode: 'serial' });
async function setup(page: Page) {
	let note = { content: '', drawing: '', richDocument: '', inheritedFrom: null };
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: '7890',
				data: { id: '7890', name: '검수 계정', email: 'review@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/api/personal/**', async (r) => {
		const u = new URL(r.request().url());
		if (u.pathname.includes('/student/'))
			return r.fulfill({ response: await r.fetch({ url: api + u.pathname + u.search }) });
		if (u.pathname.includes('/daily-notes/')) {
			if (r.request().method() === 'PUT') {
				const b = r.request().postDataJSON();
				note = {
					content: b.content,
					drawing: b.drawing,
					richDocument: b.rich_document,
					inheritedFrom: null
				};
			}
			return r.fulfill({ json: note });
		}
		return r.fulfill({ json: [] });
	});
}
async function reset(page: Page) {
	const draft = (
		await (
			await page.request.get(`${api}/api/personal/student/timetable/draft?term=${term}`)
		).json()
	).draft;
	await page.request.put(`${api}/api/personal/student/timetable/draft?term=${term}`, {
		data: {
			course_ids: [],
			manual_lessons: [],
			starts_on: '2026-09-01',
			ends_on: '2026-12-20',
			skip_holidays: true,
			excluded_dates: [],
			revision: draft?.revision || 0
		}
	});
}
test('real SNU course search, conflict prevention, save/reload and calendar import', async ({
	page
}) => {
	await setup(page);
	await reset(page);
	await page.setViewportSize({ width: 1440, height: 1000 });
	await page.goto('/personal-project/calendar/student/timetable');
	await page.getByLabel('강의 검색어').fill('자료구조 강유');
	await page.getByRole('button', { name: '검색', exact: true }).click();
	await expect(page.locator('.course')).toHaveCount(1);
	await page.getByRole('button', { name: '자료구조 001 담기', exact: true }).click();
	await expect(page.locator('.class-block')).toHaveCount(2);
	await page.getByText('수업 직접 입력', { exact: true }).click();
	await page.getByLabel('직접 입력 과목명').fill('겹치는 강의');
	await page.getByLabel('직접 입력 시작').fill('10:00');
	await page.getByRole('button', { name: '수업 담기', exact: true }).click();
	await expect(page.getByRole('alert')).toContainText('겹칩니다');
	await page.getByRole('button', { name: '시간표 저장', exact: true }).click();
	await expect(page.locator('.notice[role=status]')).toContainText('시간표를 저장했습니다.');
	await page.reload();
	await expect(page.locator('.class-block')).toHaveCount(2);
	await page.screenshot({ path: `${artifacts}/timetable-desktop.png`, fullPage: true });
	await page.getByRole('button', { name: '캘린더 등록 미리보기', exact: true }).click();
	await expect(
		page.getByRole('button', { name: '내 캘린더로 가져오기', exact: true })
	).toBeEnabled();
	await page.getByLabel('종강', { exact: true }).fill('2026-12-19');
	await expect(
		page.getByRole('button', { name: '내 캘린더로 가져오기', exact: true })
	).toBeDisabled();
	await page.getByRole('button', { name: '캘린더 등록 미리보기', exact: true }).click();
	await page.getByRole('button', { name: '내 캘린더로 가져오기', exact: true }).click();
	await expect(page.locator('.notice[role=status]')).toContainText(/캘린더에 추가|이미 가져온/);
	await page.getByRole('button', { name: '내 캘린더로 가져오기', exact: true }).click();
	await expect(page.locator('.notice[role=status]')).toContainText('이미 가져온');
});
test('mobile timetable fits and sidebar opens student destinations directly', async ({ page }) => {
	await setup(page);
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto('/personal-project/calendar/student/timetable');
	await expect(page.locator('.class-block')).toHaveCount(2);
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.screenshot({ path: `${artifacts}/timetable-mobile.png`, fullPage: true });
	await page.getByRole('button', { name: '사이드바 펼치기', exact: true }).click();
	await page
		.getByRole('navigation', { name: '학생서비스', exact: true })
		.getByRole('link', { name: '수강계획', exact: true })
		.click();
	await expect(
		page.getByRole('heading', { name: '수강계획과 이수규정', exact: true })
	).toBeVisible();
	await page.getByRole('button', {name:'전공 탐색',exact:true}).click();
	await expect(page.locator('.metrics')).toContainText('39');
	await expect(page.locator('.rule')).toContainText('자료구조');
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.screenshot({ path: `${artifacts}/curriculum-mobile.png`, fullPage: true });
});
test('official meals display inside the app and all cards collapse', async ({ page }) => {
	await setup(page);
	// Snapshot of official source, already parsed by the backend fixture test. No external network in UI tests.
	await page.route('**/api/personal/student/meals?**', (r) =>
		r.fulfill({
			json: {
				date: '2026-09-27',
				restaurants: [
					{
						title: '기숙사식당 (881-9072)',
						breakfast: '',
						lunch: '추석연휴 휴무',
						dinner: '추석연휴 휴무'
					},
					{
						title: '학생회관식당',
						breakfast: '등록된 메뉴 없음',
						lunch: '등록된 메뉴 없음',
						dinner: '등록된 메뉴 없음'
					}
				],
				fetchedAt: '2026-09-27T04:00:00Z',
				stale: false
			}
		})
	);
	await page.goto('/personal-project/calendar/student/meals');
	await expect(page.locator('.restaurants')).toContainText('추석연휴 휴무');
	await page.getByRole('button', { name: '모두 펼치기', exact: true }).click();
	await expect(page.locator('.restaurants details[open]')).toHaveCount(2);
	await page.getByRole('button', { name: '모두 접기', exact: true }).click();
	await expect(page.locator('.restaurants details[open]')).toHaveCount(0);
	await page.setViewportSize({ width: 390, height: 844 });
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
	await page.screenshot({ path: `${artifacts}/meals-mobile.png`, fullPage: true });
});
test('folded note content survives saving and ink board can collapse', async ({ page }) => {
	await setup(page);
	await page.goto('/personal-project/calendar/day?date=2026-09-27');
	await page.getByRole('button', { name: '서식 편집기 사용', exact: true }).click();
	await page.getByText('텍스트 서식 도구', { exact: true }).click();
	await page.getByRole('button', { name: '토글 목록 추가', exact: true }).click();
	await expect(page.getByRole('button', { name: '새 토글 접기', exact: true })).toBeVisible();
	await page.getByRole('button', { name: '새 토글 접기', exact: true }).click();
	await expect(page.getByText('내용을 입력하세요', { exact: true })).toBeHidden();
	await page.getByRole('button', { name: '메모 저장', exact: true }).click();
	await page.reload();
	await expect(page.getByRole('button', { name: '새 토글 펼치기', exact: true })).toBeVisible();
	await expect(page.getByText('내용을 입력하세요', { exact: true })).toBeHidden();
	await page.getByRole('button', { name: '새 토글 펼치기', exact: true }).click();
	await expect(page.getByText('내용을 입력하세요', { exact: true })).toBeVisible();
	await page.getByText('펜 메모 · 접기/펼치기', { exact: true }).click();
	await expect(page.getByLabel('펜으로 작성하는 메모')).toBeHidden();
	await page.getByText('펜 메모 · 접기/펼치기', { exact: true }).click();
	await expect(page.getByLabel('펜으로 작성하는 메모')).toBeVisible();
	await page.screenshot({ path: `${artifacts}/notes-desktop.png`, fullPage: true });
});

test('current majors persist and compare; philosophy notes remain readable', async ({page})=>{
 await setup(page);
 const old=await (await page.request.get(`${api}/api/personal/student/major-plan`)).json();
 await page.request.put(`${api}/api/personal/student/major-plan`,{data:{items:[],revision:old.revision}});
 await page.goto('/personal-project/calendar/student/plan');
 await page.getByRole('button',{name:'현재 전공 추가',exact:true}).click();
 await page.getByRole('combobox',{name:'전공 유형',exact:true}).selectOption('multi');
 await page.getByRole('button',{name:'+ 현재 전공에 추가',exact:true}).click();
 await expect(page.locator('.major-card')).toHaveCount(1);
 await page.getByRole('button',{name:'현재 전공 추가',exact:true}).click();
 await page.getByRole('combobox',{name:'전공 유형',exact:true}).selectOption('double');
 await page.getByRole('button',{name:'+ 현재 전공에 추가',exact:true}).click();
 await expect(page.locator('.major-card')).toHaveCount(2);
 await page.reload();
 await expect(page.locator('.major-card')).toHaveCount(2);
 await page.screenshot({path:`${artifacts}/major-comparison-desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.screenshot({path:`${artifacts}/major-comparison-mobile.png`,fullPage:true});
 await page.getByRole('button',{name:'전공 탐색',exact:true}).click();
 await page.getByRole('combobox',{name:'학과',exact:true}).selectOption('철학과');
 await expect(page.locator('.rule')).toContainText('자료 확인 필요');
 await expect(page.locator('.rule details[open]').last()).not.toContainText('SPA-blocked');
 await expect(page.locator('.rule details[open]').last()).toContainText('임시 기준');
});
