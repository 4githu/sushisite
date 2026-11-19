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

test('Aura report send flow uses only mocked save/send APIs and blocks unregistered or external requests', async ({
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
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`) && method === 'GET') {
			return route.fulfill({ json: calls.some((call) => call.method === 'POST') ? { id: 'synthetic', targetId, state: 'queued', requestedAt: 1794300000, sendAfter: 1794305400, errorCode: null } : null });
		}
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`) && method === 'POST') {
			calls.push({ method, path });
			return route.fulfill({ json: { id: 'synthetic', targetId, state: 'queued', requestedAt: 1794300000, sendAfter: 1794305400, errorCode: null } });
		}
		if (path.startsWith(`/api/personal/aura/targets/${targetId}/kakao-clinic/delivery-requests/`) && method === 'GET') {
			return route.fulfill({ status: 404, json: { detail: '합성 요청 결과 없음' } });
		}
		if (path.endsWith(`/aura/targets/${targetId}/kakao-clinic/send-report`) && method === 'POST') {
			calls.push({ method, path });
			return route.fulfill({
				json: {
					sent: true,
					deliveryStatus: 'verified',
					sentCount: 1,
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

	const sendButton = page.getByRole('button', { name: '90분 후 전송 예약' });
	await expect(sendButton).toBeEnabled();
	await expect(sendButton).toHaveCSS('border-top-style', 'solid');
	await expect(sendButton).toHaveCSS('cursor', 'pointer');
	let releaseSave!: () => void;
	const saveGate = new Promise<void>((resolve) => { releaseSave = resolve; });
	let saveStarted!: () => void;
	const saveObserved = new Promise<void>((resolve) => { saveStarted = resolve; });
	await page.route(`**/api/personal/aura/target-reports/${reportId}`, async (route) => {
		if (route.request().method() !== 'PATCH') return route.fallback();
		saveStarted();
		await saveGate;
		return route.fallback();
	}, { times: 1 });
	await sendButton.click();
	await saveObserved;
	await expect(page.getByRole('button', { name: '카카오톡으로 받기' })).toBeDisabled();
	releaseSave();
	await expect(page.getByText(/예약 대기/)).toBeVisible();
	await expect(sendButton).toBeDisabled();
	expect(calls).toEqual([
		{ method: 'PATCH', path: `/api/personal/aura/target-reports/${reportId}` },
		{ method: 'POST', path: `/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries` }
	]);
	await page.reload();
	await expect(page.getByText(/예약 대기/)).toBeVisible();
	await expect(page.getByRole('button', { name: '90분 후 전송 예약' })).toBeDisabled();
	await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries/synthetic`, async (route) => {
		expect(route.request().method()).toBe('DELETE');
		await route.fulfill({ json: { id: 'synthetic', targetId, state: 'cancelled', requestedAt: 1794300000, sendAfter: 1794305400, errorCode: null } });
	}, { times: 1 });
	await page.getByRole('button', { name: '예약 취소' }).click();
	await expect(page.getByText('예약 취소됨', { exact: false })).toBeVisible();
	await expect(page.getByText('예정 시각:', { exact: false })).toHaveCount(0);
	await expect(page.getByRole('button', { name: '90분 후 전송 예약' })).toBeEnabled();
	await expect(page.getByRole('button', { name: '예약 취소' })).toHaveCount(0);
	for (const [state, label] of [['generating', '리포트 생성 중'], ['ready', '전송 준비 완료'], ['sending', '전송 중'], ['sent', '전송 완료'], ['unknown', '전송 결과 확인 필요'], ['partial', '일부 전송 · 확인 필요'], ['failed', '예약 실패']] as const) {
		await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`, (route) => route.fulfill({ json: { id: 'synthetic', targetId, state, requestedAt: 1794300000, sendAfter: 1794305400, errorCode: 'PRIVATE_TEST_CODE' } }), { times: 1 });
		await page.reload();
		await expect(page.getByText(label, { exact: false })).toBeVisible();
		await expect(page.getByText('PRIVATE_TEST_CODE')).toHaveCount(0);
		if (state === 'unknown' || state === 'partial') {
			await expect(page.getByRole('button', { name: '카카오톡으로 받기' })).toBeEnabled();
		}
		if (state === 'sent') {
			const resend = page.getByRole('button', { name: '카카오톡으로 받기' });
			await expect(resend).toBeEnabled();
			await resend.click();
			await expect(resend).toBeEnabled();
		}
		await expect(page.getByRole('button', { name: '예약 취소' })).toHaveCount(state === 'generating' || state === 'ready' ? 1 : 0);
		if (state === 'failed') await expect(page.getByRole('button', { name: '90분 후 다시 예약' })).toBeEnabled();
		else await expect(page.getByRole('button', { name: '90분 후 전송 예약' })).toBeDisabled();
	}
	await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/send-report`, (route) => route.abort(), { times: 1 });
	await page.getByRole('button', { name: '카카오톡으로 받기' }).click();
	await expect(page.getByText(/전송 결과를 확인할 수 없습니다/).first()).toBeVisible();
	await expect(page.getByRole('button', { name: '카카오톡으로 받기' })).toBeEnabled();
	await expect(page.getByRole('button', { name: '90분 후 다시 예약' })).toBeEnabled();
	await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`, (route) => route.fulfill({ json: { id: 'synthetic', targetId, state: 'failed', requestedAt: 1794300000, sendAfter: 1794305400, errorCode: null } }), { times: 1 });
	await page.reload();
	await expect(page.getByText(/전송 결과를 확인할 수 없습니다/).first()).toBeVisible();
	await expect(page.getByRole('button', { name: '카카오톡으로 받기' })).toBeEnabled();
	await page.setViewportSize({ width: 390, height: 844 });
	await expect(page.getByRole('button', { name: /90분 후 (다시 예약|전송 예약)/ })).toBeVisible();
	expect(savedBody).toMatchObject({
		status: 'draft',
		generated_report_json: report.generatedReportJson
	});
	expect(unexpectedRequests).toEqual([]);
	expect(blockedExternalRequests).toContain(externalProbeUrl);
	await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`, (route) => route.abort(), { times: 1 });
	await page.reload();
	await expect(page.getByText('예약 상태를 확인하지 못했습니다. 연결을 확인한 뒤 다시 확인하세요.')).toBeVisible();
	const immediate = page.getByRole('button', { name: '카카오톡으로 받기' });
	await expect(immediate).toBeEnabled();
	const before = calls.filter((call) => call.path.endsWith('/send-report')).length;
	await immediate.click();
	await expect.poll(() => calls.filter((call) => call.path.endsWith('/send-report')).length).toBe(before + 1);
	for (const state of ['queued', 'ready'] as const) {
		await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries`, (route) => route.fulfill({ json: { id: 'replace-me', targetId, state, requestedAt: 1794300000, sendAfter: 1794305400, errorCode: null } }), { times: 1 });
		await page.reload();
		await expect(immediate).toBeEnabled();
		await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/scheduled-deliveries/replace-me`, (route) => route.fulfill({ json: { id: 'replace-me', targetId, state: 'cancelled', requestedAt: 1794300000, sendAfter: 1794305400, errorCode: 'superseded_by_immediate' } }), { times: 1 });
		if (state === 'ready') await page.route(`**/api/personal/aura/targets/${targetId}/kakao-clinic/send-report`, (route) => route.fulfill({ status: 500, json: { detail: '합성 전송 실패' } }), { times: 1 });
		await immediate.click();
		await expect(page.getByText('기존 예약이 취소되었습니다. 즉시 전송이 실패해도 예약은 복원되지 않습니다.')).toBeVisible();
	}
});
