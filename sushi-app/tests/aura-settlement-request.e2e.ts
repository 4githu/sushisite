import { expect, test, type Page } from '@playwright/test';

const round = (
	id: number,
	schoolName: string,
	progressStage: string,
	studentName: string,
	parentFreeForThreePlus = false
) => ({
	id,
	schoolId: id,
	schoolName,
	progressStage,
	parentFreeForThreePlus,
	eventId: id,
	roundNumber: 1,
	roundNumbers: [1],
	roundLabel: `${id}회`,
	startTime: '2026-10-10T10:00:00',
	endTime: '2026-10-10T11:00:00',
	description: '',
	attendanceStatus: 'completed',
	reportRequired: true,
	hourlyRate: 30000,
	amount: 30000,
	paymentStatus: 'pending',
	seriesGroupId: null,
	seriesIndex: null,
	targets: [{ id: id * 10, studentName, report: null }]
});

const syntheticSnapshot = {
	year: 2026,
	month: 10,
	totalAmount: 90000,
	completedCount: 3,
	settlementCount: 3,
	generatedAt: '2026-10-10T12:00:00',
	items: [
		round(1, '합성고', 'grade1_semester1_midterm', '가상 정상학생'),
		round(2, '합성고', 'accepted', '가상 합격자반학생'),
		{
			...round(3, '무료고', 'grade1_semester1_midterm', '가상 무료학생'),
			parentFreeForThreePlus: true,
			targets: [
				{ id: 31, studentName: '가상 무료학생', report: null },
				{ id: 32, studentName: '가상 무료학생', report: null },
				{ id: 33, studentName: '가상 무료학생', report: null }
			]
		}
	]
};

const validPlan = (suffix = 'a') => ({
	requestId: `request-${suffix}`,
	snapshotId: 17,
	snapshotDigest: `snapshot-${suffix}`,
	planDigest: `plan-${suffix}`,
	status: 'awaiting_confirmation',
	messageCount: 1,
	matchedRooms: [
		{ room: '합성고 가상 정상학생 생명클리닉', evidence: 'unique_exact', parentCharge: 30000 }
	],
	messagePreviews: [
		{
			room: '합성고 가상 정상학생 생명클리닉',
			text: '합성 서버 생성 안내 30,000원',
			parentCharge: 30000
		}
	],
	exclusionSummary: {
		acceptedStageStudents: 1,
		unknownStageStudents: 0,
		zeroParentChargeStudents: 1
	},
	excludedStudentCount: 2
});

type ParentSettlementMock = {
	studentKey: string;
	status: 'pending' | 'paid' | 'needs_review';
	amount: number;
	paidAmount: number;
	updatedAt: string | null;
	manualDeliveryConfirmed?: boolean;
	manualDeliveryConfirmedAt?: string | null;
};

async function openSettlement(
	page: Page,
	options: {
		plans?: ReturnType<typeof validPlan>[];
		confirmResponses?: Array<{ status: number; body: unknown }>;
		parentItems?: ParentSettlementMock[];
		parentItemsByMonth?: Record<number, ParentSettlementMock[]>;
		delayedSettlementMonth?: number;
		delayedParentMonth?: number;
		delayedParentPatchMs?: number;
		delayedConfirmMs?: number;
		delayMs?: number;
		twoStudents?: boolean;
	} = {}
) {
	const previewPosts: Array<{ url: string; body: unknown }> = [];
	const confirmPosts: Array<{ url: string; body: unknown }> = [];
	const parentGets: Array<{ url: string; method: string }> = [];
	const settlementGets: Array<{ url: string; method: string }> = [];
	const parentPatches: Array<{ url: string; method: string; body: unknown }> = [];
	const manualDeliveryPatches: Array<{ url: string; method: string; body: unknown }> = [];
	let parentItems = options.parentItems ?? [
		{
			studentKey: '1:가상 정상학생',
			status: 'pending',
			amount: 30000,
			paidAmount: 0,
			updatedAt: null,
			manualDeliveryConfirmed: false,
			manualDeliveryConfirmedAt: null
		}
	];
	let previewIndex = 0;
	let confirmIndex = 0;
	await page.route('**/auth/isjwt?key=mainauth', (route) =>
		route.fulfill({ json: { sub: '1', data: { id: '1', name: '테스트' }, exp: 9999999999 } })
	);
	await page.route('**/api/personal/**', async (route) => {
		const url = new URL(route.request().url());
		if (url.pathname.endsWith('/aura/settlements/parents') && route.request().method() === 'GET') {
			const month = Number(url.searchParams.get('month'));
			parentGets.push({ url: `${url.pathname}${url.search}`, method: route.request().method() });
			if (options.delayedParentMonth === month)
				await new Promise((resolve) => setTimeout(resolve, options.delayMs ?? 300));
			const items = options.parentItemsByMonth?.[month] ?? parentItems;
			return route.fulfill({ json: { items }, headers: { 'cache-control': 'no-store' } });
		}
		if (
			url.pathname.endsWith('/aura/settlements/parents/delivery') &&
			route.request().method() === 'PATCH'
		) {
			const body = route.request().postDataJSON() as {
				year: number;
				month: number;
				studentKey: string;
			};
			manualDeliveryPatches.push({ url: url.pathname, method: route.request().method(), body });
			const current = parentItems.find((item) => item.studentKey === body.studentKey);
			if (!current) return route.fulfill({ status: 404, json: { detail: 'unknown student' } });
			const updated = {
				...current,
				manualDeliveryConfirmed: true,
				manualDeliveryConfirmedAt: '2026-10-16T12:00:00'
			};
			parentItems = parentItems.map((item) =>
				item.studentKey === body.studentKey ? updated : item
			);
			return route.fulfill({ json: updated });
		}
		if (
			url.pathname.endsWith('/aura/settlements/parents') &&
			route.request().method() === 'PATCH'
		) {
			const body = route.request().postDataJSON() as {
				year: number;
				month: number;
				studentKey: string;
				paid: boolean;
			};
			parentPatches.push({ url: url.pathname, method: route.request().method(), body });
			if (options.delayedParentPatchMs)
				await new Promise((resolve) => setTimeout(resolve, options.delayedParentPatchMs));
			const current = parentItems.find((item) => item.studentKey === body.studentKey);
			if (!current) return route.fulfill({ status: 404, json: { detail: 'unknown student' } });
			const updated = {
				...current,
				status: body.paid ? ('paid' as const) : ('pending' as const),
				paidAmount: body.paid ? current.amount : 0,
				updatedAt: '2026-10-16T12:00:00'
			};
			parentItems = parentItems.map((item) =>
				item.studentKey === body.studentKey ? updated : item
			);
			return route.fulfill({ json: updated });
		}
		if (url.pathname.endsWith('/aura/settlements') && route.request().method() === 'GET') {
			const month = Number(url.searchParams.get('month'));
			settlementGets.push({
				url: `${url.pathname}${url.search}`,
				method: route.request().method()
			});
			if (options.delayedSettlementMonth === month)
				await new Promise((resolve) => setTimeout(resolve, options.delayMs ?? 300));
			return route.fulfill({
				json: {
					...syntheticSnapshot,
					items: options.twoStudents
						? [
								...syntheticSnapshot.items,
								round(4, '합성고', 'grade1_semester1_midterm', '가상 두번째학생')
							]
						: syntheticSnapshot.items,
					month,
					totalAmount: month === 11 ? 120000 : 90000
				},
				headers: { 'cache-control': 'no-store' }
			});
		}
		if (url.pathname.endsWith('/aura/settlement-requests/preview')) {
			previewPosts.push({ url: url.pathname, body: route.request().postDataJSON() });
			const plans = options.plans ?? [validPlan()];
			const plan = plans[Math.min(previewIndex, plans.length - 1)];
			previewIndex++;
			return route.fulfill({ json: plan, headers: { 'cache-control': 'no-store' } });
		}
		if (url.pathname.includes('/aura/settlement-requests/') && url.pathname.endsWith('/confirm')) {
			confirmPosts.push({ url: url.pathname, body: route.request().postDataJSON() });
			if (options.delayedConfirmMs)
				await new Promise((resolve) => setTimeout(resolve, options.delayedConfirmMs));
			const response = options.confirmResponses?.[confirmIndex++] ?? {
				status: 200,
				body: { requestId: 'request-a', status: 'succeeded', sentCount: 1 }
			};
			return route.fulfill({ status: response.status, json: response.body });
		}
		return route.fulfill({ json: [] });
	});
	await page.clock.install({ time: new Date('2026-10-15T12:00:00') });
	await page.goto('/personal-project/aura/settlements');
	await expect(page.getByRole('heading', { name: '학교별 월 정산' })).toBeVisible();
	return {
		previewPosts,
		confirmPosts,
		parentGets,
		parentPatches,
		manualDeliveryPatches,
		settlementGets
	};
}

test('개별 retryable은 사용자 클릭으로만 다시 시도하고 retryable plan도 확인한다', async ({
	page
}) => {
	await page.setViewportSize({ width: 390, height: 844 });
	const retryPlan = { ...validPlan('retry'), status: 'retryable' };
	const { previewPosts, confirmPosts } = await openSettlement(page, {
		plans: [validPlan(), retryPlan],
		confirmResponses: [
			{
				status: 200,
				body: { requestId: 'request-a', status: 'retryable', retryable: true, sentCount: 0 }
			},
			{ status: 200, body: { requestId: 'request-retry', status: 'succeeded', sentCount: 1 } }
		]
	});
	const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	const button = row.getByRole('button', { name: '학생별 정산 보내기' });
	await button.scrollIntoViewIfNeeded();
	const before = await page.evaluate(() => window.scrollY);
	await button.click();
	await expect(row.getByRole('status')).toHaveText('전송 전에 중단됐어요. 다시 누르면 재시도해요.');
	await expect(button).toBeEnabled();
	expect(await page.evaluate(() => window.scrollY)).toBe(before);
	expect(confirmPosts).toHaveLength(1);
	await button.click();
	await expect(row.getByRole('status')).toHaveText('전송 완료');
	await expect(button).toBeDisabled();
	expect(previewPosts).toHaveLength(2);
	expect(confirmPosts).toHaveLength(2);
	await expect(page.getByRole('dialog')).toHaveCount(0);
});

for (const firstStatus of ['manual_check', 'succeeded'] as const) {
	test(`${firstStatus} 대상은 차단하고 다른 대상은 독립적으로 보낸다`, async ({ page }) => {
		const { previewPosts, confirmPosts } = await openSettlement(page, {
			twoStudents: true,
			confirmResponses: [
				{
					status: 200,
					body: {
						requestId: 'request-a',
						status: firstStatus,
						sentCount: firstStatus === 'succeeded' ? 1 : 0
					}
				},
				{ status: 200, body: { requestId: 'request-a', status: 'succeeded', sentCount: 1 } }
			]
		});
		const first = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
		const second = page.locator('.message-row').filter({ hasText: '합성고 가상 두번째학생' });
		const firstButton = first.getByRole('button', { name: '학생별 정산 보내기' });
		const secondButton = second.getByRole('button', { name: '학생별 정산 보내기' });
		await firstButton.click();
		await expect(firstButton).toBeDisabled();
		await expect(page.getByRole('button', { name: '정산 요청', exact: true })).toBeEnabled();
		await expect(secondButton).toBeEnabled();
		expect(confirmPosts).toHaveLength(1);
		await secondButton.click();
		await expect(second.getByRole('status')).toHaveText('전송 완료');
		expect(confirmPosts).toHaveLength(2);
		expect(previewPosts).toHaveLength(2);
	});
}

test('일괄 일부 성공 후 retryable은 명시적 재클릭으로 이어가고 이미 보낸 건을 합산한다', async ({
	page
}) => {
	const base = validPlan();
	const plan = {
		...base,
		messageCount: 2,
		matchedRooms: [
			...base.matchedRooms,
			{ room: '합성 방 2', evidence: 'unique_exact', parentCharge: 30000 }
		],
		messagePreviews: [
			...base.messagePreviews,
			{ room: '합성 방 2', text: '합성 문구 2', parentCharge: 30000 }
		]
	};
	const { confirmPosts } = await openSettlement(page, {
		plans: [plan, { ...plan, status: 'retryable' }],
		confirmResponses: [
			{
				status: 200,
				body: { requestId: 'request-a', status: 'retryable', retryable: true, sentCount: 1 }
			},
			{
				status: 200,
				body: { requestId: 'request-a', status: 'succeeded', sentCount: 1, alreadySentCount: 1 }
			}
		]
	});
	const button = page.getByRole('button', { name: '정산 요청', exact: true });
	await button.click();
	await expect(button).toBeEnabled();
	await expect(page.getByRole('status').filter({ hasText: '전송 전에 중단됐어요.' })).toBeVisible();
	expect(confirmPosts).toHaveLength(1);
	await button.click();
	await expect(page.getByRole('status').filter({ hasText: '전송 완료' })).toBeVisible();
	await expect(button).toBeDisabled();
	expect(confirmPosts).toHaveLength(2);
});

for (const [status, message] of [
	['succeeded', '전송 완료'],
	['manual_check', '이전 전송 결과 확인이 필요해요.'],
	['sending', '이전 전송 결과 확인이 필요해요.']
] as const) {
	test(`preview ${status}는 확인 호출 없이 대상만 잠근다`, async ({ page }) => {
		const { confirmPosts } = await openSettlement(page, {
			twoStudents: true,
			plans: [{ ...validPlan(), status }]
		});
		const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
		const button = row.getByRole('button', { name: '학생별 정산 보내기' });
		await button.click();
		await expect(row.getByRole('status')).toHaveText(message);
		await expect(button).toBeDisabled();
		await expect(
			page
				.locator('.message-row')
				.filter({ hasText: '합성고 가상 두번째학생' })
				.getByRole('button', { name: '학생별 정산 보내기' })
		).toBeEnabled();
		expect(confirmPosts).toHaveLength(0);
	});
}

for (const [code, message, blocked] of [
	['manual_check_only', '이전 전송 결과 확인이 필요해요.', true],
	['recipient_unverified', '대화방을 확인하지 못해 전송하지 않았어요.', false]
] as const) {
	test(`API ${code}는 의미에 맞게 표시하고 재시도를 제어한다`, async ({ page }) => {
		const { confirmPosts } = await openSettlement(page, {
			twoStudents: true,
			confirmResponses: [{ status: 409, body: { detail: { code, message: 'synthetic' } } }]
		});
		const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
		const button = row.getByRole('button', { name: '학생별 정산 보내기' });
		await button.click();
		await expect(row.getByRole('status')).toHaveText(message);
		if (blocked) await expect(button).toBeDisabled();
		else await expect(button).toBeEnabled();
		await expect(
			page
				.locator('.message-row')
				.filter({ hasText: '합성고 가상 두번째학생' })
				.getByRole('button', { name: '학생별 정산 보내기' })
		).toBeEnabled();
		expect(confirmPosts).toHaveLength(1);
	});
}

test('합격자반과 무료 회차는 기존 수동 문구·복사 대상에서 제외하고 정산 총액은 보존한다', async ({
	page
}) => {
	await openSettlement(page);
	await expect(page.getByText('90,000원')).toBeVisible();
	await expect(page.getByText('합성고 가상 정상학생', { exact: true })).toBeVisible();
	await expect(page.getByText('합성고 가상 합격자반학생', { exact: true })).toHaveCount(0);
	await expect(page.getByText('무료고 가상 무료학생', { exact: true })).toHaveCount(0);
	await expect(page.getByRole('button', { name: '복사' })).toHaveCount(1);
});

test('정산 요청 버튼 한 번 클릭으로 검증된 미리보기 생성과 카카오 전송을 수행한다', async ({
	page
}) => {
	const { previewPosts, confirmPosts } = await openSettlement(page);
	await page.getByRole('button', { name: '정산 요청' }).click();
	await expect(page.getByRole('status')).toHaveText('전송 완료');
	await expect(page.getByRole('dialog')).toHaveCount(0);
	expect(previewPosts).toHaveLength(1);
	expect(previewPosts[0].url).toBe('/api/personal/aura/settlement-requests/preview');
	expect(previewPosts[0].body).toMatchObject({ year: 2026, month: 10, senderName: '김지후' });
	expect(typeof (previewPosts[0].body as { idempotencyKey?: unknown }).idempotencyKey).toBe(
		'string'
	);
	expect(confirmPosts).toHaveLength(1);
	expect(confirmPosts[0].url).toBe('/api/personal/aura/settlement-requests/request-a/confirm');
	expect(confirmPosts[0].body).toEqual({ planDigest: 'plan-a', senderName: '김지후' });
});

test('alreadySentCount가 양수일 때만 이미 발송되어 제외된 수를 표시한다', async ({ page }) => {
	const plan = validPlan('receipt');
	plan.messageCount = 3;
	plan.matchedRooms = [1, 2, 3].map((index) => ({
		room: `합성 방 ${index}`,
		evidence: 'unique_exact',
		parentCharge: 30000
	}));
	plan.messagePreviews = plan.matchedRooms.map((matched) => ({
		room: matched.room,
		text: '합성 요청 내용',
		parentCharge: matched.parentCharge
	}));
	const { confirmPosts } = await openSettlement(page, {
		plans: [plan],
		confirmResponses: [
			{
				status: 200,
				body: {
					requestId: 'request-duplicate',
					status: 'succeeded',
					sentCount: 1,
					alreadySentCount: 2
				}
			}
		]
	});
	await page.getByRole('button', { name: '정산 요청' }).click();
	await expect(page.getByRole('status')).toHaveText('전송 완료');
	expect(confirmPosts).toHaveLength(1);
});

test('snapshot_changed는 자동 재전송하지 않고, 사용자가 다시 누를 때만 새 요청을 보낸다', async ({
	page
}) => {
	const { previewPosts, confirmPosts } = await openSettlement(page, {
		plans: [validPlan('old'), validPlan('fresh')],
		confirmResponses: [
			{ status: 409, body: { detail: { code: 'snapshot_changed', message: 'snapshot changed' } } },
			{ status: 200, body: { requestId: 'request-fresh', status: 'succeeded', sentCount: 1 } }
		]
	});
	const sendButton = page.getByRole('button', { name: '정산 요청' });
	await sendButton.click();
	await expect(page.getByRole('status')).toHaveText('보내지 못했어요.');
	expect(confirmPosts).toHaveLength(1);
	expect(previewPosts).toHaveLength(1);
	await sendButton.click();
	await expect(page.getByRole('status')).toHaveText('전송 완료');
	expect(confirmPosts).toHaveLength(2);
	expect(previewPosts).toHaveLength(2);
	expect(confirmPosts.map((post) => post.url)).toEqual([
		'/api/personal/aura/settlement-requests/request-old/confirm',
		'/api/personal/aura/settlement-requests/request-fresh/confirm'
	]);
});

test('알 수 없는 stage는 확인 없이 바로 차단한다', async ({ page }) => {
	const unknown = validPlan('unknown');
	unknown.exclusionSummary.unknownStageStudents = 1;
	unknown.excludedStudentCount = 3;
	const { confirmPosts } = await openSettlement(page, { plans: [unknown] });
	await page.getByRole('button', { name: '정산 요청' }).click();
	await expect(page.getByRole('status')).toHaveText('보내지 못했어요.');
	expect(confirmPosts).toHaveLength(0);
});

test('manual_check 응답은 전송 불확실 상태로 고정하고 재시도하지 않는다', async ({ page }) => {
	const { confirmPosts } = await openSettlement(page, {
		confirmResponses: [
			{ status: 200, body: { requestId: 'request-a', status: 'manual_check', sentCount: 0 } }
		]
	});
	const sendButton = page.getByRole('button', { name: '정산 요청' });
	await sendButton.click();
	await expect(page.getByRole('status')).toHaveText('전송 결과를 확인할 수 없어요.');
	await expect(sendButton).toBeDisabled();
	expect(confirmPosts).toHaveLength(1);
});

test('중복 room·미검증 근거·0원 메시지는 확인 없이 즉시 차단한다', async ({ page }) => {
	const invalid = validPlan('invalid');
	invalid.messageCount = 2;
	invalid.matchedRooms = [
		{ ...invalid.matchedRooms[0], room: '합성고 같은 방', evidence: 'unique_exact' },
		{ ...invalid.matchedRooms[0], room: '합성고 같은 방', evidence: 'ambiguous' }
	];
	invalid.messagePreviews = [
		{ ...invalid.messagePreviews[0], room: '합성고 같은 방' },
		{ ...invalid.messagePreviews[0], room: '합성고 같은 방', parentCharge: 0 }
	];
	const { confirmPosts } = await openSettlement(page, { plans: [invalid] });
	await page.getByRole('button', { name: '정산 요청' }).click();
	await expect(page.getByRole('status')).toHaveText('보내지 못했어요.');
	expect(confirmPosts).toHaveLength(0);
});

test('모바일에서도 성공·실패 상태 전후 헤더와 스크롤 위치를 유지한다', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await openSettlement(page);
	const layout = (target: Page) =>
		target.evaluate(() => {
			const rect = (selector: string) => document.querySelector(selector)?.getBoundingClientRect();
			return {
				pageHeadHeight: rect('.page-head')?.height ?? 0,
				requestActionHeight: rect('.request-action')?.height ?? 0,
				generateButtonHeight: rect('.settlement-generate-button')?.height ?? 0,
				settlementTop: rect('.settlement-top')?.top ?? 0,
				scrollY: window.scrollY
			};
		});
	const expectStableLayout = (
		before: Awaited<ReturnType<typeof layout>>,
		after: Awaited<ReturnType<typeof layout>>
	) => {
		expect(Math.abs(after.pageHeadHeight - before.pageHeadHeight)).toBeLessThanOrEqual(1);
		expect(Math.abs(after.requestActionHeight - before.requestActionHeight)).toBeLessThanOrEqual(1);
		expect(Math.abs(after.generateButtonHeight - before.generateButtonHeight)).toBeLessThanOrEqual(
			1
		);
		expect(Math.abs(after.settlementTop - before.settlementTop)).toBeLessThanOrEqual(1);
		expect(after.scrollY).toBe(before.scrollY);
	};
	await page.evaluate(() => window.scrollTo(0, 32));
	const beforeSuccess = await layout(page);
	expect(beforeSuccess.scrollY).toBeGreaterThan(0);
	await page.getByRole('button', { name: '정산 요청' }).click();
	await expect(page.getByRole('status')).toHaveText('전송 완료');
	expectStableLayout(beforeSuccess, await layout(page));
	expect(
		await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
	).toBeTruthy();
	await page.screenshot({
		path: 'test-results/aura-settlement-request-mobile.png',
		fullPage: true
	});

	const failurePage = await page.context().newPage();
	await failurePage.setViewportSize({ width: 390, height: 844 });
	await openSettlement(failurePage, {
		confirmResponses: [{ status: 500, body: { detail: 'synthetic failure' } }]
	});
	await failurePage.evaluate(() => window.scrollTo(0, 32));
	const beforeFailure = await layout(failurePage);
	await failurePage.getByRole('button', { name: '정산 요청' }).click();
	await expect(failurePage.getByRole('status')).toHaveText('전송 결과를 확인할 수 없어요.');
	expectStableLayout(beforeFailure, await layout(failurePage));
	await failurePage.close();
});

test('학생별 보내기는 정확한 studentKey로 요청하고 한 번 클릭으로 전송한다', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	const { previewPosts, confirmPosts, parentGets } = await openSettlement(page);
	const mobileLayout = await page.evaluate(() => {
		const rect = (selector: string) => document.querySelector(selector)?.getBoundingClientRect();
		const head = rect('.page-head');
		const controls = rect('.export-controls');
		const name = rect('.export-controls > label');
		const request = rect('.settlement-request-button');
		const generate = rect('.settlement-generate-button');
		const exportButton = rect('.settlement-export-button');
		return {
			headHeight: head?.height ?? 0,
			controlsWidth: controls?.width ?? 0,
			nameWidth: name?.width ?? 0,
			requestTop: request?.top ?? 0,
			requestLeft: request?.left ?? 0,
			generateTop: generate?.top ?? 0,
			generateLeft: generate?.left ?? 0,
			exportWidth: exportButton?.width ?? 0
		};
	});
	expect(mobileLayout.headHeight).toBeLessThan(288);
	expect(mobileLayout.nameWidth).toBeGreaterThanOrEqual(mobileLayout.controlsWidth - 2);
	expect(Math.abs(mobileLayout.requestTop - mobileLayout.generateTop)).toBeLessThanOrEqual(2);
	expect(mobileLayout.generateLeft).toBeGreaterThan(mobileLayout.requestLeft);
	expect(mobileLayout.exportWidth).toBeGreaterThanOrEqual(mobileLayout.controlsWidth - 2);
	await page.setViewportSize({ width: 1280, height: 844 });
	await expect(page.locator('.export-controls')).toHaveCSS('display', 'flex');
	await expect(page.locator('.request-action')).toHaveCSS('display', 'contents');
	await page.setViewportSize({ width: 390, height: 844 });
	const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	const sendButton = row.getByRole('button', { name: '학생별 정산 보내기' });
	await expect(sendButton).toBeVisible();
	await sendButton.scrollIntoViewIfNeeded();
	const scrollBeforeSend = await page.evaluate(() => window.scrollY);
	await sendButton.click();
	await expect(page.getByRole('status')).toHaveText('전송 완료');
	await expect(row.getByRole('status')).toHaveText('전송 완료');
	const scrollAfterSend = await page.evaluate(() => window.scrollY);
	expect(Math.abs(scrollAfterSend - scrollBeforeSend)).toBeLessThanOrEqual(2);
	await expect(page.getByRole('dialog')).toHaveCount(0);
	expect(previewPosts).toHaveLength(1);
	expect(previewPosts[0].body).toMatchObject({ studentKey: '1:가상 정상학생' });
	expect(confirmPosts).toHaveLength(1);
	expect(parentGets).toHaveLength(1);
	expect(parentGets[0].method).toBe('GET');
	expect(
		await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
	).toBeTruthy();
	await page.screenshot({
		path: 'test-results/aura-settlement-individual-mobile.png',
		fullPage: true
	});
});

test('학생별 발송 진행은 스피너로 알리고 성공한 학생 카드만 옅은 초록으로 표시한다', async ({
	page
}) => {
	const { confirmPosts } = await openSettlement(page, { delayedConfirmMs: 350 });
	const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	const button = row.locator('.send-student-button');
	const clickPromise = button.click();
	await expect(button).toHaveAttribute('aria-busy', 'true');
	await expect(button.getByTestId('settlement-send-spinner')).toBeVisible();
	await expect(button).toContainText('전송 중');
	await expect(row).not.toHaveClass(/sent-success/);
	await clickPromise;
	await expect(row.getByRole('status')).toHaveText('전송 완료');
	await expect(row).toHaveClass(/sent-success/);
	await expect(row).toHaveCSS('background-color', 'rgb(237, 246, 239)');
	await expect(button).toBeDisabled();
	expect(confirmPosts).toHaveLength(1);
});

test('전송 화면은 입금 상태를 표시하거나 수정하지 않고 수동 전송 확인만 읽는다', async ({
	page
}) => {
	const { parentGets, parentPatches } = await openSettlement(page);
	const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	await expect(row).toBeVisible();
	await expect(row).not.toContainText('정산 완료 처리');
	await expect(row).not.toContainText('입금 대기');
	await expect(row.getByRole('button', { name: '완료 취소' })).toHaveCount(0);
	expect(parentGets).toHaveLength(1);
	expect(parentGets[0]).toMatchObject({
		url: '/api/personal/aura/settlements/parents?year=2026&month=10',
		method: 'GET'
	});
	expect(parentPatches).toHaveLength(0);
});

test('수동 전송 완료 확인은 전송 상태만 기록하고 입금 상태와 카카오 발송은 건드리지 않는다', async ({
	page
}) => {
	const { previewPosts, confirmPosts, parentGets, parentPatches, manualDeliveryPatches } =
		await openSettlement(page);
	const row = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	const button = row.getByRole('button', { name: '전송 완료로 기록' });
	await expect(button).toBeVisible();
	await button.click();
	await expect(row.getByRole('status')).toHaveText('수동 확인 완료');
	expect(manualDeliveryPatches).toEqual([
		{
			url: '/api/personal/aura/settlements/parents/delivery',
			method: 'PATCH',
			body: { year: 2026, month: 10, studentKey: '1:가상 정상학생' }
		}
	]);
	expect(parentGets).toHaveLength(1);
	expect(parentPatches).toHaveLength(0);
	expect(previewPosts).toHaveLength(0);
	expect(confirmPosts).toHaveLength(0);
	await page.reload();
	const reloadedRow = page.locator('.message-row').filter({ hasText: '합성고 가상 정상학생' });
	await expect(reloadedRow.getByRole('status')).toHaveText('수동 확인 완료');
	await expect(reloadedRow.getByRole('button', { name: '전송 완료로 기록' })).toHaveCount(0);
	expect(manualDeliveryPatches).toHaveLength(1);
	expect(parentPatches).toHaveLength(0);
});

test('늦은 이전 월 정산 응답은 현재 월 금액을 덮지 않는다', async ({ page }) => {
	const { settlementGets } = await openSettlement(page, { delayedSettlementMonth: 10 });
	await expect.poll(() => settlementGets.length).toBe(1);
	await page.getByRole('button', { name: '다음 달' }).click();
	await expect(page.locator('.month-picker')).toContainText('2026년 11월');
	await expect(page.locator('.summary')).toContainText('120,000원');
	await expect.poll(() => settlementGets.length).toBe(2);
	await page.waitForTimeout(350);
	await expect(page.locator('.summary')).toContainText('120,000원');
});
