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
	await page.getByRole('checkbox', { name: '스시과 세미나 완료' }).click();
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

test('일별 메모 자동 저장과 일정 필기 영역, 페이지 스크롤', async ({page}) => {
 await setup(page);
 let note:any={content:'',richDocument:'',revision:0};
 await page.route('**/api/personal/calendar/daily-notes/*',async r=>{
  if(r.request().method()==='PUT'){const body=r.request().postDataJSON();note={...body,richDocument:body.rich_document,revision:note.revision+1};}
  return r.fulfill({json:note});
 });
 await page.goto('/personal-project/calendar/day');
 const editor=page.locator('.daily-plan [contenteditable=true]');
 await expect(editor).toBeVisible();await editor.fill('오늘 연구 메모');await page.clock.runFor(2500);
 await expect.poll(()=>note.richDocument).toContain('오늘 연구 메모');
 await page.reload();await expect(editor).toContainText('오늘 연구 메모');
 await expect(page.getByLabel('필기 작업 공간')).toBeVisible();
 await expect(page.locator('.cw-day-grid .cw-slot')).toHaveCount(0);
 await expect(page.locator('.cw-week-scroll')).toHaveCount(0);
 await page.screenshot({path:'/private/tmp/ondo-day-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
 await page.screenshot({path:'/private/tmp/ondo-day-mobile.png',fullPage:true});
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

test('체크리스트 Enter와 공통 필기 도구',async({page})=>{
 await setup(page);
 await page.goto('/personal-project/calendar/day');
 const editor=page.locator('.daily-plan [contenteditable=true]');
 await editor.fill('준비');await page.getByRole('button',{name:'체크리스트',exact:true}).click();
 await editor.press('End');await editor.press('Enter');
 await expect(editor.getByRole('checkbox')).toHaveCount(2);
 await editor.press('Enter');await expect(editor.getByRole('checkbox')).toHaveCount(1);
 await page.getByLabel('PDF 도구').selectOption('erase');
 await expect(page.getByLabel('지우개 방식')).toBeVisible();
 await page.getByLabel('PDF 도구').selectOption('lasso');
 await expect(page.getByLabel('PDF 도구')).toHaveValue('lasso');
});

test('학교 설정 저장과 학생서비스 바로가기', async ({page}) => {
 await setup(page);
 let profile={is_student:false,school:'',department:''};
 await page.route('**/api/personal/student/profile',async r=>{
  if(r.request().method()==='PUT')profile=r.request().postDataJSON();
  return r.fulfill({json:profile});
 });
 await page.goto('/personal-project/calendar/student');
 await page.getByLabel('학생서비스 사용',{exact:true}).check();
 await page.getByRole('combobox',{name:'학교',exact:true}).selectOption('__other');
 await page.getByLabel('학교 이름',{exact:true}).fill('다른 대학교');
 await page.getByRole('combobox',{name:'학과·전공',exact:true}).fill('수학과');
 await page.getByRole('button',{name:'설정 저장',exact:true}).click();
 await expect(page.getByRole('status').filter({hasText:'학교 설정을 저장했습니다.'})).toBeVisible();
 await page.reload();await expect(page.getByLabel('학교 이름',{exact:true})).toHaveValue('다른 대학교');
 await expect(page.locator('.destinations a').filter({hasText:'시간표'})).toHaveAttribute('href','/personal-project/calendar/student/timetable');
});

test('APK 다운로드 응답은 설치 파일 이름과 타입을 유지한다',async({request})=>{
 const response=await request.get('/downloads/android-widget');
 expect(response.status()).toBe(200);expect(response.headers()['content-type']).toBe('application/vnd.android.package-archive');
 expect(response.headers()['content-disposition']).toContain('filename="ondo-widget.apk"');
 expect((await response.body()).subarray(0,2).toString()).toBe('PK');
});

test('기존 학과 게시판 주소는 일반 게시판으로 이동한다',async({page})=>{
 await setup(page);
 await page.route('**/api/personal/boards',r=>r.fulfill({json:{boards:[],canCreate:false}}));
 await page.goto('/personal-project/calendar/student/board');
 await expect(page).toHaveURL(/calendar\/boards$/);
 await expect(page.getByRole('heading',{name:'게시판',exact:true})).toBeVisible();
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

test('빠른 할 일 입력, 날짜 필터, 완료 취소와 저장 실패 복구', async ({ page }) => {
 await setup(page);
 await page.goto('/personal-project/calendar');
 await page.getByRole('button', {name:'할 일',exact:true}).click();
 await page.getByLabel('새 할 일', {exact:true}).fill('도서관 책 반납');
 await page.getByLabel('할 일 날짜', {exact:true}).fill('2026-09-18');
 await page.getByLabel('새 할 일', {exact:true}).press('Enter');
 await expect(page.locator('.cw-task').filter({hasText:'도서관 책 반납'})).toBeVisible();
 await page.getByRole('button',{name:'오늘',exact:true}).last().click();
 await expect(page.locator('.cw-task').filter({hasText:'도서관 책 반납'})).toHaveCount(0);
 await page.getByRole('button',{name:'예정',exact:true}).click();
 await page.getByRole('checkbox',{name:'도서관 책 반납 완료'}).click();
 await page.getByRole('button',{name:'완료 취소',exact:true}).click();
 await expect(page.getByRole('checkbox',{name:'도서관 책 반납 완료'})).not.toBeChecked();
 await page.route('**/calendar/events/*', async route => {
   if(route.request().method()==='PATCH') await route.fulfill({status:503,json:{detail:'저장 연결을 확인해주세요'}});
   else await route.fallback();
 });
 await page.getByRole('checkbox',{name:'도서관 책 반납 완료'}).click();
 await expect(page.getByText('저장 연결을 확인해주세요')).toBeVisible();
 await expect(page.getByRole('checkbox',{name:'도서관 책 반납 완료'})).not.toBeChecked();
 await page.getByRole('button',{name:'전체',exact:true}).click();
 await page.screenshot({path:'/private/tmp/todos-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'/private/tmp/todos-mobile.png',fullPage:true});
 await expect(page.locator('body')).toHaveJSProperty('scrollWidth',390);
});

test('weekly starts at 08 with overnight events and hides classes in month',async({page})=>{
 await setup(page);
 const sample={id:77,title:'수업 테스트',description:'',startTime:'2026-09-16T09:00:00+09:00',endTime:'2026-09-16T10:00:00+09:00',isAllDay:false,status:'passive',type:'personal',hideInMonth:true};
 await page.route('**/api/personal/calendar/events?**',r=>r.fulfill({json:[sample,{...sample,id:78,title:'새벽 테스트',startTime:'2026-09-16T00:30:00+09:00',endTime:'2026-09-16T01:30:00+09:00',hideInMonth:false}]}));
 await page.goto('/personal-project/calendar/week?date=2026-09-16');
 await expect(page.getByRole('grid',{name:'08시부터 익일 02시까지 일정 시간표'})).toBeVisible();
 await expect(page.locator('.cw-timed').filter({hasText:'새벽 테스트'})).toBeVisible();
 expect(await page.locator('.cw-week-scroll').evaluate(e=>e.scrollTop)).toBe(0);
 await page.locator('.cw-week-scroll').evaluate(e=>e.scrollTop=600);
 await page.getByRole('button',{name:'오늘',exact:true}).click();
 await expect.poll(()=>page.locator('.cw-week-scroll').evaluate(e=>e.scrollTop)).toBe(0);
 await page.goto('/personal-project/calendar?date=2026-09-16');
 await expect(page.locator('.cw-month')).not.toContainText('수업 테스트');
 await expect(page.getByRole('button',{name:'Zoom 예약',exact:true})).toHaveCount(0);
});

test('Google login and signup entry points use login-only OAuth',async({page})=>{
 await page.goto('/login');
 await expect(page.getByRole('link',{name:'Google로 로그인',exact:true})).toHaveAttribute('href',/purpose=login/);
 await page.goto('/register');
 await expect(page.getByRole('link',{name:'Google로 가입 \/ 로그인',exact:true})).toHaveAttribute('href',/purpose=login/);
});
