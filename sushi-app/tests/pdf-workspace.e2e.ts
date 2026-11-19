import { test, expect, type Page } from '@playwright/test';
import { PDFDocument } from 'pdf-lib';
async function setup(page: Page, initial: unknown = null) {
	const pdf = await PDFDocument.create();
	for (let i = 0; i < 864; i++) {
		const p = pdf.addPage(i === 863 ? [800, 400] : [595, 842]);
		if (i === 863) p.setRotation({ type: 'degrees', angle: 90 } as any);
	}
	const bytes = Buffer.from(await pdf.save());
	let data: any = initial,
		revision = 0;
	const errors: string[] = [];
	page.on('pageerror', (e) => errors.push(e.message));
	await page.route('**/auth/isjwt?key=mainauth', (r) =>
		r.fulfill({
			json: { sub: 'margin-test', data: { id: 'margin-test', name: 'Test' }, exp: 9999999999 }
		})
	);
	await page.route('**/api/personal/**', async (r) => {
		const path = new URL(r.request().url()).pathname;
		if (path.endsWith('/drive/status'))
			return r.fulfill({
				json: {
					quotaBytes: 524288000,
					usedBytes: bytes.length,
					transferDays: 15,
					googleAccounts: []
				}
			});
		if (path.endsWith('/drive/items'))
			return r.fulfill({
				json: [
					{
						id: 'margin-fixture',
						bucket: 'transfer',
						provider: 'local',
						accountId: null,
						name: '전공책.pdf',
						mimeType: 'application/pdf',
						byteSize: bytes.length,
						createdAt: '2026-11-12T00:00:00Z',
						expiresAt: null
					}
				]
			});
		if (path.endsWith('/content'))
			return r.fulfill({ contentType: 'application/pdf', body: bytes });
		if (path.includes('/documents/')) {
			if (r.request().method() === 'PUT') {
				const body = r.request().postDataJSON();
				data = body.data;
				revision++;
			}
			return r.fulfill({ json: { data, revision } });
		}
		return r.fulfill({ json: [] });
	});
	await page.goto('/personal-project/calendar/drive');
	await page.getByRole('button', { name: /전공책.pdf/ }).click();
	await expect(page.getByLabel('PDF 페이지', { exact: true })).toBeVisible();
	await expect(page.locator('.paper svg')).toBeVisible();
	await expect(page.locator('.paper canvas').first()).toBeVisible();
	await expect(page.getByText('페이지 불러오는 중…', { exact: true })).toHaveCount(0);
	await expect
		.poll(() =>
			page
				.locator('.paper canvas')
				.first()
				.evaluate((c: HTMLCanvasElement) => c.width)
		)
		.toBeGreaterThan(0);
	return { saved: () => data, errors };
}
async function draw(page: Page) {
	const area = page.getByLabel('PDF 필기 영역');
	await area.scrollIntoViewIfNeeded();
	const box = (await area.boundingBox())!;
	const x = box.x + 80,
		y = box.y + 80;
	await page.mouse.move(x, y);
	await page.mouse.down();
	for (let i = 1; i < 40; i++) await page.mouse.move(x + i * 3, y + Math.sin(i / 5) * 15);
	await page.mouse.up();
	return { x, y };
}
test('864-page book, vector ink, lasso duplicate, inline text, persistence and export', async ({
	page
}) => {
	const state = await setup(page);
	const drawn = await draw(page);
	await expect(page.locator('.paper svg > path')).toHaveCount(1);
	await page.getByRole('button', { name: '올가미', exact: true }).click();
	await page.mouse.move(drawn.x - 15, drawn.y - 30);
	await page.mouse.down();
	for (const [x, y] of [
		[drawn.x + 140, drawn.y - 30],
		[drawn.x + 140, drawn.y + 35],
		[drawn.x - 15, drawn.y + 35],
		[drawn.x - 15, drawn.y - 30]
	])
		await page.mouse.move(x, y);
	await page.mouse.up();
	await expect(page.getByText('1개 선택', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: '복제', exact: true }).click();
	await expect(page.locator('.paper svg > path')).toHaveCount(2);
	await page.getByRole('button', { name: '텍스트', exact: true }).click();
	const area = page.getByLabel('PDF 필기 영역');
	const box = (await area.boundingBox())!;
	await page.mouse.click(box.x + 80, box.y + 160);
	await page.getByLabel('텍스트 주석 내용').fill('벡터 필기 테스트');
	await page.getByRole('button', { name: '완료', exact: true }).click();
	await page
		.locator('.margin-workspace header')
		.getByRole('button', { name: '저장', exact: true })
		.click();
	await expect.poll(() => state.saved()?.pages[0].strokes.length).toBe(2);
	expect(state.saved().pages[0].notes[0].text).toBe('벡터 필기 테스트');
	expect(state.saved().pages[863].sourceReady).toBe(false);
	await page.getByLabel('PDF 페이지', { exact: true }).selectOption({ value: '863' });

	await expect
		.poll(() => page.locator('.paper').evaluate((el) => el.clientWidth / el.clientHeight))
		.toBeCloseTo(.5,2);
	await page.getByLabel('PDF 페이지', { exact: true }).selectOption('0');
	await expect(page.locator('.paper svg > path')).toHaveCount(2);
	const downloadPromise = page.waitForEvent('download');
	await page.getByRole('button', { name: '내보내기', exact: true }).click();
	const download = await downloadPromise;
	expect(download.suggestedFilename()).toBe('전공책-필기.pdf');
	await page.reload();
	await page.getByRole('button', { name: /전공책.pdf/ }).click();
	await expect(page.locator('.paper svg > path')).toHaveCount(2);
	expect(state.errors).toEqual([]);
	await page.screenshot({ path: '/tmp/margin-desktop.png', fullPage: true });
});
test('mobile keeps tools reachable and has no document-level overflow', async ({ page }) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await setup(page);
	await expect(page.getByRole('button', { name: '올가미', exact: true })).toBeVisible();
	expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
	await page.screenshot({ path: '/tmp/margin-mobile.png', fullPage: true });
});

test('existing 1500 strokes stay untouched while the new stroke is being drawn', async ({
	page
}) => {
	const strokes = Array.from({ length: 1500 }, (_, i) => ({
		id: `stress-${i}`,
		kind: 'pen',
		geometry: 'outline',
		width: 1,
		color: '#242424',
		points: Array.from({ length: 20 }, (_, j) => ({
			x: 20 + (i % 40) * 12 + j / 5,
			y: 20 + Math.floor(i / 40) * 12 + Math.sin(j),
			pressure: 0.5
		}))
	}));
	await setup(page, {
		version: 1,
		pages: [{ id: 'stress', source: 0, rotation: 0, width: 595, height: 842, strokes, notes: [] }]
	});
	await page.evaluate(() => {
		(window as any).inkMutations = 0;
		const observer = new MutationObserver((list) => {
			(window as any).inkMutations += list.filter((m) => m.type === 'attributes').length;
		});
		observer.observe(document.querySelector('.paper svg')!, {
			subtree: true,
			attributes: true,
			attributeFilter: ['d', 'stroke', 'fill']
		});
	});
	const box = (await page.getByLabel('PDF 필기 영역').boundingBox())!;
	await page.mouse.move(box.x + 60, box.y + 60);
	await page.mouse.down();
	for (let i = 0; i < 60; i++)
		await page.mouse.move(box.x + 60 + i * 3, box.y + 65 + Math.sin(i / 5) * 15);
	expect(await page.evaluate(() => (window as any).inkMutations)).toBe(0);
	await page.mouse.up();
	await expect(page.locator('.paper svg > path')).toHaveCount(1501);
});

test('Surface barrel selects, inverted eraser cannot scroll, text is clickable', async ({
	page
}) => {
	await setup(page);
	const { x, y } = await draw(page);
	await expect(page.locator('.paper svg > path')).toHaveCount(1);
	const cdp = await page.context().newCDPSession(page);
	const pen = async (type: 'mousePressed'|'mouseReleased'|'mouseMoved', x: number, y: number, buttons: number, button: 'left'|'right'|'none' = 'right') =>
		cdp.send('Input.dispatchMouseEvent', {
			type,
			x,
			y,
			pointerType: 'pen',
			button,
			buttons,
			force: type === 'mouseReleased' ? 0 : 0.5
		});
	await pen('mousePressed', x - 10, y - 30, 2);
	for (const [px, py] of [
		[x + 140, y - 30],
		[x + 140, y + 35],
		[x - 10, y + 35],
		[x - 10, y - 30]
	])
		await pen('mouseMoved', px, py, 2, 'none');
	await pen('mouseReleased', x - 10, y - 30, 0);
	await expect(page.getByText('1개 선택', { exact: true })).toBeVisible();
	const initial = await page.locator('.viewport').evaluate((el) => el.scrollTop);
	await page.getByRole('button',{name:'지우개',exact:true}).click();
 const er=(await page.getByLabel('PDF 필기 영역').boundingBox())!;const ex=er.x+80,ey=er.y+80;
 await pen('mousePressed',ex,ey,1,'left');
	await page.mouse.wheel(0, 300);
	expect(await page.locator('.viewport').evaluate((el) => el.scrollTop)).toBe(initial);
	await pen('mouseReleased',ex,ey,0,'left');
	await expect(page.locator('.paper svg > path')).toHaveCount(0);
	await page.getByRole('button', { name: '텍스트', exact: true }).click();
	const b = (await page.getByLabel('PDF 필기 영역').boundingBox())!;
	await page.mouse.click(b.x + 60, b.y + 150);
	await page.getByLabel('텍스트 주석 내용').fill('클릭 편집');
	await page.getByRole('button', { name: '완료', exact: true }).click();
	await page.getByRole('button', { name: '펜', exact: true }).click();
	await page.locator('text[data-note-id]').click();
	await expect(page.getByLabel('텍스트 주석 내용')).toHaveValue('클릭 편집');
	expect(
		await page.locator('.margin-workspace').evaluate((el) => getComputedStyle(el).position)
	).toBe('relative');
	expect(
		await page.getByLabel('PDF 필기 영역').evaluate((el) => getComputedStyle(el).touchAction)
	).toBe('none');
});
