import { expect, test, type Page } from '@playwright/test';
const environment = {
	title: '반복 연습',
	purpose: '발표',
	language: '한국어',
	place: '세미나실',
	duration_minutes: 30,
	question_count: 3
};
const draft = {
	id: 't1',
	version: 1,
	type: 'presentation',
	environment,
	files: { slide: null, paper: null, script: null, script_content: '이것은 원문입니다.' },
	audience: {
		audience_type: '대학생',
		audience_count: 6,
		expertise_level: '중간',
		interest_level: '중간'
	}
};
const user = {
	user_id: 'workspace-test',
	auth_id: 'workspace-test',
	config: { favorite_template_ids: ['t2'] },
	recent_template: draft,
	created_at: '2026-09-12',
	updated_at: '2026-09-12'
};
function record(i: number) {
	return {
		session_id: `s${i}`,
		user_id: user.user_id,
		template_id: i % 2 ? 't1' : 't2',
		template: draft,
		feedback: {
			score: { overall_score: i === 0 ? 0 : 80 },
			duration: { actual_seconds: 60 },
			score_card: { scores: { engagement: 80, clarity: 80, credibility: 80 } }
		},
		state: 'completed',
		ended_at: new Date(Date.UTC(2026, 8, 1, 0, 0, i)).toISOString(),
		created_at: new Date(Date.UTC(2026, 8, 1, 0, 0, i)).toISOString()
	};
}
async function setup(page: Page, count = 205) {
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: {
				sub: user.user_id,
				data: { id: user.user_id, name: '검증 사용자', email: 'test@example.com' },
				exp: 9999999999
			}
		})
	);
	await page.route('**/odi/db/login', (r) => r.fulfill({ json: { user } }));
	await page.route(`**/odi/db/users/${user.user_id}/sessions?*`, (r) => {
		const offset = Number(new URL(r.request().url()).searchParams.get('offset') ?? 0);
		return r.fulfill({
			json: {
				sessions: Array.from({ length: count }, (_, i) => record(i)).slice(offset, offset + 200)
			}
		});
	});
	await page.route(`**/odi/db/users/${user.user_id}/templates`, (r) =>
		r.fulfill({
			json: {
				templates: Array.from({ length: 12 }, (_, i) => ({
					template_id: `t${i + 1}`,
					version: 1,
					template: {
						...draft,
						id: `t${i + 1}`,
						environment: { ...environment, title: `환경 ${i + 1}` }
					},
					use_count: 12 - i,
					last_used_at: new Date(Date.UTC(2026, 8, 12 - i)).toISOString(),
					updated_at: '2026-09-12'
				}))
			}
		})
	);
}
test('200개 이후 기록도 포함하고 동명 템플릿을 ID별로 구분하며 통계는 검색과 독립적이다', async ({
	page
}) => {
	await setup(page);
	await page.goto('/odi/report');
	await expect(page.locator('.topic')).toHaveCount(2);
	await page.getByRole('button', { name: '전체 기록', exact: true }).click();
	await expect(page.getByText('총 205개 기록')).toBeVisible();
	const stats = await page.locator('.stat-grid').innerText();
	await page.getByLabel('세션 이름 검색').fill('없는 이름');
	await expect(page.getByText('검색 결과가 없어요.')).toBeVisible();
	expect(await page.locator('.stat-grid').innerText()).toBe(stats);
	await page.getByLabel('세션 이름 검색').fill('');
	await page
		.getByRole('navigation', { name: '페이지 이동' })
		.getByRole('button', { name: '41', exact: true })
		.click();
	await expect(page.locator('tbody tr')).toHaveCount(5);
	await expect(page.locator('tbody').getByText('0', { exact: true })).toBeVisible();
});
test('템플릿 전체 목록, 즐겨찾기, 검색과 페이지 이동 및 저장만 수행하는 동작', async ({ page }) => {
	await setup(page, 0);
	let saves = 0,
		starts = 0;
	await page.route('**/odi/db/pre-sessions/start', (r) => {
		starts++;
		return r.fulfill({ status: 500, json: {} });
	});
	await page.route('**/odi/db/templates/t2', (r) => {
		saves++;
		const sent = r.request().postDataJSON();
		expect(sent.expected_version).toBe(1);
		return r.fulfill({
			json: { template: { template: { ...sent.template, version: 2 }, version: 2 } }
		});
	});
	await page.goto('/odi/favorites');
	await expect(page).toHaveURL(/\/odi\/templates$/);
	await expect(page.getByText('총 12개 템플릿')).toBeVisible();
	await page.getByRole('button', { name: '즐겨찾기', exact: true }).click();
	await expect(page.getByText('총 1개 템플릿')).toBeVisible();
	await page.getByRole('button', { name: '수정', exact: true }).click();
	await expect(page.getByText('저장된 기본 환경', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: '이 템플릿의 기본 환경으로 저장' }).click();
	await expect(page.getByText('기본 환경을 저장했어요.')).toBeVisible();
	expect(saves).toBe(1);
	expect(starts).toBe(0);
});
test('스크립트 수정 제안은 원문 변경 시 적용을 막고 다시 검사 후 선택 적용한다', async ({
	page
}) => {
	await setup(page, 0);
	await page.route('**/odi/coaching/script/check', (r) => {
		const req = r.request().postDataJSON();
		return r.fulfill({
			json: {
				version: req.version,
				source_text: req.text,
				source_hash: 'test',
				sections: [{ slide: null, text: req.text }],
				suggestions: [
					{
						id: 'one',
						category: 'length',
						start: 0,
						end: req.text.length,
						original: req.text,
						replacement: '짧은 발표입니다.'
					}
				],
				page_count: 0,
				mapping_available: false,
				estimated_seconds: 5
			}
		});
	});
	await page.goto('/odi/session/presentation/script');
	await page.getByLabel('전체 스크립트').fill('이것은 아주 긴 발표 원문입니다.');
	await page.getByRole('button', { name: '다시 검사하기' }).click();
	await expect(page.getByText('1문장').first()).toBeVisible();
	await page.getByLabel('전체 스크립트').fill('원문이 변경되었습니다.');
	await expect(page.getByRole('button', { name: '모두 적용하기' })).toBeDisabled();
	await page.getByRole('button', { name: '다시 검사하기' }).click();
	await page.getByRole('checkbox', { name: '수정 제안 선택' }).check();
	await page.getByRole('button', { name: '선택 항목 적용하기' }).click();
	await expect(page.getByLabel('슬라이드 1 스크립트')).toHaveValue('짧은 발표입니다.');
});
for (const width of [1440, 820, 390])
	test(`홈·템플릿·리포트·훈련은 ${width}px에서 문서 가로 넘침이 없다`, async ({ page }) => {
		await page.setViewportSize({ width, height: 900 });
		await setup(page, 3);
		await page.route('**/odi/coaching/practice', (r) =>
			r.fulfill({
				json: {
					catalog: [
						{
							id: 'speech_rate',
							title: '발화 속도',
							group: 'delivery',
							task: '설명하세요',
							available: true
						},
						{ id: 'gaze', title: '시선 처리', group: 'delivery', task: '준비 중', available: false }
					],
					attempts: [],
					progress: { completed_count: 0, total_seconds: 0, weekly_successes: 0, metrics: {} }
				}
			})
		);
		for (const path of ['/odi', '/odi/templates', '/odi/report', '/odi/practice']) {
			await page.goto(path);
			await expect(page.locator('.odi-workspace')).toBeVisible();
			await expect(page.getByText(/불러오는 중/)).toHaveCount(0);
			const layout = await page.evaluate(() => ({
				width: innerWidth,
				scroll: document.documentElement.scrollWidth,
				overflow: [...document.querySelectorAll('.odi-workspace,.odi-workspace > *, .toolbar > *')]
					.filter((e) => e.getBoundingClientRect().right > innerWidth)
					.map((e) => ({
						tag: e.tagName,
						cls: e.className,
						right: e.getBoundingClientRect().right,
						width: e.getBoundingClientRect().width
					}))
			}));
			expect(layout.scroll, `${path} ${JSON.stringify(layout)}`).toBe(width);
		}
		await expect(page.getByRole('button', { name: /시선 처리/ })).toBeDisabled();
	});
test('기록 없는 홈에는 예시 점수 없이 사용 안내를 표시한다', async ({ page }) => {
	await setup(page, 0);
	await page.goto('/odi');
	await expect(page.getByRole('heading', { name: '어떻게 진행되나요?' })).toBeVisible();
	await expect(page.getByText('평균 세션 점수')).toHaveCount(0);
});

test.use({
	launchOptions: { args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] }
});
test.describe('웹 녹음', () => {
	const catalog = [
		{
			id: 'speech_rate',
			title: '발화 속도',
			group: 'delivery',
			task: '주제를 설명하세요.',
			available: true
		}
	];
	test('마이크 거부 상태를 표시하고 다시 시작할 수 있다', async ({ page }) => {
		await setup(page, 0);
		await page.route('**/odi/coaching/practice', (r) =>
			r.fulfill({
				json: {
					catalog,
					attempts: [],
					progress: { completed_count: 0, total_seconds: 0, weekly_successes: 0, metrics: {} }
				}
			})
		);
		await page.addInitScript(() => {
			navigator.mediaDevices.getUserMedia = async () => {
				throw new DOMException('Denied', 'NotAllowedError');
			};
		});
		await page.goto('/odi/practice?training=speech_rate');
		await page.getByRole('button', { name: '녹음 시작', exact: true }).click();
		await expect(page.getByRole('alert')).toContainText('마이크 권한이 필요해요');
		await expect(page.getByRole('button', { name: '녹음 시작', exact: true })).toBeEnabled();
	});
	test('녹음 재생과 분석 실패 재시도는 같은 시도 ID를 사용하고 결과를 한 번 표시한다', async ({
		page
	}) => {
		await setup(page, 0);
		let id = '',
			requests = 0;
		const ids: string[] = [];
		await page.route('**/odi/coaching/practice/attempts', (r) => {
			requests++;
			const body = r.request().postData() ?? '';
			id = body.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0] ?? '';
			ids.push(id);
			return r.fulfill({ json: { attempt_id: id, state: 'queued' } });
		});
		await page.route('**/odi/coaching/practice', (r) =>
			r.fulfill({
				json: {
					catalog,
					attempts: id
						? [
								{
									attempt_id: id,
									metric_id: 'speech_rate',
									state: requests === 1 ? 'failed' : 'completed',
									score: 80,
									created_at: '2026-09-12',
									error: '분석을 다시 시도해 주세요.',
									feedback: { feedback: '안정적인 속도입니다.', evidence: '반복 연습' },
									transcript: '반복 연습'
								}
							]
						: [],
					progress: {
						completed_count: requests >= 2 ? 1 : 0,
						total_seconds: requests >= 2 ? 2 : 0,
						weekly_successes: requests >= 2 ? 1 : 0,
						metrics: {}
					}
				}
			})
		);
		await page.goto('/odi/practice?training=speech_rate');
		await page.getByRole('button', { name: '녹음 시작', exact: true }).click();
		await page.waitForTimeout(2200);
		await page.getByRole('button', { name: '녹음 마치기' }).click();
		await expect(page.locator('audio')).toBeVisible();
		await page.getByRole('button', { name: '이 녹음 분석하기' }).click();
		await page.getByRole('button', { name: '분석 다시 시도' }).click();
		await expect(page.locator('.result')).toContainText('80점');
		expect(ids[0]).toBeTruthy();
		expect(ids[0]).toBe(ids[1]);
		await expect(page.locator('.history details')).toHaveCount(1);
	});
});
