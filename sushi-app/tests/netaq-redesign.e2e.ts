import { test, expect, type Page } from '@playwright/test';
async function setup(page: Page) {
	const writes: any[] = [];
	let folders: any[] = [],
		placements: Record<string, string> = {},
		shared: string[] = [];
	const files = [
		{
			id: 'f1',
			name: '실험 노트.txt',
			bucket: 'archive',
			provider: 'local',
			accountId: null,
			mimeType: 'text/plain',
			byteSize: 120,
			createdAt: '2026-11-16T00:00:00Z',
			expiresAt: null
		}
	];
	await page.clock.install({ time: new Date('2026-11-16T12:00:00+09:00') });
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
		const url = new URL(r.request().url()),
			path = url.pathname,
			method = r.request().method(),
			body = method === 'GET' ? null : r.request().postDataJSON();
		if (method !== 'GET') writes.push({ path, method, body });
		if (path.endsWith('/drive/status'))
			return r.fulfill({
				json: { quotaBytes: 524288000, usedBytes: 120, transferDays: 15, googleAccounts: [] }
			});
		if (path.endsWith('/drive/items')) return r.fulfill({ json: files });
		if (path.endsWith('/drive/library')) {
			const fid = url.searchParams.get('folder_id');
			return r.fulfill({
				json: {
					folders: folders.filter((f) => f.parent_id === fid),
					allFolders: folders,
					trail: fid ? folders.filter((f) => f.id === fid) : [],
					placements,
					shared
				}
			});
		}
		if (path.endsWith('/drive/folders')) {
			folders.push({
				id: 'folder1',
				name: body.name,
				parent_id: body.parent_id,
				created_at: '2026-11-16T00:00:00Z'
			});
			return r.fulfill({ status: 201, json: { id: 'folder1' } });
		}
		if (path.endsWith('/organization')) {
			files[0].name = body.name;
			if (body.folder_id) placements.f1 = body.folder_id;
			else delete placements.f1;
			return r.fulfill({ json: { ok: true } });
		}
		if (path.endsWith('/preview'))
			return r.fulfill({ json: { kind: 'text', text: '실험 준비 사항\n다음 주 시약 확인' } });
		if (path.endsWith('/share')) {
			if (method === 'DELETE') {
				shared = [];
				return r.fulfill({ status: 204 });
			}
			shared = ['f1'];
			return r.fulfill({
				json: { token: 'isolated-share-token', expiresAt: '2026-11-23T01:00:00Z' }
			});
		}
		if (path.endsWith('/boards'))
			return r.fulfill({
				json: {
					canAdmin: false,
					canCreate: false,
					boards: [
						{
							id: 1,
							name: '자료공유',
							parent_id: null,
							realm: 'main',
							post_count: 2,
							last_title: '분자생물학 기말 정리 자료',
							permissions: { read: true, post: true }
						}
					]
				}
			});
		if (path.includes('/boards/1/posts'))
			return r.fulfill({
				json: {
					posts: [
						{
							id: 1,
							title: '분자생물학 기말 정리 자료',
							excerpt:
								'이번 학기 시험 범위에 맞춰 정리했어요. 빠진 내용이 있으면 댓글로 알려주세요.',
							author_id: 1,
							author_name: '지후',
							pinned: 0,
							revision: 1,
							created_at: '2026-11-16',
							comments: 8
						},
						{
							id: 2,
							title: '실험 보고서 참고문헌 형식 질문',
							excerpt: '학과 양식에서 DOI는 어디에 적으면 될까요?',
							author_id: 2,
							author_name: '민서',
							pinned: 0,
							revision: 1,
							created_at: '2026-11-15',
							comments: 3
						}
					],
					total: 2,
					page: 1
				}
			});
		if (
			path.includes('/calendar/events/series') ||
			(path.endsWith('/calendar/events') && method === 'POST')
		)
			return r.fulfill({ status: 201, json: [] });
		if (path.endsWith('/calendar/events'))
			return r.fulfill({
				json: [
					{
						id: 10,
						title: '1시간 일정',
						startTime: '2026-11-16T09:00:00+09:00',
						endTime: '2026-11-16T10:00:00+09:00',
						isAllDay: false,
						status: 'passive',
						type: 'personal',
						description: '',
						location: '',
						categoryName: '공부',
						canEdit: true
					},
					{
						id: 11,
						title: '2시간 일정',
						startTime: '2026-11-16T11:00:00+09:00',
						endTime: '2026-11-16T13:00:00+09:00',
						isAllDay: false,
						status: 'passive',
						type: 'personal',
						description: '',
						location: '실험실',
						categoryName: '공부',
						canEdit: true
					}
				]
			});
		if (path.includes('/documents/')) return r.fulfill({ json: { revision: 0, data: null } });
		if (path.includes('/calendar/daily-notes/'))
			return r.fulfill({
				json: { content: '', drawing: '', richDocument: '', revision: 0, inheritedFrom: null }
			});
		return r.fulfill({ json: method === 'POST' ? {} : [] });
	});
	return { writes, folders, files };
}
for (const width of [1440, 390]) {
	test(`drive folders, rename, move, share and preview at ${width}px`, async ({ page }) => {
		await page.setViewportSize({ width, height: 960 });
		await setup(page);
		await page.goto('/personal-project/calendar/drive');
		await page.getByRole('button', { name: '＋ 새 폴더', exact: true }).click();
		await page.getByRole('textbox', { name: '폴더 이름', exact: true }).fill('생명과학');
		await page.getByRole('button', { name: '만들기', exact: true }).click();
		await expect(page.getByRole('dialog', { name: '새 폴더' })).toBeHidden();
		await page.getByRole('button', { name: /실험 노트.txt/ }).click();
		await expect(page.getByRole('textbox', { name: '실험 노트.txt 편집' })).toHaveValue(
			/실험 준비/
		);
		await page.getByRole('button', { name: '이름·이동·공유', exact: true }).click();
		const modal = page.getByRole('dialog', { name: '파일 관리', exact: true });
		await modal.getByLabel('파일 이름', { exact: true }).fill('새 실험 노트.txt');
		await modal.getByRole('combobox', { name: '폴더', exact: true }).selectOption('folder1');
		await modal.getByRole('button', { name: '변경 저장', exact: true }).click();
		await expect(modal.getByRole('status')).toContainText('파일 정보를 저장했어요');
		await modal.getByRole('button', { name: '공유 링크 만들기', exact: true }).click();
		await expect(modal.getByRole('textbox', { name: '공유 링크', exact: true })).toHaveValue(
			/\/share\/isolated-share-token$/
		);
		await modal.getByRole('button', { name: '링크 공유 해제', exact: true }).click();
		await expect(modal.getByRole('status')).toContainText('모두 해제');
		await modal.getByRole('button', { name: '파일 관리 닫기' }).click();
		await page.getByRole('button', { name: '미리보기 닫기' }).click();
		await page.getByRole('button', { name: /^생명과학/ }).click();
		await expect(page.getByRole('button', { name: /새 실험 노트.txt/ })).toBeVisible();
		await page.getByRole('button', { name: /새 실험 노트.txt/ }).click();
		await expect(page.getByRole('textbox', { name: '새 실험 노트.txt 편집' })).toBeVisible();
		expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
			true
		);
		await page.screenshot({
			path: `/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-drive-patched-${width}.png`,
			fullPage: true
		});
	});
	test(`board readable preview and navigation at ${width}px`, async ({ page }) => {
		await page.setViewportSize({ width, height: 960 });
		await setup(page);
		await page.goto('/personal-project/calendar/boards?board=1');
		await expect(
			page
				.getByRole('navigation', { name: '게시판 선택' })
				.getByRole('link', { name: '자료공유', exact: true })
		).toHaveAttribute('href', '?board=1');
		await expect(page.getByText('분자생물학 기말 정리 자료', { exact: true })).toBeVisible();
		await expect(
			page.getByText(
				'이번 학기 시험 범위에 맞춰 정리했어요. 빠진 내용이 있으면 댓글로 알려주세요.',
				{ exact: true }
			)
		).toBeVisible();
		await expect(page.getByLabel('댓글 8개', { exact: true })).toBeVisible();
		expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
			true
		);
		await page.screenshot({
			path: `/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-board-patched-${width}.png`,
			fullPage: true
		});
	});
	test(`multidate, recurrence and undated task input at ${width}px`, async ({ page }) => {
		await page.setViewportSize({ width, height: 960 });
		const state = await setup(page);
		await page.goto('/personal-project/calendar');
		await page.getByRole('button', { name: '여러 날짜 선택', exact: true }).click();
		await page.getByRole('button', { name: '2026-11-18 선택', exact: true }).click();
		await page.getByRole('button', { name: '2026-11-21 선택', exact: true }).click();
		await page.getByRole('button', { name: '선택한 날짜에 일정 만들기', exact: true }).click();
		let modal = page.getByRole('dialog');
		await modal.getByLabel('제목', { exact: true }).fill('날짜 여러 개');
		await modal.getByRole('button', { name: '시간 미정', exact: true }).click();
		await modal.getByRole('button', { name: '저장', exact: true }).click();
		await expect(modal).toBeHidden();
		const batch = state.writes.find((w) => w.path.endsWith('/series'));
		expect(batch.body.selected_dates).toEqual(['2026-11-18', '2026-11-21']);
		expect(batch.body.time_unspecified).toBe(true);
		await page.getByRole('button', { name: '일정 만들기', exact: true }).click();
		modal = page.getByRole('dialog');
		await modal.getByLabel('제목', { exact: true }).fill('월간 반복 업무');
		await modal.getByRole('combobox', { name: '반복', exact: true }).selectOption('month');
		await modal.getByRole('spinbutton', { name: /간격/ }).fill('2');
		await modal.getByRole('spinbutton', { name: '반복 횟수', exact: true }).fill('4');
		await expect(modal.getByRole('heading')).toBeInViewport();
		await expect(modal.getByRole('button', { name: '저장', exact: true })).toBeInViewport();
		await page.screenshot({
			path: `/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-event-patched-${width}.png`,
			fullPage: true
		});
		await modal.getByRole('button', { name: '저장', exact: true }).click();
		await expect(modal).toBeHidden();
		const repeats = state.writes.filter((w) => w.path.endsWith('/series'));
		expect(repeats[1].body).toMatchObject({
			repeat_unit: 'month',
			repeat_interval: 2,
			repeat_count: 4
		});
		await page.getByRole('button', { name: '일정 만들기', exact: true }).click();
		modal = page.getByRole('dialog');
		await modal.getByRole('button', { name: '할 일', exact: true }).click();
		await expect(modal.getByRole('checkbox', { name: '날짜 미정', exact: true })).toBeChecked();
		await modal.getByLabel('제목', { exact: true }).fill('날짜 없이 생각 정리');
		await modal.getByRole('button', { name: '저장', exact: true }).click();
		await expect(modal).toBeHidden();
		expect(
			state.writes.find((w) => w.path.endsWith('/calendar/events') && w.method === 'POST').body
		).toMatchObject({ task_unplanned: true, end_time: null, status: 'todo' });
	});
}
test('week grid uses event duration and shows start and end times', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	const state=await setup(page);
	await page.goto('/personal-project/calendar/week');
	const one = page.locator('.cw-timed').filter({ hasText: '1시간 일정' }),
		two = page.locator('.cw-timed').filter({ hasText: '2시간 일정' });
	await expect(one).toBeVisible();
	await expect(two).toContainText('11:00–13:00');
	const first = await one.boundingBox(),
		second = await two.boundingBox();
	expect(second!.height / first!.height).toBeCloseTo(2, 1);
	await page.screenshot({
		path: '/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-week-patched.png',
		fullPage: true
	});
	await one.click();const editor=page.getByRole('dialog');
	await editor.getByLabel('제목',{exact:true}).fill('제목만 수정');
	await editor.getByRole('button',{name:'저장',exact:true}).click();
	await expect(editor).toBeHidden();
	const patch=state.writes.find(w=>w.path.endsWith('/10/scope'));
	expect(patch.body).not.toHaveProperty('status');
	expect(patch.body).not.toHaveProperty('task_due_at');
});

test('widget setup provides both installers and expires pairing codes',async({page})=>{
	await setup(page);
	await page.route('**/api/personal/calendar/widget/pair',r=>r.fulfill({json:{code:'isolated-five-minute-code',expiresIn:300}}));
	await page.goto('/personal-project/calendar/widgets');
	await expect(page.getByRole('link',{name:'Windows 설치 파일',exact:true})).toHaveAttribute('href','/downloads/windows-widget');
	await expect(page.getByRole('link',{name:'Android APK',exact:true})).toHaveAttribute('href','/downloads/android-widget');
	await page.getByRole('button',{name:'연결 코드 만들기',exact:true}).click();
	await expect(page.getByRole('textbox',{name:'위젯 연결 코드',exact:true})).toHaveValue('isolated-five-minute-code');
	await page.clock.runFor(301000);
	await expect(page.getByRole('button',{name:'복사',exact:true})).toBeDisabled();
	await expect(page.getByText('만료됨 · 새 코드를 만들어주세요',{exact:true})).toBeVisible();
});

test('public shared file is available without an account and a revoked link has a clear error',async({page})=>{
	await page.setViewportSize({width:390,height:844});
	await page.route('**/api/personal/drive/shared/*',r=>r.fulfill(r.request().url().endsWith('/valid-link')?{json:{name:'공유한 실험 자료.txt',byteSize:120}}:{status:404,json:{detail:'만료되었거나 해제된 공유 링크입니다.'}}));
	await page.goto('/share/valid-link');
	await expect(page.getByRole('heading',{name:'공유한 실험 자료.txt',exact:true})).toBeVisible();
	await expect(page.getByRole('link',{name:'파일 다운로드',exact:true})).toHaveAttribute('href',/\/shared\/valid-link\/content$/);
	await page.goto('/share/revoked-link');
	await expect(page.getByRole('alert')).toContainText('만료되었거나 해제된');
	expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
