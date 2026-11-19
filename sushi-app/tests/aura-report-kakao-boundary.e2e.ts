import { expect, test, type Page } from '@playwright/test';

const targetId = 37;
const reportId = 91;
const report = {
	id: reportId,
	targetId,
	studentName: '합성 학생',
	schoolId: 11,
	schoolName: '합성 학교',
	progressStage: 'grade1_semester1_midterm',
	roundNumber: 1,
	roundNumbers: [1],
	roundLabel: '합성 1회차',
	startTime: '2026-11-01T10:00:00',
	endTime: '2026-11-01T11:00:00',
	templateVersion: 1,
	contentJson: {
		version: 1,
		documentId: 'synthetic-report-document',
		createdAt: '2026-11-01T00:00:00Z',
		updatedAt: '2026-11-01T00:00:00Z',
		blocks: [
			{
				id: 'synthetic-paragraph',
				type: 'paragraph',
				children: [{ type: 'text', text: '합성 리포트' }]
			}
		]
	},
	analysisJson: {},
	sourceNotes: '',
	questionChecks: {},
	lectureProgress: 5,
	lectureComprehension: 5,
	memoryBefore: 4,
	memoryAfter: 5,
	assessmentJson: null,
	generatedReportJson: {
		schemaVersion: 'aura.clinic-report-output.v2',
		target: { label: '합성 대상' },
		assessment: null,
		learningContent: { paragraphs: ['합성 보고서 내용'] },
		problemSolvingNote: ''
	},
	aiModel: null,
	clinicTargets: [{ id: targetId, studentName: '합성 학생', status: 'draft' }],
	status: 'draft',
	submittedAt: null
};

for (const lookupOutcome of ['unknown', 'missing', 'not_started'] as const) {
test(`Aura recovery: ${lookupOutcome} lookup, no automatic resend`, async ({
	page
}) => {
	const baseURL = test.info().project.use.baseURL;
	if (typeof baseURL !== 'string')
		throw new Error('The E2E test requires a local preview baseURL.');
	const localOrigin = new URL(baseURL);
	if (
		localOrigin.protocol !== 'http:' ||
		!['127.0.0.1', 'localhost'].includes(localOrigin.hostname)
	) {
		throw new Error(`Refusing to open a non-local E2E baseURL: ${localOrigin.origin}`);
	}

	const calls: Array<{ method: string; path: string }> = [];
	const unexpectedRequests: string[] = [];
	const blockedApiProbeRequests: string[] = [];
	const blockedExternalRequests: string[] = [];
	let savedBody: Record<string, unknown> | undefined;
	let resultChecks = 0;
	let sentRequestId = '';
	const previousRequestId = '11111111-1111-4111-8111-111111111111';
	await page.addInitScript(({ targetId, previousRequestId }) => localStorage.setItem(`aura-clinic-send-uncertain:${targetId}`, previousRequestId), { targetId, previousRequestId });

	// One catch-all route makes the network boundary fail closed: only this
	// synthetic auth/report/status/save/send fixture is fulfilled; unknown API
	// calls are aborted and every external request is blocked before networking.
	await page.route('**/*', async (route) => {
		const request = route.request();
		const url = new URL(request.url());
		const method = request.method();
		const path = url.pathname;

		if (path.endsWith('/api/personal/boards') && method === 'GET') {
			return route.fulfill({ json: { canAdmin: false } });
		}
		if (path === '/auth/isjwt' && url.searchParams.get('key') === 'mainauth' && method === 'GET') {
			return route.fulfill({
				json: {
					sub: 'synthetic-user',
					data: { id: 'synthetic-user', name: '합성 사용자', email: 'synthetic@example.invalid' },
					exp: 9999999999
				}
			});
		}
		if (path.endsWith(`/aura/targets/${targetId}/report`) && method === 'GET') {
			return route.fulfill({ json: report });
		}
		if (path.endsWith(`/aura/targets/${targetId}/attachments`) && method === 'GET') {
			return route.fulfill({ json: [] });
		}
		if (path.endsWith('/aura/ai/models') && method === 'GET') {
			return route.fulfill({ json: { defaultModel: '', models: [] } });
		}
		if (path.endsWith(`/aura/targets/${targetId}/ai-reports`) && method === 'GET') {
			return route.fulfill({ json: { targetId, results: [] } });
		}
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`) && method === 'GET') {
			return route.fulfill({ json: null });
		}
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/delivery-requests/${previousRequestId}`) && method === 'GET') {
			resultChecks++;
			if (lookupOutcome === 'missing') return route.fulfill({ status: 404, json: { detail: { code: 'request_not_found', deliveryStatus: 'unknown', retryable: false } } });
			if (lookupOutcome === 'not_started' && resultChecks > 1) return route.fulfill({ json: { deliveryStatus: 'not_started', retryable: true } });
			return route.fulfill({ json: { deliveryStatus: 'unknown' } });
		}
		if (path.endsWith('/aura/kakao-self/status') && method === 'GET') {
			return route.fulfill({ json: { enabled: true, destination: '나와의 채팅', maxPages: 1 } });
		}
		if (path.endsWith(`/aura/target-reports/${reportId}`) && method === 'PATCH') {
			calls.push({ method, path });
			savedBody = request.postDataJSON() as Record<string, unknown>;
			return route.fulfill({
				json: {
					...report,
					contentJson: savedBody.content_json,
					sourceNotes: savedBody.source_notes,
					questionChecks: savedBody.question_checks,
					generatedReportJson: savedBody.generated_report_json
				}
			});
		}
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/send-report`) && method === 'POST') {
			calls.push({ method, path });
			sentRequestId = request.headers()['x-delivery-request-id'] ?? '';
			return route.fulfill({
				json: {
					sent: true,
					sentCount: 1,
					deliveryStatus: 'verified',
					destination: '합성 전송 대상',
					evidence: 'synthetic-only'
				}
			});
		}

		if (path === '/api/personal/__unregistered_probe' && method === 'GET') {
			blockedApiProbeRequests.push(`${method} ${path}`);
			return route.abort();
		}
		if (url.origin !== localOrigin.origin) blockedExternalRequests.push(request.url());
		if (path.startsWith('/api/') || path.startsWith('/auth/') || method !== 'GET') {
			unexpectedRequests.push(`${method} ${path}`);
			return route.abort();
		}
		if (url.origin !== localOrigin.origin) return route.abort();
		return route.continue();
	});

	await page.goto(`/personal-project/aura/reports/${targetId}`);
	await expect(page.getByRole('heading', { name: '합성 학생', exact: true })).toBeVisible();
	const unknownApiWasBlocked = await page.evaluate(async () => {
		try {
			await fetch('/api/personal/__unregistered_probe');
			return false;
		} catch {
			return true;
		}
	});
	const externalProbeUrl = 'https://aura-egress-probe.invalid/should-be-blocked';
	const externalRequestWasBlocked = await page.evaluate(async (url) => {
		try {
			await fetch(url);
			return false;
		} catch {
			return true;
		}
	}, externalProbeUrl);
	expect(unknownApiWasBlocked).toBeTruthy();
	expect(blockedApiProbeRequests).toEqual(['GET /api/personal/__unregistered_probe']);
	expect(externalRequestWasBlocked).toBeTruthy();
	expect(blockedExternalRequests).toContain(externalProbeUrl);

	const sendButton = page.getByRole('button', { name: '카카오톡으로 받기' });
	await expect(sendButton).toBeEnabled();
	await expect(page.getByRole('button', { name: '전송 결과 다시 확인' })).toHaveCount(0);
	await expect(page.getByRole('button', { name: '중복 가능성을 알고 다시 진행' })).toHaveCount(0);
	expect(calls).toEqual([]);
	await sendButton.click();
	await expect(
		page.getByText(/합성 전송 대상에 서버에서 만든 리포트 1장을 보냈습니다/)
	).toBeVisible();
	expect(sentRequestId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
	expect(sentRequestId).not.toBe(previousRequestId);

	expect(calls).toEqual([
		{ method: 'PATCH', path: `/api/personal/aura/target-reports/${reportId}` },
		{ method: 'POST', path: `/api/personal/aura/targets/${targetId}/kakao-clinic/send-report` }
	]);
	expect(savedBody).toMatchObject({
		status: 'draft',
		generated_report_json: report.generatedReportJson
	});
	expect(unexpectedRequests).toEqual([]);
	expect(blockedExternalRequests).toContain(externalProbeUrl);
});
}
