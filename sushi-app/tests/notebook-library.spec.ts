import { test, expect } from '@playwright/test';
const base = 'http://127.0.0.1:5192/';
test('notebooks, sections and pages retain titles and independent notes after reload', async ({
	page
}) => {
	await page.goto(base);
	await expect(page.locator('.paper')).toBeVisible();
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).fill('역학 첫 강의');
	await page.getByRole('button', { name: '섹션 만들기', exact: false }).click();
	await page.getByRole('textbox', { name: '이름', exact: true }).fill('전공 과제');
	await page.getByRole('button', { name: '만들기', exact: true }).click();
	await page.locator('.library-add-page button').first().click();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'제목 없는 페이지'
	);
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).fill('과제 1');
	await page.getByRole('button', { name: '빠른 메모', exact: true }).click();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'역학 첫 강의'
	);
	await page.getByRole('button', { name: '전공 과제', exact: true }).click();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue('과제 1');
	await page.reload();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue('과제 1');
});
test('paper options persist defaults and page deletion can be undone from trash', async ({
	page
}) => {
	await page.goto(base);
	await page.locator('.paper').waitFor();
	await page.getByRole('button', { name: '새 페이지 용지 선택', exact: true }).click();
	await page.getByRole('button', { name: '백지', exact: true }).click();
	await page.getByRole('button', { name: '검은 종이', exact: true }).click();
	await page.getByRole('checkbox', { name: '새 페이지 기본값으로 저장' }).check();
	await page.locator('.paper-options .apply-paper').click();
	await expect
		.poll(() => page.locator('.paper').evaluate((e) => getComputedStyle(e).backgroundColor))
		.toBe('rgb(37, 39, 43)');
	await expect(page.locator('.ruled-paper')).toHaveCount(0);
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).fill('밤 필기');
	await page.getByRole('button', { name: 'NETAQ 홈으로', exact: false }).count();
	await page.locator('.library-add-page button').first().click();
	await expect
		.poll(() => page.locator('.paper').evaluate((e) => getComputedStyle(e).backgroundColor))
		.toBe('rgb(37, 39, 43)');
	await page.getByRole('button', { name: '밤 필기 페이지 삭제', exact: true }).click();
	await page.getByRole('button', { name: '휴지통', exact: true }).click();
	await page.locator('.page-name').filter({ hasText: '밤 필기' }).click();
	await page.getByRole('button', { name: '휴지통', exact: true }).click();
	await expect(page.locator('.page-name').filter({ hasText: '밤 필기' })).toHaveCount(1);
});
test('mobile navigation opens as a dismissible sheet and returns to the writing surface', async ({
	page
}) => {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(base);
	await page.locator('.paper').waitFor();
	await expect(page.locator('.notebook-navigation')).toBeHidden();
	await page.getByRole('button', { name: '노트 목록', exact: true }).click();
	await expect(page.locator('.notebook-navigation')).toBeVisible();
	await page.getByRole('button', { name: '필기로 돌아가기', exact: true }).click();
	await expect(page.locator('.notebook-navigation')).toBeHidden();
	await expect(page.locator('.main-tools')).toBeVisible();
	await page.screenshot({ path: '/tmp/notebook-library-mobile.png' });
});
async function seedObjects(page: any) {
	await page.goto(base + '?workspace=1');
	await page.locator('.paper').waitFor();
	await page.evaluate(async () => {
		const db = await new Promise<IDBDatabase>((resolve, reject) => {
			const r = indexedDB.open('netaq-notes', 1);
			r.onsuccess = () => resolve(r.result);
			r.onerror = reject;
		});
		await new Promise<void>((resolve, reject) => {
			const tx = db.transaction('workspace', 'readwrite');
			tx.objectStore('workspace').put(
				{
					title: '변형 확인',
					pages: [
						{
							id: 'p',
							source: null,
							w: 794,
							h: 1123,
							paper: { pattern: 'blank', color: 'white' },
							items: [
								{
									id: 's',
									kind: 'stroke',
									points: [
										{ x: 100, y: 100 },
										{ x: 180, y: 140 }
									],
									width: 2,
									color: '#242529',
									uniform: true
								},
								{
									id: 't',
									kind: 'text',
									x: 200,
									y: 200,
									w: 180,
									h: 60,
									html: '<p><span style="font-size:16px">텍스트 보존</span></p>'
								},
								{
									id: 'i',
									kind: 'image',
									x: 320,
									y: 300,
									w: 80,
									h: 80,
									src: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jTQAAAABJRU5ErkJggg=='
								}
							]
						}
					],
					pageIndex: 0
				},
				'current'
			);
			tx.oncomplete = () => resolve();
			tx.onerror = () => reject(tx.error);
		});
		db.close();
	});
	await page.reload();
	await page.locator('.image-object').waitFor();
}
for (const pointer of ['pen', 'touch'])
	test(`lasso selection moves and scales ink images and rich text with ${pointer}`, async ({
		page
	}) => {
		await seedObjects(page);
		await page.getByRole('button', { name: '선택', exact: true }).click();
		await page.getByRole('button', { name: '페이지 전체 선택', exact: true }).click();
		const cdp = await page.context().newCDPSession(page);
		if (pointer === 'touch')
			await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
		async function drag(x: number, y: number, dx: number, dy: number) {
			if (pointer === 'touch') {
				await cdp.send('Input.dispatchTouchEvent', {
					type: 'touchStart',
					touchPoints: [{ x, y, id: 1 }]
				});
				for (let i = 1; i <= 5; i++)
					await cdp.send('Input.dispatchTouchEvent', {
						type: 'touchMove',
						touchPoints: [{ x: x + (dx * i) / 5, y: y + (dy * i) / 5, id: 1 }]
					});
				await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
			} else {
				await cdp.send('Input.dispatchMouseEvent', {
					type: 'mousePressed',
					x,
					y,
					button: 'left',
					buttons: 1,
					pointerType: 'pen',
					force: 0.5
				});
				for (let i = 1; i <= 5; i++)
					await cdp.send('Input.dispatchMouseEvent', {
						type: 'mouseMoved',
						x: x + (dx * i) / 5,
						y: y + (dy * i) / 5,
						button: 'none',
						buttons: 1,
						pointerType: 'pen',
						force: 0.5
					});
				await cdp.send('Input.dispatchMouseEvent', {
					type: 'mouseReleased',
					x: x + dx,
					y: y + dy,
					button: 'left',
					buttons: 0,
					pointerType: 'pen',
					force: 0
				});
			}
		}
		const selection = await page
			.getByRole('button', { name: '선택 영역 이동', exact: true })
			.boundingBox();
		const before = await page.locator('.viewport').evaluate((e) => e.scrollTop);
		await drag(selection!.x + selection!.width / 2, selection!.y + selection!.height / 2, 32, 20);
		expect(
			await page.locator('.text-object').evaluate((e) => parseFloat((e as HTMLElement).style.left))
		).toBeGreaterThan(210);
		expect(await page.locator('.viewport').evaluate((e) => e.scrollTop)).toBe(before);
		const handle = await page
			.getByRole('button', { name: '선택 영역 크기 조절', exact: true })
			.last()
			.boundingBox();
		await drag(handle!.x + handle!.width / 2, handle!.y + handle!.height / 2, 45, 45);
		expect(
			await page
				.locator('.image-object')
				.evaluate((e) => parseFloat((e as HTMLElement).style.width))
		).toBeGreaterThan(85);
		expect(
			await page.locator('.text-content').evaluate((e) => parseFloat((e as HTMLElement).style.zoom))
		).toBeGreaterThan(1);
		await expect(page.locator('.text-object')).toContainText('텍스트 보존');
	});
test('text tool can move its own box using the move handle without lasso', async ({ page }) => {
	await seedObjects(page);
	await page.getByRole('button', { name: '텍스트', exact: true }).click();
	await page.getByRole('button', { name: '텍스트박스 편집', exact: true }).click();
	const h = page.getByRole('button', { name: '텍스트박스 이동', exact: true });
	await expect(h).toBeVisible();
	const r = await h.boundingBox();
	await page.mouse.move(r!.x + 10, r!.y + 10);
	await page.mouse.down();
	await page.mouse.move(r!.x + 55, r!.y + 40, { steps: 6 });
	await page.mouse.up();
	expect(
		await page.locator('.text-object').evaluate((e) => parseFloat((e as HTMLElement).style.left))
	).toBeGreaterThan(220);
	await expect(page.locator('.paper [contenteditable=true]')).toContainText('텍스트 보존');
});
test('Android pen erases only while the barrel is held and returns to the previous pen', async ({
	page
}) => {
	await page.addInitScript(() =>
		Object.defineProperty(navigator, 'userAgent', {
			get: () => 'Mozilla/5.0 (Linux; Android 14; SM-X810) Chrome/130 SamsungBrowser/27'
		})
	);
	await seedObjects(page);
	const r = await page.locator('.paper').boundingBox(),
		scale = r!.width / 794;
	const cdp = await page.context().newCDPSession(page);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mousePressed',
		x: r!.x + 100 * scale,
		y: r!.y + 100 * scale,
		button: 'right',
		buttons: 3,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.getByRole('button', { name: '지우개', exact: true })).toHaveClass(/active/);
	await expect(page.locator('.ink-layer path')).toHaveCount(0);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: r!.x + 100 * scale,
		y: r!.y + 100 * scale,
		button: 'right',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: r!.x + 150 * scale,
		y: r!.y + 200 * scale,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.getByRole('button', { name: '펜', exact: true })).toHaveClass(/active/);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: r!.x + 150 * scale,
		y: r!.y + 200 * scale,
		button: 'left',
		buttons: 0,
		pointerType: 'pen',
		force: 0
	});
	await expect(page.locator('.ink-layer path')).toHaveCount(1);
	await page.locator('.paper').evaluate((el) => {
		for (const buttons of [1, 0])
			el.dispatchEvent(
				new PointerEvent('pointermove', {
					bubbles: true,
					pointerType: 'pen',
					pointerId: 2,
					pressure: 0,
					buttons
				})
			);
	});
	await expect(page.getByRole('button', { name: '펜', exact: true })).toHaveClass(/active/);
});
test('a new notebook and its pages remain separate from the original notebook', async ({
	page
}) => {
	await page.goto(base);
	await page.locator('.paper').waitFor();
	await page.getByRole('button', { name: '노트북 만들기', exact: false }).click();
	await page.getByRole('textbox', { name: '이름', exact: true }).fill('수학');
	await page.getByRole('button', { name: '만들기', exact: true }).click();
	await page.locator('.library-add-page button').first().click();
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).fill('선형대수');
	await page.getByRole('combobox', { name: '노트북 선택' }).selectOption({ label: '내 노트북' });
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'첫 번째 페이지'
	);
	await page.getByRole('combobox', { name: '노트북 선택' }).selectOption({ label: '수학' });
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'선형대수'
	);
});
test('changing page defaults affects new pages without recoloring existing notes', async ({
	page
}) => {
	await page.goto(base);
	await page.locator('.paper').waitFor();
	await page.getByRole('button', { name: '페이지 기본값', exact: true }).click();
	await page.getByRole('button', { name: '백지', exact: true }).click();
	await page.getByRole('button', { name: '노란 종이', exact: true }).click();
	await page.getByRole('button', { name: '기본값 저장', exact: true }).click();
	expect(await page.locator('.paper').evaluate((e) => getComputedStyle(e).backgroundColor)).toBe(
		'rgb(255, 255, 255)'
	);
	await page.locator('.library-add-page button').first().click();
	await expect
		.poll(() => page.locator('.paper').evaluate((e) => getComputedStyle(e).backgroundColor))
		.toBe('rgb(255, 245, 207)');
	await expect(page.locator('.ruled-paper')).toHaveCount(0);
});

for (const browser of ['Samsung desktop', 'Chrome desktop client hints', 'Chrome desktop legacy']) {
	test(`${browser}: Samsung hover barrel erases from the margin, then tip lift restores writing`, async ({
		page
	}) => {
		await page.addInitScript((browser) => {
			Object.defineProperty(navigator, 'userAgent', {
				get: () =>
					'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ' +
					(browser === 'Samsung desktop' ? 'SamsungBrowser/27.0 ' : '') +
					'Chrome/130.0 Safari/537.36'
			});
			Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 10 });
			Object.defineProperty(navigator, 'userAgentData', {
				get: () => (browser.includes('client hints') ? { platform: 'Android' } : undefined)
			});
		}, browser);
		await seedObjects(page);
		const r = (await page.locator('.paper').boundingBox())!,
			scale = r.width / 794;
		const x = r.x + 100 * scale,
			y = r.y + 100 * scale;
		await page.locator('.viewport').evaluate(
			(el, point) =>
				el.dispatchEvent(
					new PointerEvent('pointermove', {
						bubbles: true,
						pointerType: 'pen',
						pointerId: 2,
						buttons: 1,
						pressure: 0,
						clientX: point.x - 10,
						clientY: point.y + 50
					})
				),
			r
		);
		await expect(page.getByRole('button', { name: '지우개', exact: true })).toHaveClass(/active/);
		// Hover itself must not erase, draw, select or scroll.
		await expect(page.locator('.ink-layer path')).toHaveCount(1);
		const cdp = await page.context().newCDPSession(page);
		await cdp.send('Input.dispatchMouseEvent', {
			type: 'mousePressed',
			x,
			y,
			button: 'left',
			buttons: 1,
			pointerType: 'pen',
			force: 0.5
		});
		await expect(page.locator('.ink-layer path')).toHaveCount(0);
		await cdp.send('Input.dispatchMouseEvent', {
			type: 'mouseReleased',
			x,
			y,
			button: 'left',
			buttons: 0,
			pointerType: 'pen',
			force: 0
		});
		await expect(page.getByRole('button', { name: '펜', exact: true })).toHaveClass(/active/);
		await cdp.send('Input.dispatchMouseEvent', {
			type: 'mousePressed',
			x,
			y,
			button: 'left',
			buttons: 1,
			pointerType: 'pen',
			force: 0.5
		});
		await cdp.send('Input.dispatchMouseEvent', {
			type: 'mouseMoved',
			x: x + 40,
			y: y + 20,
			button: 'none',
			buttons: 1,
			pointerType: 'pen',
			force: 0.5
		});
		await cdp.send('Input.dispatchMouseEvent', {
			type: 'mouseReleased',
			x: x + 40,
			y: y + 20,
			button: 'left',
			buttons: 0,
			pointerType: 'pen',
			force: 0
		});
		await expect(page.locator('.ink-layer path')).toHaveCount(1);
		await expect(page.locator('.image-object')).toHaveCount(1);
		await expect(page.locator('.text-object')).toContainText('텍스트 보존');
	});
}

test('ink remains visible above an inserted image and can be drawn on it', async ({ page }) => {
	await seedObjects(page);
	const layers = await page.evaluate(() => ({
		ink: Number(getComputedStyle(document.querySelector('.paper .ink-layer')!).zIndex),
		image: Number(getComputedStyle(document.querySelector('.paper .image-object')!).zIndex)
	}));
	expect(layers.ink).toBeGreaterThan(layers.image);
	const before = await page.locator('.paper .ink-layer path').count();
	const image = await page.locator('.image-object').boundingBox();
	await page.getByRole('button', { name: '펜', exact: true }).first().click();
	await page.mouse.move(image!.x + 15, image!.y + 15);
	await page.mouse.down();
	await page.mouse.move(image!.x + 55, image!.y + 55, { steps: 5 });
	await page.mouse.up();
	await expect(page.locator('.paper .ink-layer path')).toHaveCount(before + 1);
});
