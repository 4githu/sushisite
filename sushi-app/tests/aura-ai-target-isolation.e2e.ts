import { expect, test } from '@playwright/test';

const targetId = 7341;
const report = {
	id: 2841,
	targetId,
	studentName: '합성 학생',
	startTime: '2026-09-25T00:00:00Z',
	endTime: '2026-09-25T01:00:00Z',
	schoolId: 7,
	schoolName: '검증고',
	progressStage: 'accepted',
	roundNumber: 1,
	roundNumbers: [1],
	roundLabel: '1회차',
	templateVersion: 1,
	status: 'draft',
	sourceNotes: '',
	questionChecks: {},
	lectureProgress: 5,
	lectureComprehension: 5,
	memoryBefore: 4,
	memoryAfter: 5,
	assessmentJson: null,
	generatedReportJson: null,
	aiModel: null,
	clinicTargets: [],
	contentJson: {
		version: 1,
		documentId: 'synthetic-aura-report',
		createdAt: '2026-09-25T00:00:00Z',
		updatedAt: '2026-09-25T00:00:00Z',
		blocks: [
			{
				id: 'synthetic-block',
				type: 'paragraph',
				children: [{ type: 'text', text: '합성 테스트' }]
			}
		]
	}
};

const generatedResult = {
	runId: 991,
	provider: 'synthetic',
	model: 'synthetic-model',
	cacheMode: 'explicit',
	reused: false,
	output: {
		target: {},
		assessment: null,
		learningContent: { paragraphs: ['합성 AI 생성 결과입니다.'] },
		problemSolvingNote: ''
	}
};

for (const failFirst of [false, true])
	test(`target isolation and reversed responses (first failure: ${failFirst})`, async ({
		page
	}) => {
		const appOrigin = new URL(test.info().project.use.baseURL ?? 'http://127.0.0.1:4173').origin;
		const targets = [
			{ id: 7341, studentName: '합성 학생', status: 'draft' },
			{ id: 7342, studentName: '합성 둘', status: 'draft' }
		];
		const saved: Record<number, any> = {
			7341: { ...report, clinicTargets: targets },
			7342: { ...report, id: 2842, targetId: 7342, studentName: '합성 둘', clinicTargets: targets }
		};
		const releases: Record<number, () => void> = {};
		const started: number[] = [];
		await page.route('**/auth/isjwt?key=mainauth', (route) =>
			route.fulfill({
				json: {
					sub: '1',
					data: { id: '1', name: '합성', email: 'synthetic@example.com' },
					exp: 9999999999
				}
			})
		);
		await page.route('**/api/personal/**', async (route) => {
			const req = route.request(),
				url = new URL(req.url()),
				path = url.pathname,
				method = req.method();
			if (url.origin !== appOrigin) return route.continue();
			if (path.endsWith('/aura/ai/models'))
				return route.fulfill({
					json: {
						defaultModel: 'synthetic-model',
						models: [
							{ id: 'synthetic-model', provider: 'synthetic', label: '합성 모델', is_default: true }
						]
					}
				});
			const target = Number(path.match(/targets\/(\d+)/)?.[1]);
			if (path.endsWith('/report') && method === 'GET')
				return route.fulfill({ json: saved[target] });
			if (path.endsWith('/attachments')) return route.fulfill({ json: [] });
			if (path.endsWith('/ai-reports/generate')) {
				started.push(target);
				await new Promise<void>((resolve) => {
					releases[target] = resolve;
				});
				if (failFirst && target === 7341)
					return route.fulfill({ status: 502, json: { detail: {} } });
				return route.fulfill({
					json: {
						targetId: target,
						results: [
							{
								...generatedResult,
								runId: target,
								output: {
									...generatedResult.output,
									learningContent: { paragraphs: [`결과 ${target}`] }
								}
							}
						],
						errors: []
					}
				});
			}
			if (path.endsWith('/ai-reports'))
				return route.fulfill({ json: { targetId: target, results: [] } });
			if (path.includes('/target-reports/') && method === 'PATCH') {
				const id = Number(path.split('/').pop());
				const t = id === 2841 ? 7341 : 7342;
				const body = req.postDataJSON();
				if ('generated_report_json' in body)
					saved[t].generatedReportJson = body.generated_report_json;
				if ('ai_model' in body) saved[t].aiModel = body.ai_model;
				return route.fulfill({ json: saved[t] });
			}
			if (path.endsWith('/aura/unit-templates')) return route.fulfill({ json: [] });
			return route.fulfill({ status: 404, json: { detail: `Unexpected ${method} ${path}` } });
		});
		await page.goto('/personal-project/aura/reports/7341');
		await page.getByRole('button', { name: 'AI 리포트 생성' }).first().click();
		await expect.poll(() => started.includes(7341)).toBeTruthy();
		await page
			.getByRole('navigation', { name: '같은 클리닉 학생 전환' })
			.getByRole('button', { name: '합성 둘작성 중' })
			.click();
		await page.getByRole('button', { name: 'AI 리포트 생성' }).first().click();
		await expect.poll(() => started.includes(7342)).toBeTruthy();
		releases[7342]();
		await expect.poll(() => saved[7342].generatedReportJson?.runId).toBe(7342);
		releases[7341]();
		if (failFirst) {
			await expect(
				page
					.getByRole('navigation', { name: '같은 클리닉 학생 전환' })
					.getByRole('button', { name: /합성 학생.*확인하지 못했습니다/ })
			).toBeVisible();
			expect(saved[7341].generatedReportJson).toBeNull();
		} else {
			await expect.poll(() => saved[7341].generatedReportJson?.runId).toBe(7341);
		}
		await expect(page.locator('.report-modal')).toContainText('결과 7342');
		await expect(page.locator('.report-modal')).not.toContainText('결과 7341');
	});
