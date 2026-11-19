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

for(const width of [1440,390])test(`shared notebook daily migration and quick memo ${width}`,async({page})=>{
 await page.setViewportSize({width,height:1000});const state=await setup(page);
 await page.goto('/personal-project/calendar/today?date='+day);
 const root=page.locator('.daily-notebook');await expect(root).toHaveAttribute('data-notebook-version','2');
 await expect(root.locator('.ink-layer>path')).toHaveCount(1);
 await expect(root.getByText('기존 시간표 메모',{exact:true})).toBeVisible();
 expect((await root.boundingBox())!.width).toBeLessThanOrEqual(421);
 await expect(root.getByRole('region',{name:'선택한 도구 설정'})).toHaveCount(0);
 await root.getByRole('button',{name:'펜',exact:true}).click();
 await root.locator('.viewport').evaluate(e=>{e.scrollTop=0});
 const paper=root.locator('.paper');const r=(await paper.boundingBox())!;
 await page.mouse.move(r.x+100,r.y+100);await page.mouse.down();await page.mouse.move(r.x+150,r.y+120,{steps:5});await page.mouse.up();
 await expect(root.locator('.ink-layer>path')).toHaveCount(2);
 await expect.poll(()=>[...state.docs.keys()].some(k=>k.includes('note:day-ink:')&&k.endsWith(':v2'))).toBe(true);
 expect(state.docs.get('/api/personal/documents/pdf:day-ink:'+day)!.revision).toBe(3);
 await expect(root.locator('.daily-save-state')).toHaveText('서버에 저장됨');
 await page.reload();await expect(root.locator('.ink-layer>path')).toHaveCount(2);
 await page.keyboard.press('Control+Shift+m');await expect(page.locator('dialog[open] textarea[aria-label="메모 내용"]')).toHaveValue('남겨둔 메모');
 await page.mouse.click(2,2);await expect(page.locator('dialog[open]')).toHaveCount(0);
 await page.screenshot({path:'/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-v7-'+width+'.png',fullPage:true});
 expect(state.errors).toEqual([]);
});
