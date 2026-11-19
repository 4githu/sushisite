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

test('AI 502 reports unknown cause and a safe next step', async ({
	page
}) => {
	let historyGetCount = 0;
	let generationPostCount = 0;
	let savedReport: Record<string, unknown> = { ...report };
	const appOrigin = new URL(test.info().project.use.baseURL ?? 'http://127.0.0.1:4173').origin;

	await page.route('**/auth/isjwt?key=mainauth', (route) => {
		if (new URL(route.request().url()).origin !== appOrigin) return route.continue();
		return route.fulfill({
			json: {
				sub: '1',
				data: { id: '1', name: '합성 검증', email: 'synthetic@example.com' },
				exp: 9999999999
			}
		});
	});
	await page.route('**/api/personal/**', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		if (url.origin !== appOrigin) return route.continue();
		const path = url.pathname;
		const method = request.method();

		if (path.endsWith('/aura/ai/models') && method === 'GET') {
			return route.fulfill({
				json: {
					defaultModel: 'synthetic-model',
					models: [
						{
							id: 'synthetic-model',
							provider: 'synthetic',
							label: '합성 모델',
							description: '',
							is_default: true,
							explicit_cache: false
						}
					]
				}
			});
		}
		if (path.endsWith(`/aura/targets/${targetId}/report`) && method === 'GET') {
			return route.fulfill({ json: savedReport });
		}
		if (path.endsWith(`/aura/targets/${targetId}/attachments`) && method === 'GET') {
			return route.fulfill({ json: [] });
		}
		if (path.endsWith(`/aura/targets/${targetId}/ai-reports/generate`) && method === 'POST') {
			generationPostCount += 1;
			return route.fulfill({
				status: 502, json: { detail: {} }
			});
		}
		if (path.endsWith(`/aura/targets/${targetId}/ai-reports`) && method === 'GET') {
			historyGetCount += 1;
			if (historyGetCount === 1) return route.fulfill({ json: { targetId, results: [] } });
			return route.fulfill({
				status: 502,
				contentType: 'application/json',
				body: JSON.stringify({ detail: '합성 history GET 오류' })
			});
		}
		if (path.endsWith(`/aura/target-reports/${report.id}`) && method === 'PATCH') {
			const body = request.postDataJSON();
			savedReport = {
				...savedReport,
				generatedReportJson: body.generated_report_json,
				aiModel: body.ai_model
			};
			return route.fulfill({ json: savedReport });
		}
		if (path.endsWith('/aura/unit-templates') && method === 'GET') {
			return route.fulfill({ json: [] });
		}
		return route.fulfill({
			status: 404,
			json: { detail: `Unexpected synthetic request: ${method} ${path}` }
		});
	});

	await page.goto(`/personal-project/aura/reports/${targetId}`);
	await page.getByRole('button', { name: 'AI 리포트 생성' }).first().click();

	await expect(page.locator('.error-banner')).toContainText('AI 리포트를 생성하지 못했습니다');
	await expect(page.locator('.error-banner')).toContainText('원인은 확인되지 않았습니다');
	await expect(page.locator('.error-banner')).toContainText('생성 기록을 확인');
	await expect.poll(() => generationPostCount).toBe(1);
});
