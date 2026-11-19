import { expect, test } from '@playwright/test';

// The frontend and Aura API are real processes. Only the login identity is synthetic.
test('legacy 회차 UI→실제 API→격리 SQLite/PDF 계약', async ({ page, request }) => {
	const backend = process.env.AURA_TEST_API_URL;
	if (!backend) throw new Error('Run with the isolated aura integration runner');
	const seedResponse = await request.post(`${backend}/__test/seed`);
	expect(seedResponse.status()).toBe(200);
	const { school, other } = await seedResponse.json();
	const api = `${backend}/api/personal/aura`;
	const list = async () => {
		const response = await request.get(`${api}/rounds`);
		expect(response.status()).toBe(200);
		return response.json();
	};
	const initial = await list();
	expect(initial).toHaveLength(2);
	const original = initial[0];
	expect(original.startTime).toMatch(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/); // legacy naive
	expect(initial[1].startTime).toMatch(/\+09:00$/); // modern aware control
	const target = original.targets[0].id;
	const getReport = async () => {
		const response = await request.get(`${api}/targets/${target}/report`);
		expect(response.status()).toBe(200);
		return response.json();
	};
	const report = await getReport();
	expect(report.contentJson.blocks[0].id).toBe('legacy-template');
	const png = await page.screenshot();
	const upload = await request.post(
		`${api}/targets/${target}/attachments?kind=blank_test&filename=synthetic.png`,
		{
			data: png,
			headers: { 'content-type': 'image/png' }
		}
	);
	expect(upload.status()).toBe(201);
	const attachment = (await upload.json()).id;
	const pdf = async () => {
		const response = await request.get(`${api}/targets/${target}/report.pdf`);
		expect(response.status()).toBe(200);
		const bytes = await response.body();
		expect(bytes.subarray(0, 4).toString()).toBe('%PDF');
		return bytes;
	};
	await pdf();

	const patches: Record<string, unknown>[] = [];
	const patchStatuses: number[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PATCH' && /\/api\/personal\/aura\/rounds\/\d+$/.test(r.url()))
			patches.push(r.postDataJSON());
	});
	page.on('response', (r) => {
		if (r.request().method() === 'PATCH' && /\/api\/personal\/aura\/rounds\/\d+$/.test(r.url()))
			patchStatuses.push(r.status());
	});
	await page.goto('/personal-project/aura');
	await expect(page.locator('.week-scheduler .slot.busy').first()).toBeVisible();
	await page.locator('.week-scheduler .slot.busy').first().click();
	await expect(page.locator('#round-stage')).toHaveValue('grade1_semester1');
	await page.locator('#round-start').fill('2026-11-03T17:00');
	await page.locator('#round-end').fill('2026-11-03T18:00');
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(() => patches.length).toBe(1);
	await expect.poll(() => patchStatuses).toEqual([200]);
	for (const field of ['progress_stage', 'school_id', 'round_number', 'round_numbers'])
		expect(patches[0]).not.toHaveProperty(field);
	await expect
		.poll(async () => {
			const current = (await list()).find((round: { id: number }) => round.id === original.id);
			return new Date(current.startTime).toISOString();
		})
		.toBe('2026-11-03T08:00:00.000Z');
	const updated = (await list()).find((round: { id: number }) => round.id === original.id);
	expect(updated.progressStage).toBe('grade1_semester1');
	expect((await getReport()).id).toBe(report.id);

	// Direct HTTP PATCH complements the UI test: the UI deliberately sends stage on a school move.
	const moved = await request.patch(`${api}/rounds/${original.id}`, { data: { school_id: other } });
	expect(moved.status()).toBe(200);
	expect((await moved.json()).progressStage).toBe('grade1_semester1');
	expect((await getReport()).id).toBe(report.id);

	await page.goto('/personal-project/aura', { waitUntil: 'domcontentloaded' });
	await page.getByRole('button', { name: '＋ 새 회차' }).click();
	await expect(page.locator('#round-stage')).toHaveValue('grade1_semester1_midterm');
	await page.locator('#round-school').selectOption(String(school));
	await expect(page.locator('#round-number')).toHaveValue('3');
	await page.locator('#round-students').fill('합성 중간학생');
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(async () => (await list()).length).toBe(3);
	const midterm = (await list()).find(
		(round: { progressStage: string }) => round.progressStage === 'grade1_semester1_midterm'
	);
	expect(midterm.roundNumber).toBe(3);
	const midtermReport = await request.get(`${api}/targets/${midterm.targets[0].id}/report`);
	expect(midtermReport.status()).toBe(200);
	expect((await midtermReport.json()).contentJson.blocks[0].id).toBe('legacy-template');
	await page.goto('/personal-project/aura', { waitUntil: 'domcontentloaded' });
	await page.getByRole('button', { name: '＋ 새 회차' }).click();
	await page.locator('#round-stage').selectOption('grade1_semester1_final');
	await expect(page.locator('#round-number')).toHaveValue('1');
	await page.locator('#round-students').fill('합성 기말학생');
	await page.locator('#round-start').fill('2026-11-04T18:00');
	await page.locator('#round-end').fill('2026-11-04T19:00');
	await page.locator('.modal .modal-actions .primary-button').click();
	await expect.poll(async () => (await list()).length).toBe(4);
	const final = (await list()).find(
		(round: { progressStage: string }) => round.progressStage === 'grade1_semester1_final'
	);
	expect(final.roundNumber).toBe(1);
	const finalReport = await request.get(`${api}/targets/${final.targets[0].id}/report`);
	expect(finalReport.status()).toBe(200);
	expect((await finalReport.json()).contentJson.blocks[0]?.id).not.toBe('legacy-template');

	const submitted = await request.post(`${api}/target-reports/${report.id}/submit`);
	expect(submitted.status()).toBe(200);
	const attached = await request.get(`${api}/targets/${target}/attachments`);
	expect((await attached.json()).map((item: { id: number }) => item.id)).toContain(attachment);
	const image = await request.get(`${api}/report-attachments/${attachment}`);
	expect(image.status()).toBe(200);
	expect(await image.body()).toEqual(png);
	await pdf();
	expect((await getReport()).id).toBe(report.id);

 await test.step('13시간 입력은 오전·오후와 길이를 설명하고 수정 후 저장한다',async()=>{
 await page.goto('/personal-project/aura');await expect(page.locator('.slot.busy').first()).toBeVisible();
 await page.locator('.slot.busy').first().click();
 await page.locator('#round-start').fill('2026-11-03T10:30');await page.locator('#round-end').fill('2026-11-03T23:30');
 await expect(page.locator('form.modal [role="status"]')).toContainText('총 13시간');
 await page.locator('form.modal .modal-actions .primary-button').click();
 await expect(page.locator('form.modal [role="alert"]')).toContainText('13시간');
 await expect(page.locator('form.modal [role="alert"]')).toContainText('오후 11:30');
 await expect(page.locator('#round-end')).toHaveValue('2026-11-03T23:30');
 await page.screenshot({path:'test-results/aura-time-validation-clear.png',fullPage:true});
 await page.locator('#round-end').fill('2026-11-03T11:30');
 await expect(page.locator('form.modal [role="status"]')).toContainText('총 1시간');
 await page.locator('form.modal .modal-actions .primary-button').click();
 await expect(page.locator('form.modal')).toHaveCount(0);
 });
});
