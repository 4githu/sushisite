import { test, expect, type Page } from '@playwright/test';
const day = '2026-11-16';
async function setup(page: Page, { failNote = false, failPlan = false } = {}) {
	let note = '- [ ] 기기 대여 안내하기\n- [x] 질문 회신하기',
		richDocument = '{"document":{"blocks":[]}}',
		revision = 0,
		noteWrites = 0,
		planWrites = 0,
		eventWrites = 0;
	let offline = false;
	let failNextNote = failNote,
		failNextPlan = failPlan;
	const plans = new Map<string, { revision: number; data: any }>();
	const tasks: any[] = [
		{
			id: 10,
			title: '발표 자료 검토',
			description: '',
			startTime: day + 'T00:00:00',
			endTime: day + 'T18:00:00',
			isAllDay: true,
			status: 'todo',
			taskUnplanned: false,
			taskDueAt: day + 'T18:00:00',
			canEdit: true,
			type: 'personal',
			categoryName: '학교'
		},
		{
			id: 11,
			title: '보고서 참고문헌 정리',
			description: '',
			startTime: day + 'T00:00:00',
			endTime: null,
			isAllDay: false,
			status: 'todo',
			taskUnplanned: true,
			canEdit: true,
			type: 'personal'
		},
		{
			id: 12,
			title: '기기 대여 문의',
			description: '',
			startTime: day + 'T00:00:00',
			endTime: null,
			isAllDay: false,
			status: 'todo',
			taskUnplanned: true,
			canEdit: true,
			type: 'personal'
		}
	];
	const events = [
		{
			id: 1,
			title: '공학수학 2',
			description: '',
			startTime: day + 'T09:30:00',
			endTime: day + 'T10:45:00',
			isAllDay: false,
			status: 'passive',
			type: 'personal',
			location: '43-1-302',
			canEdit: true
		},
		{
			id: 2,
			title: '일반미생물학',
			description: '',
			startTime: day + 'T13:00:00',
			endTime: day + 'T15:50:00',
			isAllDay: false,
			status: 'passive',
			type: 'google',
			location: '200-6112',
			canEdit: false
		}
	];
	const captures = [
		{
			id: 'widget-record',
			text: '위젯에서 적어둔 내용',
			createdAt: day + 'T10:00:00',
			kind: 'inbox',
			today: null,
			done: false
		}
	];
	await page.clock.setFixedTime(new Date(day + 'T12:00:00+09:00'));
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: '991',
				data: { id: '991', name: '내 프로필', email: 'test@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/api/personal/**', async (r) => {
		const path = new URL(r.request().url()).pathname,
			method = r.request().method(),
			body = method === 'PUT' || method === 'PATCH' ? r.request().postDataJSON() : null;
		if (path.includes('/calendar/daily-notes/')) {
			if (method === 'GET' && offline)
				return r.fulfill({ status: 503, json: { detail: '연결하지 못했어요' } });
			if (method === 'GET')
				return r.fulfill({
					json: {
						content: note,
						richDocument,
						drawing: 'preserved-ink',
						revision,
						inheritedFrom: revision ? null : '2026-11-14'
					}
				});
			if (failNextNote) {
				failNextNote = false;
				return r.fulfill({ status: 503, json: { detail: '저장 실패' } });
			}
			if (body.revision !== revision)
				return r.fulfill({ status: 409, json: { detail: '다른 화면에서 변경' } });
			expect(body.drawing).toBe('preserved-ink');
			note = body.content;
			richDocument = body.rich_document;
			revision++;
			noteWrites++;
			return r.fulfill({ json: { revision } });
		}
		if (path.includes('/documents/netaq-time-plan-v1:')) {
			const state = plans.get(path) || { revision: 0, data: { blocks: [] } };
			if (method === 'GET') return r.fulfill({ json: state });
			if (failNextPlan) {
				failNextPlan = false;
				return r.fulfill({ status: 503, json: { detail: '계획 저장 실패' } });
			}
			if (body.revision !== state.revision)
				return r.fulfill({ status: 409, json: { detail: '계획 충돌' } });
			const next = { revision: state.revision + 1, data: body.data };
			plans.set(path, next);
			planWrites++;
			return r.fulfill({ json: next });
		}
		if (path.endsWith('/documents/netaq-captures-v1'))
			return r.fulfill({ json: { revision: 0, data: { items: captures } } });
		if (path.endsWith('/calendar/tasks')) return r.fulfill({ json: tasks });
		if (/\/calendar\/events\/\d+$/.test(path) && method === 'PATCH') {
			eventWrites++;
			const i = tasks.findIndex((t) => String(t.id) === path.split('/').at(-1));
			tasks[i] = { ...tasks[i], ...body };
			return r.fulfill({ json: tasks[i] });
		}
		if (path.endsWith('/calendar/events')) return r.fulfill({ json: events });
		if (path.endsWith('/calendar/projects')) return r.fulfill({ json: [] });
		if (path.endsWith('/boards')) return r.fulfill({ json: { canAdmin: false, boards: [] } });
		return r.fulfill({ json: method === 'POST' ? {} : [] });
	});
	return {
		offline: (value: boolean) => (offline = value),
		note: () => note,
		noteWrites: () => noteWrites,
		rich: () => richDocument,
		plans: () => [...plans.values()].flatMap((p) => p.data.blocks),
		planWrites: () => planWrites,
		eventWrites: () => eventWrites,
		remoteChange: () => {
			note = '다른 화면에서 추가한 문장';
			revision++;
		}
	};
}
test('unsaved memo survives close, navigation, reload and a failed save', async ({ page }) => {
	const state = await setup(page, { failNote: true });
	await page.goto('/personal-project/calendar/today');
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	const memo = page.getByRole('dialog', { name: '오늘 메모' }),
		input = memo.getByRole('textbox', { name: '메모 내용' });
	await expect(input).toBeEnabled();
	await input.fill('작성 중인 원문');
	await memo.getByRole('button', { name: '메모 닫기' }).click();
	await page.getByRole('link', { name: '내 드라이브', exact: true }).click();
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	await expect(input).toHaveValue(/작성 중인 원문/);
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('alert')).toContainText('저장 실패');
	await expect(input).toHaveValue(/작성 중인 원문/);
	await memo.getByRole('button', { name: '메모 닫기' }).click();
	await page.reload();
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	await expect(input).toHaveValue(/작성 중인 원문/);
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('status')).toContainText('저장됨');
	expect(state.note()).toContain('작성 중인 원문');
});
test('concurrent memo changes are shown and can be merged without overwriting either side', async ({
	page
}) => {
	const state = await setup(page);
	await page.goto('/personal-project/calendar/today');
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	const memo = page.getByRole('dialog', { name: '오늘 메모' }),
		input = memo.getByRole('textbox', { name: '메모 내용' });
	await expect(input).toBeEnabled();
	await input.fill('내 입력');
	state.remoteChange();
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('alert')).toContainText('다른 화면');
	await memo.locator('summary').click();
	await expect(memo.locator('pre')).toContainText('다른 화면에서 추가한 문장');
	await memo.getByRole('button', { name: '최신 메모 뒤에 내 내용 추가' }).click();
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('status')).toContainText('저장됨');
	expect(state.note()).toBe('다른 화면에서 추가한 문장\n\n내 입력');
});
test('a local draft remains readable and editable when reopening offline', async ({ page }) => {
	const state = await setup(page);
	await page.goto('/personal-project/calendar/today');
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	const memo = page.getByRole('dialog', { name: '오늘 메모' }),
		input = memo.getByRole('textbox', { name: '메모 내용' });
	await expect(input).toBeEnabled();
	await input.fill('오프라인에도 남을 원문');
	await memo.getByRole('button', { name: '메모 닫기' }).click();
	state.offline(true);
	await page.reload();
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	await expect(input).toHaveValue('오프라인에도 남을 원문');
	await expect(input).toBeEnabled();
	await expect(memo.getByRole('button', { name: '저장', exact: true })).toBeDisabled();
	await input.fill('오프라인에도 남을 원문과 추가 입력');
	await memo.getByRole('button', { name: '메모 닫기' }).click();
	await page.reload();
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	await expect(input).toHaveValue('오프라인에도 남을 원문과 추가 입력');
	state.offline(false);
	await memo.getByRole('button', { name: '다시 불러오기', exact: true }).click();
	await expect(input).toHaveValue('오프라인에도 남을 원문과 추가 입력');
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('status')).toContainText('저장됨');
	expect(state.note()).toBe('오프라인에도 남을 원문과 추가 입력');
});

test('foreground account refresh does not strand the memo loader', async ({ page }) => {
	await setup(page);
	await page.goto('/personal-project/calendar/today');
	await expect(page.getByRole('button', { name: '빠른 기록', exact: true })).toBeVisible();
	await page.route('**/auth/isjwt?key=mainauth', async (r) => {
		await new Promise((resolve) => setTimeout(resolve, 180));
		return r.fulfill({
			json: {
				sub: '991',
				data: { id: '991', name: '내 프로필', email: 'test@example.com' },
				exp: 9999999999
			}
		});
	});
	await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	const memo = page.getByRole('dialog', { name: '오늘 메모' });
	await expect(memo.getByRole('textbox', { name: '메모 내용' })).toBeEnabled();
	await expect(memo.getByRole('textbox', { name: '메모 내용' })).toHaveValue(/기기 대여 안내하기/);
});

test('changing accounts while a memo is open never writes the previous account text', async ({
	page
}) => {
	const state = await setup(page);
	await page.goto('/personal-project/calendar/today');
	await page.getByRole('button', { name: '빠른 기록', exact: true }).click();
	const memo = page.getByRole('dialog', { name: '오늘 메모' }),
		input = memo.getByRole('textbox', { name: '메모 내용' });
	await expect(input).toBeEnabled();
	await input.fill('이전 계정의 비공개 입력');
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: '992',
				data: { id: '992', name: '다른 계정', email: 'other@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
	await memo.getByRole('button', { name: '저장', exact: true }).click();
	await expect(memo.getByRole('alert')).toContainText('계정이 바뀌었어요');
	expect(state.noteWrites()).toBe(0);
});
