import { test, expect, type Page } from '@playwright/test';
async function setup(page: Page) {
	const events: any[] = [
		{
			id: 1,
			title: '스시과 세미나',
			description: '준비 자료 확인',
			startTime: '2026-09-16T09:00:00+09:00',
			endTime: '2026-09-16T10:00:00+09:00',
			isAllDay: false,
			status: 'todo',
			type: 'personal',
			categoryName: '동아리',
			projectId: 1,
			location: '301호',
			webUrl: 'https://example.com',
			recurrenceGroupId: null,
			recurrenceIndex: null,
			canEdit: true
		},
		{
			id: 2,
			title: '아우라 클리닉',
			description: '',
			startTime: '2026-09-17T16:00:00+09:00',
			endTime: '2026-09-17T17:00:00+09:00',
			isAllDay: false,
			status: 'passive',
			type: 'aura',
			categoryName: null,
			recurrenceGroupId: null,
			recurrenceIndex: null,
			canEdit: true
		}
	];
	await page.clock.install({ time: new Date('2026-09-16T10:00:00+09:00') });
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: { sub: '1', data: { id: '1', name: '지후', email: 'test@gmail.com' }, exp: 9999999999 }
		})
	);
	await page.route('**/api/personal/**', async (r) => {
		const url = new URL(r.request().url()),
			path = url.pathname,
			method = r.request().method();
		if (path.endsWith('/calendar/projects'))
			return r.fulfill({ json: [{ id: 1, name: '스시과 일정', memberCount: 3 }] });
		if (path.endsWith('/google/accounts')) return r.fulfill({ json: [] });
		if (path.endsWith('/calendar/tasks'))
			return r.fulfill({ json: events.filter((e) => e.status !== 'passive') });
		if (path.endsWith('/calendar/events')) {
			if (method === 'POST') {
				const b = r.request().postDataJSON();
				const e = {
					id: events.length + 10,
					title: b.title,
					description: b.description,
					startTime: b.start_time,
					endTime: b.end_time,
					isAllDay: b.is_all_day,
					status: b.status,
					type: b.type,
					categoryName: b.category_name,
					projectId: b.project_id,
					location: b.location,
					webUrl: b.web_url,
					canEdit: true
				};
				events.push(e);
				return r.fulfill({ json: e, status: 201 });
			}
			return r.fulfill({ json: events });
		}
		const id = Number(path.match(/events\/(\d+)/)?.[1]);
		if (id) {
			const e = events.find((e) => e.id === id);
			if (method === 'DELETE') {
				events.splice(events.indexOf(e), 1);
				return r.fulfill({ status: 204 });
			}
			if (method === 'PATCH') {
				const b = r.request().postDataJSON();
				if (b.title) e.title = b.title;
				if (b.status) e.status = b.status;
				return r.fulfill({ json: e });
			}
			return r.fulfill({ json: e });
		}
		return r.fulfill({ json: [] });
	});
	return events;
}
test('주간 빈 시간 클릭으로 생성하고 같은 창에서 수정·삭제한다', async ({ page }) => {
	await setup(page);
	await page.goto('/personal-project/calendar/week');
	await page.getByRole('button', { name: '2026-09-16 11시 정각 일정 추가', exact: true }).click();
	const dialog = page.getByRole('dialog');
	await expect(dialog).toBeVisible();
	await dialog.getByLabel('제목', { exact: true }).fill('새 회의');
	await dialog.getByLabel('장소', { exact: true }).fill('회의실');
	await dialog.getByRole('button', { name: '저장', exact: true }).click();
	await expect(dialog).not.toBeVisible();
	await page.getByRole('button', { name: /새 회의/ }).click();
	await expect(dialog.getByLabel('장소', { exact: true })).toHaveValue('회의실');
	page.once('dialog', (d) => d.accept());
	await dialog.getByRole('button', { name: '삭제', exact: true }).click();
	await expect(page.getByRole('button', { name: /새 회의/ })).toHaveCount(0);
});
test('아우라 일정 클릭은 편집창이고 카테고리·할 일 필터가 동작한다', async ({ page }) => {
	await setup(page);
	await page.goto('/personal-project/calendar');
	await page.getByRole('button', { name: /아우라 클리닉/ }).click();
	await expect(page.getByRole('dialog')).toBeVisible();
	await expect(page).toHaveURL(/\/calendar$/);
	await page.getByRole('dialog').getByRole('button', { name: '닫기', exact: true }).last().click();
	await page.getByRole('button', { name: '표시할 캘린더', exact: true }).click();
	await page.getByLabel('동아리', { exact: true }).uncheck();
	await expect(page.locator('.cw-event').filter({ hasText: '스시과 세미나' })).toHaveCount(0);
	await page.getByLabel('동아리', { exact: true }).check();
	await page.getByRole('button', { name: '할 일', exact: true }).click();
	await page.getByRole('checkbox', { name: '스시과 세미나 완료' }).check();
	await expect(page.locator('.cw-task')).toHaveCount(0);
	await page.getByLabel('완료한 할 일').check();
	await expect(page.locator('.cw-task')).toHaveCount(1);
});
test('모바일 캘린더와 연결 패널, 설치 manifest', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await setup(page);
	await page.goto('/personal-project/calendar');
	await expect(page.locator('.cw-month')).toBeVisible();
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
	await page.screenshot({ path: '/private/tmp/ondo-mobile.png', fullPage: true });
	await page.getByRole('button', { name: '연결·공유', exact: true }).click();
	await expect(page.getByRole('link', { name: '계정 추가', exact: true })).toHaveAttribute(
		'href',
		/purpose=calendar/
	);
	const manifest = await page.request.get('/pwa/calendar/manifest.webmanifest');
	expect((await manifest.json()).display).toBe('standalone');
});
test('데스크톱 월간 시각 검증', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	await setup(page);
	await page.goto('/personal-project/calendar');
	await expect(page.locator('.cw-event').first()).toBeVisible();
	await page.screenshot({ path: '/private/tmp/ondo-desktop.png', fullPage: true });
});
