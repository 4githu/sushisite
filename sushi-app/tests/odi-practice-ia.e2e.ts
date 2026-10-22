import { expect, test } from '@playwright/test';

test.use({
	launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }
});

test('My Practice IA: 홈에서 역량·훈련 상세를 거쳐 녹음 화면으로 이동한다', async ({ page }) => {
	let runRequests = 0;
	let attemptBody = '';
	await page.route('**/odi/coaching/practice/attempts', (r) => {
		attemptBody = r.request().postData() ?? '';
		return r.fulfill({
			json: { attempt_id: '1fcb8554-d573-44ec-af37-f8d537247d24', state: 'queued' }
		});
	});
	await page.route('**/odi/coaching/practice/runs', (r) => {
		runRequests += 1;
		expect(r.request().postDataJSON()).toMatchObject({
			metric_id: 'speech_rate',
			origin: 'manual'
		});
		return r.fulfill({
			json: { run_id: '1fcb8554-d573-44ec-af37-f8d537247d23', metric_id: 'speech_rate' }
		});
	});
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: { sub: 'ia-user', data: { id: 'ia-user', name: '검증 사용자' }, exp: 9999999999 }
		})
	);
	await page.route('**/odi/db/login', (r) =>
		r.fulfill({ json: { user: { user_id: 'ia-user', config: {} } } })
	);
	await page.route('**/odi/db/users/ia-user/sessions?*', (r) =>
		r.fulfill({ json: { sessions: [] } })
	);
	await page.route('**/odi/coaching/practice', (r) =>
		r.fulfill({
			json: {
				catalog: [
					{
						id: 'speech_rate',
						title: '발화 속도',
						group: 'delivery',
						task: '주제를 설명하세요.',
						available: true
					}
				],
				attempts: [],
				progress: { completed_count: 0, total_seconds: 0, weekly_successes: 0, metrics: {} }
			}
		})
	);
	await page.goto('/odi/practice');
	await expect(page.getByRole('heading', { name: 'My Practice', level: 1 })).toBeVisible();
	await page.getByRole('button', { name: 'Delivery 역량 보기' }).click();
	await expect(page.getByRole('heading', { name: 'Delivery 역량', level: 2 })).toBeVisible();
	await expect(page.getByRole('heading', { name: '오늘의 추천 훈련' })).toHaveCount(0);
	await page.getByRole('button', { name: '발화 속도 훈련 상세 보기' }).click();
	await expect(page.getByRole('heading', { name: '발화 속도 훈련', level: 2 })).toBeVisible();
	await page.getByRole('button', { name: '연습 시작하기' }).click();
	await expect(page.getByRole('heading', { name: '연습 수행', level: 2 })).toBeVisible();
	await expect(page.getByRole('button', { name: '녹음 시작' })).toBeVisible();
	expect(runRequests).toBe(1);
	await page.getByRole('button', { name: '녹음 시작', exact: true }).click();
	await page.waitForTimeout(2200);
	await page.getByRole('button', { name: '녹음 마치기' }).click();
	await page.getByRole('button', { name: '이 녹음 분석하기' }).click();
	await expect.poll(() => attemptBody).toContain('name="run_id"');
	expect(attemptBody).toContain('1fcb8554-d573-44ec-af37-f8d537247d23');
	expect(attemptBody).toContain('name="stage"');
	expect(attemptBody).toContain('baseline');
});

test('새로고침 후 본인 run 목록에서 완료된 Baseline 결과를 다시 연다', async ({ page }) => {
	const runId = '1fcb8554-d573-44ec-af37-f8d537247d23';
	const attemptId = '1fcb8554-d573-44ec-af37-f8d537247d24';
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: { sub: 'ia-user', data: { id: 'ia-user', name: '검증 사용자' }, exp: 9999999999 }
		})
	);
	await page.route('**/odi/db/login', (r) =>
		r.fulfill({ json: { user: { user_id: 'ia-user', config: {} } } })
	);
	await page.route('**/odi/db/users/ia-user/sessions?*', (r) =>
		r.fulfill({ json: { sessions: [] } })
	);
	await page.route('**/odi/coaching/practice/runs?*', (r) =>
		r.fulfill({
			json: {
				runs: [
					{
						run_id: runId,
						metric_id: 'speech_rate',
						origin: 'manual',
						created_at: '2026-10-22T00:00:00Z'
					}
				]
			}
		})
	);
	await page.route(`**/odi/coaching/practice/runs/${runId}`, (r) =>
		r.fulfill({
			json: {
				run_id: runId,
				metric_id: 'speech_rate',
				stages: [
					{
						stage: 'baseline',
						attempt_id: attemptId,
						state: 'completed',
						score: 80,
						target_seconds: 60,
						duration_seconds: 58.5
					}
				],
				follow_up_sessions: []
			}
		})
	);
	await page.route('**/odi/coaching/practice', (r) =>
		r.fulfill({
			json: {
				catalog: [
					{
						id: 'speech_rate',
						title: '발화 속도',
						group: 'delivery',
						task: '설명하세요.',
						available: true
					}
				],
				attempts: [
					{
						attempt_id: attemptId,
						metric_id: 'speech_rate',
						state: 'completed',
						score: 80,
						feedback: { feedback: '속도가 안정적입니다.', evidence: '첫 문장' },
						transcript: '첫 문장',
						created_at: '2026-10-22T00:00:00Z'
					}
				],
				progress: { completed_count: 1, total_seconds: 30, weekly_successes: 1, metrics: {} }
			}
		})
	);
	await page.goto('/odi/practice');
	await page.getByRole('button', { name: /발화 속도 연습 이어보기/ }).click();
	await expect(page.getByRole('heading', { name: '연습 결과', level: 2 })).toBeVisible();
	await expect(page.locator('.practice-ia')).toContainText('속도가 안정적입니다.');
	await expect(page.locator('.practice-ia')).toContainText('목표 60초 · 실제 58.5초');
	await page.getByRole('button', { name: 'Guided Practice 시작' }).click();
	await expect(page.locator('.practice-ia')).toContainText('Guided Practice');
	await expect(page.getByRole('button', { name: '녹음 시작', exact: true })).toBeVisible();
});

test('전이 과제 완료 뒤 실제 세션을 명시적으로 연결하고 개선 판정을 만들지 않는다', async ({
	page
}) => {
	const runId = '1fcb8554-d573-44ec-af37-f8d537247d23';
	const attemptId = '1fcb8554-d573-44ec-af37-f8d537247d24';
	let linked = false;
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: { sub: 'ia-user', data: { id: 'ia-user', name: '검증 사용자' }, exp: 9999999999 }
		})
	);
	await page.route('**/odi/db/login', (r) =>
		r.fulfill({ json: { user: { user_id: 'ia-user', config: {} } } })
	);
	await page.route('**/odi/db/users/ia-user/sessions?*', (r) =>
		r.fulfill({
			json: {
				sessions: [
					{
						session_id: 'before-transfer',
						user_id: 'ia-user',
						state: 'completed',
						started_at: '2026-10-22T12:00:00Z',
						ended_at: '2026-10-22T13:00:00Z',
						template: { environment: { title: '전이 완료 전 발표' } }
					},
					{
						session_id: 'later-session',
						user_id: 'ia-user',
						state: 'completed',
						created_at: '2026-10-24T00:00:00Z',
						started_at: '2026-10-24T00:00:00Z',
						ended_at: '2026-10-24T01:00:00Z',
						template: { environment: { title: '후속 발표' } }
					}
				]
			}
		})
	);
	await page.route('**/odi/coaching/practice/runs?*', (r) =>
		r.fulfill({
			json: {
				runs: [{ run_id: runId, metric_id: 'speech_rate', created_at: '2026-10-22T00:00:00Z' }]
			}
		})
	);
	await page.route(`**/odi/coaching/practice/runs/${runId}`, (r) =>
		r.fulfill({
			json: {
				run_id: runId,
				metric_id: 'speech_rate',
				created_at: '2026-10-22T00:00:00Z',
				stages: [
					{
						stage: 'transfer_challenge',
						attempt_id: attemptId,
						state: 'completed',
						score: 81,
						completed_at: '2026-10-23T00:00:00Z'
					}
				],
				follow_up_sessions: linked ? ['later-session'] : []
			}
		})
	);
	await page.route(`**/odi/coaching/practice/runs/${runId}/followups`, (r) => {
		expect(r.request().postDataJSON()).toEqual({ session_id: 'later-session' });
		linked = true;
		return r.fulfill({ json: { run_id: runId, session_id: 'later-session' } });
	});
	await page.route('**/odi/coaching/practice', (r) =>
		r.fulfill({
			json: {
				catalog: [
					{
						id: 'speech_rate',
						title: '발화 속도',
						group: 'delivery',
						task: '설명하세요.',
						available: true
					}
				],
				attempts: [
					{
						attempt_id: attemptId,
						metric_id: 'speech_rate',
						state: 'completed',
						score: 81,
						feedback: { feedback: '근거를 확인하세요.', evidence: '첫 문장' },
						transcript: '첫 문장',
						created_at: '2026-10-23T00:00:00Z'
					}
				],
				progress: { completed_count: 1, total_seconds: 30, weekly_successes: 1, metrics: {} }
			}
		})
	);
	await page.goto('/odi/practice');
	await page.getByRole('button', { name: /발화 속도 연습 이어보기/ }).click();
	await expect(page.locator('.practice-ia')).toContainText(
		'전이 성공 여부는 아직 판단할 수 없습니다'
	);
	await expect(page.locator('.practice-ia')).toContainText('목표 시간이 달라질 수 있어');
	await expect(
		page.getByLabel('후속 세션 선택').locator('option[value="before-transfer"]')
	).toHaveCount(0);
	await page.getByLabel('후속 세션 선택').selectOption('later-session');
	await page.getByRole('button', { name: '세션 연결하기' }).click();
	await expect(page.locator('.practice-ia')).toContainText('후속 발표 연결됨');
	expect(linked).toBe(true);
	await expect(page.locator('.practice-ia')).not.toContainText('개선 확인');
});

test('실패한 단계는 새 녹음·새 시도 ID로 명시적으로 재시작한다', async ({ page }) => {
	const runId = '1fcb8554-d573-44ec-af37-f8d537247d23';
	const failedId = '1fcb8554-d573-44ec-af37-f8d537247d24';
	let attemptBody = '';
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({ json: { sub: 'ia-user', data: { id: 'ia-user' }, exp: 9999999999 } })
	);
	await page.route('**/odi/db/login', (r) =>
		r.fulfill({ json: { user: { user_id: 'ia-user', config: {} } } })
	);
	await page.route('**/odi/db/users/ia-user/sessions?*', (r) =>
		r.fulfill({ json: { sessions: [] } })
	);
	await page.route('**/odi/coaching/practice/runs?*', (r) =>
		r.fulfill({
			json: {
				runs: [{ run_id: runId, metric_id: 'speech_rate', created_at: '2026-10-22T00:00:00Z' }]
			}
		})
	);
	await page.route(`**/odi/coaching/practice/runs/${runId}`, (r) =>
		r.fulfill({
			json: {
				run_id: runId,
				metric_id: 'speech_rate',
				stages: [{ stage: 'baseline', attempt_id: failedId, state: 'failed', score: null }],
				follow_up_sessions: []
			}
		})
	);
	await page.route('**/odi/coaching/practice', (r) =>
		r.fulfill({
			json: {
				catalog: [
					{
						id: 'speech_rate',
						title: '발화 속도',
						group: 'delivery',
						task: '설명하세요.',
						available: true
					}
				],
				attempts: [
					{
						attempt_id: failedId,
						metric_id: 'speech_rate',
						state: 'failed',
						error: '분석 오류',
						created_at: '2026-10-22T00:00:00Z'
					}
				],
				progress: { completed_count: 0, total_seconds: 0, weekly_successes: 0, metrics: {} }
			}
		})
	);
	await page.route('**/odi/coaching/practice/attempts', (r) => {
		attemptBody = r.request().postData() ?? '';
		return r.fulfill({ json: { attempt_id: 'new-attempt', state: 'queued' } });
	});
	await page.goto('/odi/practice');
	await page.getByRole('button', { name: /발화 속도 연습 이어보기/ }).click();
	await page.getByRole('button', { name: '새 녹음으로 다시 시작' }).click();
	await page.getByRole('button', { name: '녹음 시작', exact: true }).click();
	await page.waitForTimeout(2200);
	await page.getByRole('button', { name: '녹음 마치기' }).click();
	await page.getByRole('button', { name: '이 녹음 분석하기' }).click();
	await expect.poll(() => attemptBody).toContain('name="restart_failed"');
	expect(attemptBody).toContain('true');
	expect(attemptBody).toContain(`name="run_id"\r\n\r\n${runId}`);
	expect(attemptBody).toContain('name="stage"\r\n\r\nbaseline');
	expect(attemptBody).not.toContain(`name="attempt_id"\r\n\r\n${failedId}`);
});
