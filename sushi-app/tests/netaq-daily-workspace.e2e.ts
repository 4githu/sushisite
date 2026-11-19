import { test, expect, type Page } from '@playwright/test';
const day = '2026-11-16';
async function setup(page: Page) {
	let note = '남겨둔 메모',
		revision = 0,
		richDocument = '',
		noteWrites = 0,
		eventWrites = 0;
	const docs = new Map<string, { revision: number; data: any }>();
	const errors: string[] = [];
	page.on('pageerror', (e) => errors.push(e.message));
	const tasks = Array.from({ length: 17 }, (_, i) => ({
		id: 10 + i,
		title: i ? '할 일 ' + (i + 1) : '발표 자료 검토',
		description: '',
		startTime: day + 'T00:00:00',
		endTime: null,
		isAllDay: false,
		status: 'todo',
		taskUnplanned: true,
		canEdit: true,
		type: 'personal'
	}));
	const events: any[] = [
		{
			id: 1,
			title: '공학수학 2',
			description: '',
			startTime: day + 'T09:30:00',
			endTime: day + 'T10:45:00',
			isAllDay: false,
			status: 'passive',
			type: 'personal',
			canEdit: true
		}
	];
	// Include the exact legacy day-ink document: restoration must not require a new key or migration.
	docs.set('/api/personal/documents/pdf:day-ink:' + day, {
		revision: 3,
		data: {
			version: 1,
			pages: [
				{
					id: 'old-page',
					source: 0,
					rotation: 0,
					width: 420,
					height: 760,
					strokes: [
						{
							id: 'old-ink',
							kind: 'pen',
							color: '#25262b',
							width: 3,
							points: [
								{ x: 80, y: 400, pressure: 0.5 },
								{ x: 170, y: 420, pressure: 0.5 }
							]
						}
					],
					notes: [
						{ id: 'old-note', x: 80, y: 450, text: '기존 시간표 메모', color: '#25262b', size: 14 }
					]
				}
			]
		}
	});
	await page.clock.setFixedTime(new Date(day + 'T12:00:00+09:00'));
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: '991',
				data: { id: '991', name: '검수', email: 'test@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/api/personal/**', async (r) => {
		const path = decodeURIComponent(new URL(r.request().url()).pathname),
			method = r.request().method();
		const body = ['PUT', 'POST', 'PATCH'].includes(method) ? r.request().postDataJSON() : null;
		if (path.includes('/calendar/daily-notes/')) {
			if (method === 'GET')
				return r.fulfill({
					json: {
						content: note,
						drawing: 'original-drawing',
						richDocument,
						revision,
						inheritedFrom: null
					}
				});
			expect(body.revision).toBe(revision);
			note = body.content;
			richDocument = body.rich_document;
			revision++;
			noteWrites++;
			return r.fulfill({ json: { revision } });
		}
		if (path.includes('/documents/')) {
			const saved = docs.get(path) || {
				revision: 0,
				data: path.includes('netaq-captures') ? { items: [] } : null
			};
			if (method === 'GET') return r.fulfill({ json: saved });
			if (body.revision !== saved.revision)
				return r.fulfill({ status: 409, json: { detail: '문서 충돌' } });
			const next = { revision: saved.revision + 1, data: body.data };
			docs.set(path, next);
			return r.fulfill({ json: next });
		}
		if (path.endsWith('/calendar/tasks')) return r.fulfill({ json: tasks });
		if (path.endsWith('/calendar/events')) {
			if (method === 'POST') {
				eventWrites++;
				const e = {
					id: 100 + eventWrites,
					title: body.title,
					startTime: body.start_time,
					endTime: body.end_time,
					status: body.status,
					description: '',
					type: 'personal',
					taskUnplanned: body.task_unplanned,
					isAllDay: false
				};
				if (e.status === 'todo') tasks.push(e as any);
				else events.push(e);
				return r.fulfill({ json: e });
			}
			return r.fulfill({ json: events });
		}
		if (path.endsWith('/boards')) return r.fulfill({ json: { canAdmin: false, boards: [] } });
		if (path.endsWith('/drive/status'))
			return r.fulfill({
				json: { quotaBytes: 524288000, usedBytes: 0, transferDays: 15, googleAccounts: [] }
			});
		return r.fulfill({ json: method === 'POST' ? {} : [] });
	});
	return {
		note: () => note,
		noteWrites: () => noteWrites,
		docs,
		errors,
		eventWrites: () => eventWrites
	};
}
for (const width of [1440, 390])
	test(`compact daily workspace, existing ink, inline memo and outside dismissal ${width}`, async ({
		page
	}) => {
		await page.setViewportSize({ width, height: 1000 });
		const state = await setup(page);
		await page.goto('/personal-project/calendar/today?date=' + day);
		const paper = page.locator('.daily-compact .paper');
		await expect(page.getByRole('button', { name: '펜', exact: true })).toBeEnabled();
		await expect(page.locator('.daily-compact svg > path')).toHaveCount(1);
		await expect(page.getByText('기존 시간표 메모', { exact: true })).toBeVisible();
		expect((await paper.boundingBox())!.width).toBeLessThanOrEqual(421);
		await expect(page.getByRole('button', { name: /시간 배치$/ })).toHaveCount(0);
		expect(
			(await page.locator('.dp-task-list article').first().boundingBox())!.height
		).toBeLessThan(70);
		const inline = page.getByRole('complementary', { name: '오늘 메모' });
		const memo = inline.getByRole('textbox', { name: '메모 내용' });
		await expect(memo).toHaveValue('남겨둔 메모');
		expect(state.noteWrites()).toBe(0);
		await memo.fill('바로 적은 메모');
		await expect.poll(() => state.note()).toBe('바로 적은 메모');
		await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
		const dialog = page.getByRole('dialog', { name: '오늘 메모', exact: true });
		await expect(dialog.getByRole('textbox', { name: '메모 내용' })).toHaveValue('바로 적은 메모');
		await dialog.getByRole('textbox', { name: '메모 내용' }).fill('닫아도 남는 입력');
		await page.mouse.click(4, 4);
		await expect(dialog).not.toBeVisible();
		await expect(memo).toHaveValue('닫아도 남는 입력');
		await page.locator('.dp-task-title').first().click();
		const rect = (await paper.boundingBox())!;
		await paper.scrollIntoViewIfNeeded();
		const actual = (await paper.boundingBox())!;
		await page.mouse.click(
			actual.x + actual.width * 0.75,
			actual.y + (actual.height * (22 + 3 * 40)) / 760
		);
		await expect
			.poll(
				() => [...state.docs.entries()].filter(([key]) => key.includes('netaq-time-plan')).length
			)
			.toBe(1);
		expect(state.docs.get('/api/personal/documents/netaq-time-plan-v1:'+day)?.data.blocks[0].start).toBe(660);
		await page.screenshot({
			path: `/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-v6-${width}.png`,
			fullPage: true
		});
		expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
			true
		);
		expect(state.errors).toEqual([]);
	});
test('pen and time-grid text annotations persist alongside legacy ink', async ({ page }) => {
	const state = await setup(page);
	await page.goto('/personal-project/calendar/today');
	await page.getByRole('button', { name: '펜', exact: true }).click();
	const area = page.getByLabel('PDF 필기 영역', { exact: true });
	await expect(area).toBeVisible();
	const box = (await area.boundingBox())!;
	await page.mouse.move(box.x + 80, box.y + 100);
	await page.mouse.down();
	for (let i = 0; i < 12; i++) await page.mouse.move(box.x + 80 + i * 5, box.y + 100 + i * 2);
	await page.mouse.up();
	await expect
		.poll(
			() =>
				state.docs.get('/api/personal/documents/pdf:day-ink:' + day)?.data.pages[0].strokes.length
		)
		.toBe(2);
	await page.getByRole('button', { name: '메모', exact: true }).click();
	await page.mouse.click(box.x + 90, box.y + 170);
	const dialog = page.getByRole('dialog', { name: '시간표 메모', exact: true });
	await dialog.getByRole('textbox', { name: '시간표에 쓸 메모' }).fill('대충 적는 계획');
	await dialog.getByRole('button', { name: '적용', exact: true }).click();
	await expect
		.poll(
			() => state.docs.get('/api/personal/documents/pdf:day-ink:' + day)?.data.pages[0].notes.length
		)
		.toBe(2);
	await page.reload();
	await expect(page.getByText('대충 적는 계획', { exact: true })).toBeVisible();
	await expect(page.locator('.daily-compact svg > path')).toHaveCount(2);
	expect(state.errors).toEqual([]);
});
test('quick title inputs add tasks and appointments without the full schedule dialog', async ({
	page
}) => {
	const state = await setup(page);
	await page.goto('/personal-project/calendar/today');
	const task = page.getByRole('textbox', { name: '할 일 바로 추가' });
	await task.fill('새 할 일');
	await task.press('Enter');
	await expect.poll(() => state.eventWrites()).toBe(1);
	await expect(page.getByRole('button', { name: /새 할 일/ })).toBeVisible();
	const event = page.getByRole('textbox', { name: '일정 바로 추가' });
	await event.fill('점심 약속');
	await event.press('Enter');
	await expect.poll(() => state.eventWrites()).toBe(2);
	await expect(page.getByRole('button', { name: '점심 약속 일정 열기' })).toBeVisible();
	await expect(page.locator('.cw-dialog[open]')).toHaveCount(0);
});
test('profile owns widget and school settings; navigation icons inherit the selected color', async ({
	page
}) => {
	await setup(page);
	await page.goto('/personal-project/calendar/today');
	await expect(
		page
			.getByRole('navigation', { name: '캘린더' })
			.getByRole('link', { name: '위젯', exact: true })
	).toHaveCount(0);
	await expect(
		page
			.getByRole('navigation', { name: '학생서비스' })
			.getByRole('link', { name: '학교 설정', exact: true })
	).toHaveCount(0);
	await page.locator('.account-button').click();
	await expect(
		page.getByLabel('프로필 옵션').getByRole('link', { name: '학교 설정', exact: true })
	).toBeVisible();
	await expect(
		page.getByLabel('프로필 옵션').getByRole('link', { name: '위젯 설치·연결', exact: true })
	).toBeVisible();
	await page.locator('h1').click();
	await expect(page.getByLabel('프로필 옵션')).toHaveCount(0);
	const today = page.getByRole('link', { name: '오늘', exact: true }).first(),
		calendar = page.getByRole('link', { name: '캘린더', exact: true }).first();
	expect(
		await today.locator('.ondo-nav-icon').evaluate((el) => getComputedStyle(el).backgroundColor)
	).toBe('rgb(196, 65, 44)');
	expect(
		await calendar.locator('.ondo-nav-icon').evaluate((el) => getComputedStyle(el).backgroundColor)
	).not.toBe('rgb(196, 65, 44)');
	await page.getByRole('button', { name: '09:00', exact: true }).click();
	await expect(page.getByRole('dialog', { name: '새 일정' })).toBeVisible();
	await page.mouse.click(4, 4);
	await expect(page.getByRole('dialog', { name: '새 일정' })).not.toBeVisible();
});

test('planning another day keeps its own blocks and restores the original day ink',async({page})=>{
 const state=await setup(page);await page.goto('/personal-project/calendar/today?date='+day);await page.getByRole('button',{name:'펜',exact:true}).isEnabled();await expect(page.getByRole('button',{name:'일정',exact:true})).toBeEnabled();await page.locator('.dp-task-title').first().click();const paper=page.locator('.daily-compact .paper');const r=(await paper.boundingBox())!;await page.mouse.click(r.x+r.width*.75,r.y+r.height*142/760);await expect.poll(()=>state.docs.get('/api/personal/documents/netaq-time-plan-v1:'+day)?.data.blocks.length).toBe(1);await page.getByRole('button',{name:'다음 기간',exact:true}).click();await expect(page).toHaveURL(/date=2026-11-17/);await expect(page.getByRole('button',{name:'일정',exact:true})).toBeEnabled();await expect(page.locator('.daily-compact .planned')).toHaveCount(0);await page.getByRole('button',{name:'이전 기간',exact:true}).click();await expect(page).toHaveURL(/date=2026-11-16/);await expect(page.locator('.daily-compact .planned')).toHaveCount(1);await expect(page.getByText('기존 시간표 메모',{exact:true})).toBeVisible();
});
