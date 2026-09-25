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

test('일별 메모 저장, 체크박스, 익일 시간과 고정 종일 영역', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	const events = await setup(page);
	events.push({
		...events[0],
		id: 30,
		title: '종일 준비',
		isAllDay: true,
		startTime: '2026-09-16T00:00:00+09:00',
		endTime: '2026-09-17T00:00:00+09:00',
		categoryName: '업무 > 기획, 개인'
	});
	events.push({
		...events[0],
		id: 31,
		title: '다음 주 준비',
		startTime: '2026-09-30T09:00:00+09:00',
		endTime: '2026-09-30T10:00:00+09:00'
	});
	const notes: Record<string, string> = {};
	await page.route('**/api/personal/calendar/daily-notes/*', async (r) => {
		const path = new URL(r.request().url()).pathname;
		if (r.request().method() === 'PUT') notes[path] = r.request().postDataJSON().content;
		return r.fulfill({ json: { content: notes[path] || '' } });
	});
	await page.goto('/personal-project/calendar/day');
	await expect(page.getByLabel('메모와 체크리스트')).toBeEnabled();
	await page.getByLabel('메모와 체크리스트').fill('# 연구 프로젝트\n- [ ] 자료 정리');
	await page.getByRole('button', { name: '미리보기', exact: true }).click();
	await page.getByRole('checkbox', { name: '자료 정리', exact: true }).check();
	await page.getByRole('button', { name: '메모 저장', exact: true }).click();
	await expect(page.getByText('저장됨', { exact: true })).toBeVisible();
	await page.reload();
	await page.getByRole('button', { name: '미리보기', exact: true }).click();
	await expect(page.getByRole('checkbox', { name: '자료 정리', exact: true })).toBeChecked();
	await expect(page.locator('.cw-day-grid .cw-slot')).toHaveCount(36);
	await expect(page.locator('.daily-plan details').filter({ hasText: '그 이후의 할 일' })).not.toHaveAttribute('open', '');
	await page.locator('.daily-plan details').filter({ hasText: '그 이후의 할 일' }).locator('summary').click();
	await expect(
		page.locator('.daily-plan').getByText('다음 주 준비', { exact: true })
	).toBeVisible();
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.screenshot({ path: '/private/tmp/ondo-day-desktop.png', fullPage: true });
	await page.locator('.cw-week-scroll').evaluate((el) => (el.scrollTop = 600));
	const heading = await page.locator('.cw-week-heading').boundingBox();
	const allDay = await page.locator('.cw-all-day').boundingBox();
	expect(allDay!.y).toBeGreaterThanOrEqual(heading!.y + heading!.height - 1);
	expect(allDay!.y).toBeLessThan(heading!.y + heading!.height + 2);
	await page.getByRole('button', { name: '2026-09-16 25시 30분 일정 추가', exact: true }).click();
	await expect(page.getByRole('dialog').getByLabel('시작', { exact: true })).toHaveValue(
		'2026-09-17T01:30'
	);
	await page.getByRole('dialog').getByRole('button', { name: '닫기', exact: true }).last().click();
	await page.setViewportSize({ width: 390, height: 844 });
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
	await page.screenshot({ path: '/private/tmp/ondo-day-mobile.png', fullPage: true });
});

test('아우라 전용 일정에서 수정과 학생 리포트로 연결하고 제출만 완료 처리한다', async ({
	page
}) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	await setup(page);
	const school = {
		id: 1,
		name: '검증고',
		schoolName: '검증고',
		admissionYear: 2026,
		roundCount: 1,
		currentStage: 'accepted',
		isActive: true
	};
	const round = {
		id: 1,
		eventId: 2,
		schoolId: 1,
		schoolName: '검증고',
		roundNumber: 1,
		roundNumbers: [1],
		roundLabel: '1회차',
		progressStage: 'accepted',
		description: '',
		startTime: '2026-09-16T16:00:00+09:00',
		endTime: '2026-09-16T17:00:00+09:00',
		attendanceStatus: 'scheduled',
		amount: 30000,
		targets: [{ id: 42, studentName: '지후', report: { id: 1, status: 'ready' } }]
	};
	await page.route('**/api/personal/aura/schools', (r) => r.fulfill({ json: [school] }));
	await page.route('**/api/personal/aura/rounds?*', (r) => r.fulfill({ json: [round] }));
	await page.goto('/personal-project/aura');
	await expect(page.locator('.slot.busy').first()).toBeVisible();
	await expect(page.locator('.slot.reportDone')).toHaveCount(0);
	await page.locator('.slot.busy').first().click();
	await expect(page.getByRole('heading', { name: '클리닉 일정 수정' })).toBeVisible();
	await expect(page.locator('.quick-report-student a').first()).toHaveAttribute(
		'href',
		'/personal-project/aura/reports/42'
	);
	await page.screenshot({ path: '/private/tmp/aura-clinic-edit.png', fullPage: true });
});

test('쉼표 카테고리와 상위 카테고리 필터', async ({ page }) => {
	const events = await setup(page);
	events[0].categoryName = '업무 > 기획, 개인 > 공부';
	await page.goto('/personal-project/calendar');
	await page.getByRole('button', { name: '표시할 캘린더', exact: true }).click();
	await page.getByLabel('업무', { exact: true }).uncheck();
	await expect(page.locator('.cw-event').filter({ hasText: '스시과 세미나' })).toHaveCount(1);
	await page.getByLabel('개인', { exact: true }).uncheck();
	await expect(page.locator('.cw-event').filter({ hasText: '스시과 세미나' })).toHaveCount(0);
});

test('사이드바 접기 상태 유지와 모바일 메뉴 접근', async ({ page }) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	await setup(page);
	await page.goto('/personal-project/calendar');
	const main = page.locator('.ondo-main');
	const wide = (await main.boundingBox())!.width;
	const assertNoOverlap = async () => {
		const sidebar = (await page.locator('.ondo-sidebar').boundingBox())!;
		const calendar = (await page.locator('.cw').boundingBox())!;
		expect(calendar.x).toBeGreaterThanOrEqual(sidebar.x + sidebar.width);
	};
	await assertNoOverlap();
	await page.getByRole('button', { name: '사이드바 접기', exact: true }).click();
	await expect(page.locator('.ondo-shell')).toHaveClass(/rail/);
	await expect(page.getByRole('button', { name: '사이드바 펼치기', exact: true })).toHaveAttribute(
		'aria-expanded',
		'false'
	);
	await expect.poll(async () => (await main.boundingBox())!.width).toBeGreaterThan(wide + 100);
	await assertNoOverlap();
	await page.reload();
	await expect(page.getByRole('button', { name: '사이드바 펼치기', exact: true })).toBeVisible();
	await page
		.getByRole('navigation', { name: '캘린더', exact: true })
		.getByRole('link', { name: '주간 시간표', exact: true })
		.click();
	await expect(page.locator('.cw-week')).toBeVisible();
	await expect(page.getByRole('button', { name: '사이드바 펼치기', exact: true })).toBeVisible();
	await page.evaluate(() => window.scrollTo(0, 0));
	await page.screenshot({ path: '/private/tmp/ondo-redesign-rail.png', fullPage: true });
	await page.getByRole('button', { name: '사이드바 펼치기', exact: true }).click();
	await expect(page.getByRole('button', { name: '사이드바 접기', exact: true })).toBeVisible();
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.getByRole('navigation', { name: '캘린더', exact: true })).not.toBeVisible();
	await page.getByRole('button', { name: '사이드바 펼치기', exact: true }).click();
	await expect(page.getByRole('navigation', { name: '캘린더', exact: true })).toBeVisible();
	await page.screenshot({ path: '/private/tmp/ondo-redesign-mobile-menu.png', fullPage: true });
	await page
		.getByRole('navigation', { name: '캘린더', exact: true })
		.getByRole('link', { name: '월간 캘린더', exact: true })
		.click();
	await expect(page.getByRole('navigation', { name: '캘린더', exact: true })).not.toBeVisible();
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('체크리스트 줄바꿈·서식 편집기·아우라 분리', async ({page}) => {
 const events=await setup(page);
 events.push({...events[1],id:90,status:'todo',completionSource:'external',title:'분리된 클리닉'});
 let note:any={content:'',drawing:'',richDocument:''};
 await page.route('**/api/personal/calendar/daily-notes/*', async r=>{
  if(r.request().method()==='PUT'){const body=r.request().postDataJSON();note={...body,richDocument:body.rich_document};}
  return r.fulfill({json:note});
 });
 await page.goto('/personal-project/calendar/day');
 const editor=page.getByLabel('메모와 체크리스트');
 await editor.fill('- [ ] 준비');await editor.press('End');await editor.press('Enter');
 await expect(editor).toHaveValue('- [ ] 준비\n- [ ] ');
 await editor.press('Enter');await expect(editor).toHaveValue('- [ ] 준비\n\n');
 await expect(page.locator('.daily-plan').getByText('분리된 클리닉',{exact:true})).not.toBeVisible();
 await page.locator('.daily-plan details').filter({hasText:'아우라 ·'}).locator('summary').click();
 await expect(page.locator('.daily-plan').getByText('분리된 클리닉',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'서식 편집기 사용',exact:true}).click();
 await expect(page.getByRole('textbox',{name:'문서 내용'})).toBeVisible();
 await page.getByRole('button',{name:'메모 저장',exact:true}).click();
 await expect(page.getByText('저장됨',{exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('textbox',{name:'문서 내용'})).toBeVisible();
 await expect(page.getByText('저장됨',{exact:true})).toBeVisible();
 await page.getByText('펜 도구',{exact:true}).click();
 await page.getByRole('button',{name:'지우개',exact:true}).click();
 await expect(page.getByRole('button',{name:'지우개',exact:true})).toHaveAttribute('aria-pressed','true');
 const canvas=page.getByLabel('펜으로 작성하는 메모');
 await page.getByRole('button',{name:'펜',exact:true}).click();
 await canvas.scrollIntoViewIfNeeded();const box=(await canvas.boundingBox())!;
 const stroke=async()=>{await page.mouse.move(box.x+40,box.y+50);await page.mouse.down();await page.mouse.move(box.x+120,box.y+50,{steps:12});await page.mouse.up();};
 await stroke();
 const pixels=()=>canvas.evaluate((node:HTMLCanvasElement)=>{const data=node.getContext('2d')!.getImageData(0,0,node.width,node.height).data;return data.filter((v,i)=>i%4===3&&v>0).length;});
 const before=await pixels();expect(before).toBeGreaterThan(0);
 await page.getByRole('button',{name:'지우개',exact:true}).click();await stroke();expect(await pixels()).toBeLessThan(before);
 await page.getByRole('button',{name:'메모 저장',exact:true}).click();

 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'/private/tmp/ondo-checklist-mobile.png',fullPage:true});
});

test('학생 설정·학기 미리보기·수정 후 재확인', async ({page}) => {
 await setup(page);
 let profile={is_student:false,school:'',department:''};
 await page.route('**/api/personal/student/**',async r=>{
  const path=new URL(r.request().url()).pathname;
  if(path.endsWith('/profile')){if(r.request().method()==='PUT')profile=r.request().postDataJSON();return r.fulfill({json:profile});}
  if(path.endsWith('/preview'))return r.fulfill({json:{events:[{title:'수학',startTime:'2026-09-21T09:00:00+09:00',endTime:'2026-09-21T10:30:00+09:00',location:'공학관'}],skipped:[]}});
  return r.fulfill({json:{created:1,alreadyImported:false}});
 });
 await page.goto('/personal-project/calendar/student');
 await page.getByLabel('학생인가요?').check();await page.getByLabel('학교',{exact:true}).fill('다른 대학교');
 await page.getByRole('button',{name:'설정 저장',exact:true}).click();
 await page.getByLabel('과목명',{exact:true}).fill('수학');await page.getByRole('button',{name:'학기 일정 미리보기',exact:true}).click();
 const add=page.getByRole('button',{name:'내 캘린더에 시간표 추가',exact:true});
 await expect(add).toBeEnabled();await page.getByLabel('종강일').fill('2026-12-15');await expect(add).toBeDisabled();
 await page.getByRole('button',{name:'학기 일정 미리보기',exact:true}).click();await add.click();
 await expect(page.getByRole('status')).toHaveText('1개 수업을 캘린더에 등록했습니다.');
 await page.screenshot({path:'/private/tmp/ondo-student-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/private/tmp/ondo-student-mobile.png',fullPage:true});
});

test('APK 다운로드 응답은 설치 파일 이름과 타입을 유지한다',async({request})=>{
 const response=await request.get('/downloads/android-widget');
 expect(response.status()).toBe(200);expect(response.headers()['content-type']).toBe('application/vnd.android.package-archive');
 expect(response.headers()['content-disposition']).toContain('filename="ondo-widget.apk"');
 expect((await response.body()).subarray(0,2).toString()).toBe('PK');
});

test('학과 위키와 게시판을 학교 프로필에 연결한다',async({page})=>{
 await setup(page);
 const versions:any[]=[];const posts:any[]=[];
 await page.route('**/api/personal/student/**',async r=>{
  const path=new URL(r.request().url()).pathname;
  if(path.endsWith('/profile'))return r.fulfill({json:{is_student:true,school:'서울대학교',department:'컴퓨터공학부'}});
  if(path.endsWith('/curriculum')){if(r.request().method()==='POST'){const b=r.request().postDataJSON();versions.push({...b,revision:1,created_at:'2026-09-23'});}return r.fulfill({json:{versions,canPublishOfficial:false}});}
  if(path.endsWith('/board')){if(r.request().method()==='POST'){const b=r.request().postDataJSON();posts.push({...b,id:1,start_time:b.start,end_time:b.end,canDelete:true});}return r.fulfill({json:posts});}
  return r.fulfill({json:{eventId:77,alreadyAdded:false}});
 });
 await page.goto('/personal-project/calendar/student');
 await page.getByRole('button',{name:'학과 자료 불러오기',exact:true}).click();
 await expect(page.getByText('검토된 규정을 아직 제공하지 않습니다.',{exact:true})).toBeVisible();
 await page.getByText('규정 편집',{exact:true}).click();
 await page.getByLabel('규정 내용').fill('사용자 검토가 필요한 전공 이수규정');
 await page.getByRole('button',{name:'새 버전 저장',exact:true}).click();
 await expect(page.getByText('새 버전으로 저장했습니다.',{exact:true})).toBeVisible();
 await page.getByLabel('글 제목').fill('학과 세미나');await page.getByLabel('일정 시작 (선택)').fill('2026-09-25T10:00');
 await page.getByRole('button',{name:'학과 게시판에 등록',exact:true}).click();await page.getByRole('button',{name:'내 캘린더에 추가',exact:true}).click();
 await expect(page.getByText('내 캘린더에 추가했습니다.',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/private/tmp/ondo-community-mobile.png',fullPage:true});
});

test('Google 가져오기와 미리보기 후 내보내기를 분리한다', async ({ page }) => {
  await setup(page);
  const transfers: any[] = [];
  await page.route('**/api/personal/google/**', async r => {
    const path = new URL(r.request().url()).pathname;
    if(path.endsWith('/accounts')) return r.fulfill({json:[{id:1,email:'calendar@example.com',last_sync:null,error:null}]});
    if(path.endsWith('/calendars')) return r.fulfill({json:[{calendar_id:'my-google',name:'개인 캘린더',writable:1,enabled:1}]});
    if(path.endsWith('/transfer')) {
      const body = r.request().postDataJSON(); transfers.push(body);
      return r.fulfill({json:body.preview_token ? {exported:2} : {preview_token:'a'.repeat(64),calendar_name:'개인 캘린더',create:1,update:1,unchanged:0,items:[{event_id:1,title:'회의',action:'create'},{event_id:2,title:'운동',action:'update'}]}});
    }
    return r.fulfill({json:[]});
  });
  await page.goto('/personal-project/calendar/projects');
  await page.getByRole('button',{name:'캘린더 선택',exact:true}).click();
  await page.getByText('내 캘린더 → Google 내보내기',{exact:true}).click();
  await page.getByLabel('대상 Google 캘린더').selectOption('my-google');
  await page.getByRole('button',{name:'내보내기 미리보기'}).click();
  await expect(page.getByText('개인 캘린더: 추가 1건 · 덮어쓰기 1건 · 동일 0건')).toBeVisible();
  expect(transfers).toHaveLength(1); expect(transfers[0].preview_token).toBeUndefined();
  await page.screenshot({path:'/private/tmp/ondo-google-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:'/private/tmp/ondo-google-mobile.png',fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.getByRole('button',{name:'확인한 내용으로 Google에 반영'}).click();
  await expect(page.getByRole('status').filter({hasText:'2건을 Google에 반영했습니다.'})).toBeVisible();
  expect(transfers[1].preview_token).toBe('a'.repeat(64));
  await page.getByRole('button',{name:'내보내기 미리보기'}).click();
  await page.getByLabel('종료일',{exact:true}).fill('2026-10-31');
  await expect(page.getByRole('button',{name:'확인한 내용으로 Google에 반영'})).toHaveCount(0);
});
