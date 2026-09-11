import { expect, test, type Page } from '@playwright/test';

const presentationTemplate = {
	type: 'presentation',
	environment: {
		title: '브라우저 검증 발표',
		purpose: '프로젝트 목적',
		language: '한국어',
		place: '강의실',
		duration_minutes: 2,
		question_count: 2
	},
	files: { slide: null, paper: null, script: null, script_content: '' },
	audience: {
		audience_type: '대학생',
		audience_count: 6,
		expertise_level: '중간',
		interest_level: '중간'
	}
};

const odiUser = {
	user_id: '7',
	auth_id: '7',
	recent_template: presentationTemplate,
	config: {},
	created_at: '2026-08-15T00:00:00Z',
	updated_at: '2026-08-15T00:00:00Z'
};

function reportSession(sessionId: string, title = '연속 테스트 발표') {
	return {
		session_id: sessionId,
		user_id: '7',
		template_id: 'template-test',
		template: {
			...presentationTemplate,
			environment: { ...presentationTemplate.environment, title }
		},
		feedback: {
			score: { overall_score: 86, percentile: 12 },
			duration: { planned_seconds: 120, actual_seconds: 116, qa_seconds: 20 },
			score_card: {
				scores: { engagement: 88, clarity: 84, credibility: 86 },
				average_scores: { engagement: 74, clarity: 72, credibility: 73 },
				descriptions: {
					engagement: '도입에서 청중의 관심을 안정적으로 이끌었습니다.',
					clarity: '핵심 메시지를 순서대로 설명했습니다.',
					credibility: '자료와 사례를 근거로 활용했습니다.'
				}
			},
			detail_analysis: {
				highlight_metrics: [
					{ name: '시선 처리', score: 91 },
					{ name: '핵심 메시지', score: 88 }
				],
				content_analysis: { organization: 86, central_message: 88 },
				delivery_analysis: { language_clarity: 85, gaze_delivery: 91 }
			},
			timeline: [
				{
					time_sec: 34,
					end_sec: 44,
					title: '입력 신호를 구분해 보세요',
					description: '역할을 한 문장씩 나누면 더 선명해집니다.',
					type: 'warning'
				},
				{
					time_sec: 78,
					end_sec: 88,
					title: '전환 구간은 천천히',
					description: '다음 단계 전 짧게 호흡을 두세요.',
					type: 'negative'
				}
			],
			audience_analysis: {
				graph: [
					{ time_sec: 0, E: 0.6, V: 0.5, C: 0.6 },
					{ time_sec: 116, E: 0.8, V: 0.75, C: 0.82 }
				],
				events: [{ time_sec: 34, label: '입력 신호 설명', type: 'warning' }]
			},
			ai_insight: {
				title: '핵심 메시지를 먼저 제시한 흐름이 좋았어요.',
				description: '단계 전환마다 짧게 호흡을 두면 전달력이 더 좋아집니다.'
			}
		},
		state: 'completed',
		started_at: '2026-08-25T00:00:00Z',
		ended_at: '2026-08-25T00:03:00Z',
		created_at: '2026-08-25T00:00:00Z',
		updated_at: '2026-08-25T00:03:00Z'
	};
}

async function mockSessionApi(page: Page, email = 'xrealrehear@gmail.com', user = odiUser) {
	await page.route('**/auth/isjwt?key=mainauth', (route) =>
		route.fulfill({
			json: { sub: '7', data: { id: '7', name: '테스트', email }, exp: 9999999999 }
		})
	);
	await page.route('**/odi/db/login', (route) => route.fulfill({ json: { user } }));
	await page.route('**/odi/db/users/7/recent-template', (route) =>
		route.fulfill({
			json: { user: { ...user, recent_template: presentationTemplate } }
		})
	);
	await page.route('**/odi/db/pre-sessions/start-from-recent', (route) =>
		route.fulfill({
			json: {
				pin_code: '9876',
				pre_session: {
					pin_code: '9876',
					template_id: 'template-test',
					session_id: null,
					state: 'waiting',
					expires_at: '2026-08-15T10:00:00Z',
					created_at: '2026-08-15T09:00:00Z'
				},
				// 일반 세션의 화면 전환/PIN 표시를 Firebase 네트워크와 독립적으로 검증한다.
				template: null,
				file_bundle: null
			}
		})
	);
	await page.route('**/odi/db/pre-sessions/9876/finish', (route) =>
		route.fulfill({
			json: {
				pre_session: {
					pin_code: '9876',
					template_id: 'template-test',
					session_id: 'session-test',
					state: 'finished',
					expires_at: '2026-08-15T10:00:00Z',
					created_at: '2026-08-15T09:00:00Z'
				},
				session: { session_id: 'session-test', feedback: {}, state: 'completed' }
			}
		})
	);
	await page.route('**/odi/db/pre-sessions/9876', (route) =>
		route.fulfill({
			json: {
				pre_session: {
					pin_code: '9876',
					template_id: 'template-test',
					session_id: null,
					state: 'waiting',
					expires_at: '2026-08-15T10:00:00Z',
					created_at: '2026-08-15T09:00:00Z'
				}
			}
		})
	);
}

async function openSessionFromConfirm(page: Page) {
	const browserErrors: string[] = [];
	page.on('pageerror', (error) => browserErrors.push(error.message));
	await page.goto('/odi/session/presentation/confirm');
	// Store가 비어 있는 새 세션에서는 서버의 recent_template를 잠깐이라도 보여주지 않는다.
	await expect(page.getByText('발표 제목 없음', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: '시작하기' }).click();
	return browserErrors;
}

test('연습 계정은 Confirm의 시작하기에서 체험/일반 선택창을 연다', async ({ page }) => {
	await mockSessionApi(page);
	const browserErrors = await openSessionFromConfirm(page);

	const dialog = page.getByRole('dialog', { name: '진행할 세션을 선택해 주세요' });
	await page.waitForTimeout(300);
	if ((await dialog.count()) === 0) {
		const alerts = await page.locator('[role="alert"]').allTextContents();
		throw new Error(
			`Confirm 선택창 미표시: url=${page.url()}, alerts=${JSON.stringify(alerts)}, browserErrors=${JSON.stringify(browserErrors)}`
		);
	}
	await expect(dialog).toBeVisible();
	const experienceCard = dialog.getByRole('button', { name: /체험 세션/ });
	const regularCard = dialog.getByRole('button', { name: /^일반 세션/ });
	const submitButton = dialog.getByRole('button', { name: '선택한 세션으로 시작하기' });
	await expect(experienceCard).toBeVisible();
	await expect(regularCard).toBeVisible();

	const [dialogBox, experienceBox, regularBox, submitBox] = await Promise.all([
		dialog.boundingBox(),
		experienceCard.boundingBox(),
		regularCard.boundingBox(),
		submitButton.boundingBox()
	]);
	expect(dialogBox).not.toBeNull();
	expect(experienceBox).not.toBeNull();
	expect(regularBox).not.toBeNull();
	expect(submitBox).not.toBeNull();
	expect(experienceBox!.y + experienceBox!.height).toBeLessThan(submitBox!.y);
	expect(regularBox!.y + regularBox!.height).toBeLessThan(submitBox!.y);
	expect(Math.abs(experienceBox!.height - regularBox!.height)).toBeLessThanOrEqual(1);
	expect(dialogBox!.y).toBeGreaterThanOrEqual(0);
	expect(dialogBox!.y + dialogBox!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
	await expect(page).toHaveURL(/\/odi\/session\/presentation\/confirm$/);
});

test('체험 세션은 선택 후 1234 PIN을 표시한다', async ({ page }) => {
	await mockSessionApi(page);
	await openSessionFromConfirm(page);
	await page.getByRole('button', { name: /체험 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=experience$/);
	await expect(page.getByText('1234', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toBeVisible();
});

test('일반 세션은 선택 후 백엔드가 생성한 PIN을 표시한다', async ({ page }) => {
	await mockSessionApi(page);
	await openSessionFromConfirm(page);
	await page.getByRole('button', { name: /^일반 세션/ }).click();
	await page.getByRole('button', { name: '선택한 세션으로 시작하기' }).click();

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=regular$/);
	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByText('체험 세션', { exact: true })).toHaveCount(0);
});

test('Wait VR을 새로 열어 store가 비어 있어도 일반 세션 설정을 서버에서 복구한다', async ({
	page
}) => {
	await mockSessionApi(page);
	await page.goto('/odi/waitvr?mode=regular');

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
});

test('일반 계정은 선택창 없이 바로 일반 세션으로 이동한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await openSessionFromConfirm(page);

	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=regular$/);
	await expect(page.getByRole('dialog', { name: '진행할 세션을 선택해 주세요' })).toHaveCount(0);
	await expect(page.getByText('9876', { exact: true })).toBeVisible();
});

test('일반 계정이 체험 URL로 직접 들어와도 일반 세션으로 시작한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.goto('/odi/waitvr?mode=experience');

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByText('1234', { exact: true })).toHaveCount(0);
});

test('세션 상태 조회가 실패하면 오류와 재시도 버튼을 표시한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.route('**/odi/db/pre-sessions/9876', (route) =>
		route.fulfill({ status: 503, json: { detail: '세션 상태를 확인하지 못했습니다.' } })
	);

	await page.goto('/odi/waitvr?mode=regular');

	await expect(page.getByText('9876', { exact: true })).toBeVisible();
	await expect(page.getByRole('alert').getByText('세션 상태를 확인하지 못했습니다.')).toBeVisible();
	await expect(page.getByRole('button', { name: '상태 다시 확인' })).toBeVisible();
});

test('분석값이 비어 있는 리포트는 0점 대신 준비 상태를 표시한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.route('**/odi/db/sessions/session-empty', (route) =>
		route.fulfill({
			json: {
				session: {
					session_id: 'session-empty',
					user_id: '7',
					template_id: 'template-test',
					template: presentationTemplate,
					feedback: {},
					state: 'completed',
					started_at: null,
					ended_at: null,
					created_at: '2026-08-25T00:00:00Z',
					updated_at: '2026-08-25T00:00:00Z'
				}
			}
		})
	);

	await page.goto('/odi/report/session-empty');

	await expect(page.getByText('비교 데이터 준비 중')).toBeVisible();
	await expect(page.getByText('상위 0%')).toHaveCount(0);
});

test('모바일 프로필 드롭다운은 본문 텍스트가 비치거나 카드 밖으로 새지 않는다', async ({
	page
}) => {
	await page.setViewportSize({ width: 280, height: 520 });
	await mockSessionApi(page);
	await page.goto('/odi/session/presentation/confirm');

	const openSidebar = page.getByRole('button', { name: '사이드바 열기' });
	await expect(openSidebar).toBeVisible();
	await openSidebar.click();
	await expect(page.locator('.sidebar')).toHaveClass(/open/);
	await page.waitForTimeout(250);

	const profileButton = page.getByRole('button', { name: /테스트 새싹 보이스/ });
	const profileBox = await profileButton.boundingBox();
	expect(profileBox).not.toBeNull();
	expect(profileBox!.x).toBeGreaterThanOrEqual(0);
	expect(profileBox!.y + profileBox!.height).toBeLessThanOrEqual(520);
	await profileButton.click({ force: true });

	const dropdown = page.locator('.profile-dropdown .dropdown');
	await expect(dropdown).toBeVisible();
	await expect(page.getByText(/지금화면순서/)).toHaveCount(0);

	const backgroundColor = await dropdown.evaluate(
		(element) => getComputedStyle(element).backgroundColor
	);
	expect(backgroundColor).toBe('rgb(96, 94, 191)');

	const box = await dropdown.boundingBox();
	expect(box).not.toBeNull();
	expect(box!.x).toBeGreaterThanOrEqual(0);
	expect(box!.x + box!.width).toBeLessThanOrEqual(280);
	expect(box!.y).toBeGreaterThanOrEqual(0);
	expect(box!.y + box!.height).toBeLessThanOrEqual(520);
});

test('새 세션 생성부터 XR 완료, 결과 조회와 재접속까지 한 흐름으로 이어진다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	let reportRequests = 0;

	await page.route('**/odi/db/pre-sessions/9876', (route) =>
		route.fulfill({
			json: {
				pre_session: {
					pin_code: '9876',
					template_id: 'template-test',
					session_id: 'session-flow',
					state: 'finished',
					report_status: 'ready',
					expires_at: '2026-08-15T10:00:00Z',
					created_at: '2026-08-15T09:00:00Z'
				}
			}
		})
	);
	await page.route('**/odi/db/sessions/session-flow', (route) => {
		reportRequests += 1;
		return route.fulfill({ json: { session: reportSession('session-flow') } });
	});

	await openSessionFromConfirm(page);
	await expect(page).toHaveURL(/\/odi\/waitvr\?mode=regular$/);
	await expect(page.getByText('9876', { exact: true })).toBeVisible();

	const reportButton = page.getByRole('button', { name: '결과 리포트 보기' });
	await expect(reportButton).toBeEnabled();
	await reportButton.click();

	await expect(page).toHaveURL(/\/odi\/report\/session-flow$/);
	await expect(page.locator('[data-report-version="v3"]')).toBeVisible();
	await expect(page.getByRole('heading', { name: '세션 점수' })).toBeVisible();
	await expect(page.getByText('86', { exact: true }).first()).toBeVisible();
	expect(reportRequests).toBe(1);

	await page.reload();
	await expect(page.getByRole('heading', { name: '세션 점수' })).toBeVisible();
	await expect(page.getByText('연속 테스트 발표')).toBeVisible();
	expect(reportRequests).toBe(2);
});

test('세션 파라미터가 바뀌면 이전 응답을 버리고 새 리포트만 표시한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.route('**/odi/db/sessions/session-old', async (route) => {
		await new Promise((resolve) => setTimeout(resolve, 500));
		await route.fulfill({ json: { session: reportSession('session-old', '이전 세션 제목') } });
	});
	await page.route('**/odi/db/sessions/session-new', (route) =>
		route.fulfill({ json: { session: reportSession('session-new', '현재 세션 제목') } })
	);

	await page.goto('/odi/report/session-old');
	await page.goto('/odi/report/session-new');

	await expect(page.getByText('현재 세션 제목')).toBeVisible();
	await page.waitForTimeout(650);
	await expect(page.getByText('이전 세션 제목')).toHaveCount(0);
});

test('리포트는 노트북 100% 배율과 모바일에서 가로로 넘치지 않는다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.route('**/odi/db/sessions/session-responsive', (route) =>
		route.fulfill({ json: { session: reportSession('session-responsive') } })
	);

	for (const viewport of [
		{ width: 1366, height: 768 },
		{ width: 390, height: 844 }
	]) {
		await page.setViewportSize(viewport);
		await page.goto('/odi/report/session-responsive');
		await expect(page.getByRole('heading', { name: '세션 점수' })).toBeVisible();
		await expect(page.getByRole('heading', { name: '몰입도' })).toBeVisible();
		await expect(page.locator('.video-pane')).toHaveCount(0);
		await expect(page.getByText('시연 영상 연결 대기 중')).toHaveCount(0);

		const hasOverflow = await page.evaluate(
			() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
		);
		expect(hasOverflow).toBe(false);
	}
});

test('영상이 연결된 개선 구간을 선택하면 현재 구간과 재생 상태를 표시한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	const sessionWithVideo = reportSession('session-video');
	(sessionWithVideo.feedback as any).media = {
		video_url: '/test-assets/demo-presentation.mp4',
		title: '테스트 발표 영상'
	};
	await page.route('**/odi/db/sessions/session-video', (route) =>
		route.fulfill({ json: { session: sessionWithVideo } })
	);
	await page.route('**/test-assets/demo-presentation.mp4', (route) =>
		route.fulfill({ status: 404, body: '' })
	);

	await page.goto('/odi/report/session-video');
	await page.getByRole('tab', { name: '발표 타임라인' }).click();
	await page.getByRole('button', { name: /입력 신호를 구분해 보세요/ }).click();

	const current = page.locator('.current-segment');
	await expect(current.getByText('입력 신호를 구분해 보세요')).toBeVisible();
	await expect(current.getByText('00:34–00:44')).toBeVisible();
	await expect(current.getByText(/일시정지|재생 중/)).toBeVisible();
});

test('영상 표시 설정이 켜져 있고 세션 영상이 없으면 업로드 가능한 빈 상태를 표시한다', async ({
	page
}) => {
	await mockSessionApi(page, 'normal@example.com');
	await page.route('**/odi/db/sessions/session-no-video', (route) =>
		route.fulfill({ json: { session: reportSession('session-no-video') } })
	);

	await page.goto('/odi/report/session-no-video');
	await page.getByRole('tab', { name: '발표 타임라인' }).click();

	await expect(page.getByText('동영상이 없습니다')).toBeVisible();
	await expect(page.getByRole('button', { name: '동영상 업로드' })).toBeVisible();
});

test('세션 영상을 업로드하면 같은 타임라인에서 바로 재생 화면으로 전환한다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	const uploadSession = reportSession('session-upload-video');
	await page.route('**/odi/db/sessions/session-upload-video', (route) =>
		route.fulfill({ json: { session: uploadSession } })
	);
	await page.route('**/odi/db/sessions/session-upload-video/media/upload', (route) => {
		const updated = structuredClone(uploadSession);
		(updated.feedback as any).media = {
			version: 'session-media-v1',
			session_id: 'session-upload-video',
			video_url: '/odi/db/sessions/session-upload-video/media/file',
			title: 'uploaded-demo.mp4',
			source: 'upload'
		};
		return route.fulfill({ json: { session: updated } });
	});
	await page.route('**/odi/db/sessions/session-upload-video/media/file', (route) =>
		route.fulfill({ status: 404, body: '' })
	);

	await page.goto('/odi/report/session-upload-video');
	await page.getByRole('tab', { name: '발표 타임라인' }).click();
	await page.locator('input[type="file"][accept*="video/mp4"]').setInputFiles({
		name: 'uploaded-demo.mp4',
		mimeType: 'video/mp4',
		buffer: Buffer.from('demo-video')
	});

	await expect(page.locator('.video-pane video')).toBeVisible();
	await expect(page.getByText('uploaded-demo.mp4').first()).toBeVisible();
});

test('다른 세션에 묶인 영상은 재생하지 않는다', async ({ page }) => {
	await mockSessionApi(page, 'normal@example.com');
	const sessionWithWrongVideo = reportSession('session-media-owner');
	(sessionWithWrongVideo.feedback as any).media = {
		version: 'session-media-v1',
		session_id: 'session-another',
		video_url: '/test-assets/wrong-session.mp4',
		title: '다른 발표 영상'
	};
	await page.route('**/odi/db/sessions/session-media-owner', (route) =>
		route.fulfill({ json: { session: sessionWithWrongVideo } })
	);

	await page.goto('/odi/report/session-media-owner');
	await page.getByRole('tab', { name: '발표 타임라인' }).click();
	await expect(page.getByRole('alert')).toContainText('이 세션의 영상이 아닙니다');
	await expect(page.locator('.video-pane video')).toHaveCount(0);
});

test('계정 설정에서 리포트 버전을 저장하면 기존 config를 유지하고 화면을 전환한다', async ({
	page
}) => {
	const configuredUser = {
		...odiUser,
		config: {
			keep_existing_value: 'preserved',
			preferences: {
				report_view_version: 'v2',
				show_timeline_video: true,
				another_preference: true
			}
		}
	};
	await mockSessionApi(page, 'normal@example.com', configuredUser);
	const preferenceSession = reportSession('session-preference');
	(preferenceSession.feedback as any).media = {
		video_url: '/test-assets/preference-video.mp4',
		title: '버전 전환 테스트 영상'
	};
	await page.route('**/odi/db/sessions/session-preference', (route) =>
		route.fulfill({ json: { session: preferenceSession } })
	);
	await page.route('**/test-assets/preference-video.mp4', (route) =>
		route.fulfill({ status: 404, body: '' })
	);

	let savedConfig: Record<string, unknown> | null = null;
	await page.route('**/odi/db/users/7/config', async (route) => {
		const payload = route.request().postDataJSON();
		savedConfig = payload.config;
		await route.fulfill({ json: { user: { ...configuredUser, config: payload.config } } });
	});

	await page.goto('/odi/report/session-preference');
	await expect(page.locator('[data-report-version="v2"]')).toBeVisible();
	await expect(page.locator('.video-pane')).toBeVisible();

	await page.locator('.my-page').click();
	await page.getByRole('button', { name: '설정' }).click();
	const dialog = page.getByRole('dialog', { name: '결과 리포트 설정' });
	await expect(dialog.getByLabel(/버전 3/)).toBeEnabled();
	await dialog.getByLabel(/버전 1/).check();
	await dialog.getByLabel('타임라인 연동 영상 표시').uncheck();
	await dialog.getByRole('button', { name: '설정 저장' }).click();

	await expect(dialog.getByRole('status')).toContainText('저장했습니다');
	await expect(page.locator('[data-report-version="v1"]')).toBeVisible();
	await expect(page.locator('.video-pane')).toHaveCount(0);
	expect(savedConfig).toMatchObject({
		keep_existing_value: 'preserved',
		preferences: {
			report_view_version: 'v1',
			show_timeline_video: false,
			another_preference: true
		}
	});
});
