import { test, expect } from '@playwright/test';
const preview = process.env.NOTEBOOK_PREVIEW_URL || 'http://127.0.0.1:5192/?workspace=1';
test('vertical touch scrolling stays at its new position after release', async ({ page }) => {
	await page.goto(preview);
	await page.locator('.paper').waitFor();
	const cdp = await page.context().newCDPSession(page);
	await cdp.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
	const point = await page.evaluate(() => {
		const v = document.querySelector('.viewport') as HTMLElement;
		v.scrollTop = 100;
		const r = v.getBoundingClientRect();
		return { x: r.x + r.width * 0.6, y: r.y + 230 };
	});
	await cdp.send('Input.dispatchTouchEvent', {
		type: 'touchStart',
		touchPoints: [{ ...point, id: 1 }]
	});
	for (let i = 1; i <= 6; i++)
		await cdp.send('Input.dispatchTouchEvent', {
			type: 'touchMove',
			touchPoints: [{ x: point.x, y: point.y - i * 20, id: 1 }]
		});
	await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
	await expect
		.poll(() => page.locator('.viewport').evaluate((e) => e.scrollTop))
		.toBeGreaterThan(200);
});
test('page navigation menu stays outside the compact tool rows clipping region', async ({
	page
}) => {
	await page.goto(preview);
	await page.getByRole('button', { name: '페이지 넘김 방식' }).click();
	const popover = page.locator('.notebook-popover:popover-open');
	await expect(popover).toBeVisible();
	const state = await page.evaluate(() => {
		const nav = document.querySelector('.main-tools') as HTMLElement,
			r = document.querySelector('.notebook-popover:popover-open')!.getBoundingClientRect();
		return {
			rowHeight: nav.clientHeight,
			scrollHeight: nav.scrollHeight,
			bottom: r.bottom,
			screen: innerHeight
		};
	});
	expect(state.rowHeight).toBeLessThanOrEqual(50);
	expect(state.scrollHeight).toBe(state.rowHeight);
	expect(state.bottom).toBeLessThan(state.screen);
});
test('spread fits two pages, activates the right page and advances by pairs', async ({ page }) => {
	await page.goto(preview);
	await page.getByRole('button', { name: '페이지 추가', exact: true }).click();
	await page.getByRole('button', { name: '페이지 추가', exact: true }).click();
	await page.getByRole('button', { name: '1 페이지', exact: true }).click();
	await page.getByRole('button', { name: '두 쪽 보기', exact: true }).click();
	await expect(page.locator('.page-slot')).toHaveCount(2);
	const layout = await page.locator('.page-slot').evaluateAll((es) =>
		es.map((e) => {
			const r = e.getBoundingClientRect();
			return { x: r.x, y: r.y, right: r.right };
		})
	);
	expect(Math.abs(layout[0].y - layout[1].y)).toBeLessThan(2);
	expect(layout[1].x).toBeGreaterThan(layout[0].right);
	expect(layout[1].right).toBeLessThan(page.viewportSize()!.width);
	await page.locator('.passive-page').click({ position: { x: 50, y: 50 } });
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('2');
	await expect(page.locator('.page-slot').first()).toHaveAttribute('data-page-slot', '0');
	await page.getByRole('button', { name: '다음 페이지', exact: true }).click();
	await expect(page.locator('.page-slot')).toHaveCount(1);
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('3');
});
test('barrel button can switch to lasso during a pen contact', async ({ page }) => {
	await page.goto(preview);
	await page.locator('.paper').waitFor();
	const r = await page.locator('.paper').boundingBox();
	const x = r!.x + 120,
		y = r!.y + 100;
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
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 10,
		y: y + 10,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mousePressed',
		x: x + 15,
		y: y + 15,
		button: 'right',
		buttons: 3,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 50,
		y: y + 20,
		button: 'none',
		buttons: 3,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.locator('.ink-layer path[stroke-dasharray]')).toHaveCount(1);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: x + 50,
		y: y + 20,
		button: 'right',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 70,
		y: y + 30,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.locator('.ink-layer path[stroke-dasharray]')).toHaveCount(0);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: x + 70,
		y: y + 30,
		button: 'left',
		buttons: 0,
		pointerType: 'pen',
		force: 0
	});
	expect(await page.locator('.paper').evaluate((e) => getComputedStyle(e).cursor)).toBe('default');
});
test('mobile text editing retains a white document after keyboard-sized viewport resize', async ({
	page
}) => {
	await page.setViewportSize({ width: 800, height: 1000 });
	await page.goto(preview);
	await page.getByRole('button', { name: '텍스트', exact: true }).click();
	await page.locator('.paper').click({ position: { x: 100, y: 100 } });
	const editor = page.locator('.paper [contenteditable=true]');
	await editor.fill('모바일 입력 확인');
	await page.setViewportSize({ width: 800, height: 520 });
	await expect(editor).toHaveText('모바일 입력 확인');
	await expect
		.poll(() => page.locator('.netaq-notebook').evaluate((e) => e.getBoundingClientRect().bottom))
		.toBeLessThanOrEqual(520);
	const state = await page.locator('.paper').evaluate((e) => ({
		background: getComputedStyle(e).backgroundColor,
		scheme: getComputedStyle(e).colorScheme,
		root: document.querySelector('.netaq-notebook')!.getBoundingClientRect().bottom,
		context: (e.querySelector('.live-ink') as HTMLCanvasElement)
			.getContext('2d')!
			.getContextAttributes()
	}));
	expect(state.background).toBe('rgb(255, 255, 255)');
	expect(state.scheme).toContain('light');
	expect(state.context.desynchronized).toBe(false);
	expect(state.root).toBeLessThanOrEqual(520);
	await page.screenshot({ path: '/tmp/notebook-mobile-keyboard.png' });
});
test('S Pen hover button starts lasso only when the tip touches and finishes on lift', async ({
	page
}) => {
	await page.goto(preview);
	await page.locator('.paper').waitFor();
	const r = await page.locator('.paper').boundingBox(),
		x = r!.x + 100,
		y = r!.y + 100;
	const cdp = await page.context().newCDPSession(page);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mousePressed',
		x,
		y,
		button: 'right',
		buttons: 2,
		pointerType: 'pen',
		force: 0
	});
	await expect(page.locator('.ink-layer path')).toHaveCount(0);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 5,
		y: y + 5,
		button: 'none',
		buttons: 3,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 30,
		y: y + 30,
		button: 'none',
		buttons: 3,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.locator('.ink-layer path[stroke-dasharray]')).toHaveCount(1);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 30,
		y: y + 30,
		button: 'none',
		buttons: 2,
		pointerType: 'pen',
		force: 0
	});
	await expect(page.locator('.ink-layer path')).toHaveCount(0);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: x + 30,
		y: y + 30,
		button: 'right',
		buttons: 0,
		pointerType: 'pen',
		force: 0
	});
});

test('two page toggle persists across all navigation directions including continuous rows', async ({
	page
}) => {
	await page.goto(preview);
	for (let i = 0; i < 4; i++)
		await page.getByRole('button', { name: '페이지 추가', exact: true }).click();
	const toggle = page.getByRole('button', { name: '두 쪽 보기', exact: true });
	await toggle.click();
	for (const label of ['넘기기', '연속 스크롤']) {
		await page.getByRole('button', { name: '페이지 넘김 방식' }).click();
		await page
			.locator('.navigation-menu')
			.getByRole('button', { name: label, exact: true })
			.click();
		await expect(toggle).toHaveAttribute('aria-pressed', 'true');
		if (label === '연속 스크롤') {
			await expect(page.locator('.page-row')).toHaveCount(3);
			await expect(page.locator('.page-row').first().locator('.page-slot')).toHaveCount(2);
		}
	}
	await toggle.click();
	await expect(page.locator('.page-row')).toHaveCount(5);
	await expect(page.getByRole('button', { name: '페이지 넘김 방식' })).toContainText('연속 스크롤');
});
test('ambiguous hover signals never latch a drawing tool after release', async ({ page }) => {
	await page.goto(preview);
	await page.locator('.paper').waitFor();
	const r = await page.locator('.paper').boundingBox(),
		x = r!.x + 100,
		y = r!.y + 100;
	await page.locator('.paper').evaluate(
		(el, p) =>
			el.dispatchEvent(
				new PointerEvent('pointermove', {
					bubbles: true,
					pointerType: 'pen',
					pointerId: 2,
					pressure: 0,
					buttons: 1,
					button: -1,
					clientX: p.x,
					clientY: p.y
				})
			),
		{ x, y }
	);
	// CDP assigns pointerId=2 for pen. Subsequent contact is a real captured pointer.
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
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 40,
		y: y + 20,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.locator('.ink-layer path[stroke-dasharray]')).toHaveCount(0);
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
});

test('contextmenu without a held-button signal never latches another tool', async ({ page }) => {
	await page.goto(preview);
	await page.locator('.paper').waitFor();
	const r = await page.locator('.paper').boundingBox(),
		x = r!.x + 100,
		y = r!.y + 100;
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
	await page.locator('.paper').evaluate(
		(el, p) =>
			el.dispatchEvent(
				new PointerEvent('contextmenu', {
					bubbles: true,
					cancelable: true,
					pointerType: 'pen',
					pointerId: 2,
					buttons: 1,
					button: 0,
					clientX: p.x,
					clientY: p.y
				})
			),
		{ x, y }
	);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 30,
		y: y + 20,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseMoved',
		x: x + 50,
		y: y + 40,
		button: 'none',
		buttons: 1,
		pointerType: 'pen',
		force: 0.5
	});
	await expect(page.locator('.ink-layer path[stroke-dasharray]')).toHaveCount(0);
	await cdp.send('Input.dispatchMouseEvent', {
		type: 'mouseReleased',
		x: x + 50,
		y: y + 40,
		button: 'left',
		buttons: 0,
		pointerType: 'pen',
		force: 0
	});
});
test('arrow keys turn pages and spreads, stop at boundaries, and leave text input alone', async ({
	page
}) => {
	await page.goto(preview);
	for (let i = 0; i < 3; i++)
		await page.getByRole('button', { name: '페이지 추가', exact: true }).click();
	await page.getByRole('button', { name: '1 페이지', exact: true }).click();
	await page.keyboard.press('ArrowRight');
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('2');
	await page.keyboard.press('ArrowLeft');
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('1');
	await page.getByRole('button', { name: '두 쪽 보기', exact: true }).click();
	await page.keyboard.press('ArrowRight');
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('3');
	await page.keyboard.press('ArrowRight');
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('3');
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).focus();
	await page.keyboard.press('ArrowLeft');
	await expect(page.getByRole('spinbutton', { name: '현재 페이지', exact: true })).toHaveValue('3');
});
