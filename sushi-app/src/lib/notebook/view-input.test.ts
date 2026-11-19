import { describe, it, expect } from 'vitest';
import {
	visiblePageIndices,
	visiblePageRows,
	adjacentPage,
	penOverride,
	createPenInput,
	usesAndroidPen
} from './view-input';
describe('two page layout', () => {
	it('keeps the same pair when selecting its right page', () => {
		expect(visiblePageIndices('vertical', 2, 5, true)).toEqual([2, 3]);
		expect(visiblePageIndices('horizontal', 3, 5, true)).toEqual([2, 3]);
	});
	it('allows an odd final page without inventing another', () => {
		expect(visiblePageIndices('vertical', 4, 5, true)).toEqual([4]);
	});
});
describe('chorded pen buttons', () => {
	it('recognizes barrel presses on move and releases back to the selected tool', () => {
		expect(penOverride({ pointerType: 'pen', buttons: 3, button: 2, type: 'pointermove' })).toBe(
			'lasso'
		);
		expect(penOverride({ pointerType: 'pen', buttons: 1, button: 2, type: 'pointermove' })).toBe(
			null
		);
	});
	it('prioritizes the eraser end and ignores mouse right click', () => {
		expect(penOverride({ pointerType: 'pen', buttons: 34, button: -1 })).toBe('eraser');
		expect(penOverride({ pointerType: 'mouse', buttons: 2, button: 2 })).toBe(null);
	});
});

describe('independent layout and navigation', () => {
	it('keeps continuous rows paired and an odd final page alone', () => {
		expect(visiblePageRows('continuous', 3, 5, true)).toEqual([[0, 1], [2, 3], [4]]);
		expect(visiblePageRows('continuous', 3, 5, false)).toEqual([[0], [1], [2], [3], [4]]);
	});
	it('turns one or two pages according to layout', () => {
		expect(adjacentPage(3, 1, true)).toBe(4);
		expect(adjacentPage(3, -1, true)).toBe(0);
		expect(adjacentPage(3, 1, false)).toBe(4);
	});
});
const event = (type: string, buttons: number, pressure: number, extra = {}) => ({
	type,
	buttons,
	pressure,
	button: -1,
	pointerType: 'pen',
	pointerId: 7,
	...extra
});
describe('Samsung hover compatibility without Surface regression', () => {
	it('does not mistake an ambiguous Android primary mask for a held barrel', () => {
		const input = createPenInput();
		expect(input.update(event('pointermove', 1, 0))).toEqual({ contact: false, override: null });
		expect(input.update(event('pointerdown', 1, 0.4))).toEqual({
			contact: true,
			override: null
		});
		expect(input.update(event('pointermove', 1, 0.6))).toEqual({
			contact: true,
			override: null
		});
		expect(input.update(event('pointerup', 0, 0))).toEqual({ contact: false, override: null });
		expect(input.update(event('pointerdown', 1, 0.4))).toEqual({ contact: true, override: null });
	});
	it('does not turn normal low-pressure writing into a barrel press', () => {
		const input = createPenInput();
		input.update(event('pointerdown', 1, 0));
		expect(input.update(event('pointermove', 1, 0))).toEqual({ contact: true, override: null });
	});
	it('clears a released hover button before contact', () => {
		const input = createPenInput();
		input.update(event('pointermove', 1, 0));
		input.update(event('pointermove', 0, 0));
		expect(input.update(event('pointerdown', 1, 0.4)).override).toBe(null);
	});
	it('preserves Surface barrel and inverted eraser bitmasks', () => {
		const input = createPenInput();
		expect(input.update(event('pointerdown', 3, 0.5)).override).toBe('lasso');
		expect(input.update(event('pointermove', 1, 0.5)).override).toBe(null);
		expect(input.update(event('pointermove', 32, 0.5)).override).toBe('eraser');
	});
	it('ignores fingers and mouse buttons and resets on cancellation', () => {
		const input = createPenInput();
		expect(input.update(event('pointermove', 1, 0, { pointerType: 'touch' })).override).toBe(null);
		input.update(event('pointermove', 1, 0));
		input.update(event('pointercancel', 0, 0));
		expect(input.update(event('pointerdown', 1, 0.5)).override).toBe(null);
		input.reset();
		expect(input.update(event('pointermove', 2, 0, { pointerType: 'mouse' })).override).toBe(null);
	});
});

it('does not infer a barrel from default hover pressure', () => {
	const input = createPenInput();
	expect(input.update(event('pointermove', 1, 0.5))).toEqual({ contact: false, override: null });
	expect(input.update(event('pointerdown', 1, 0.5))).toEqual({ contact: true, override: null });
});
it('does not invent a held barrel press from contextmenu', () => {
	const input = createPenInput();
	input.update(event('pointerdown', 1, 0.5));
	input.update(event('contextmenu', 1, 0.5));
	expect(input.update(event('pointermove', 1, 0.5))).toEqual({ contact: true, override: null });
	input.update(event('pointerup', 0, 0));
	expect(input.update(event('pointerdown', 1, 0.5)).override).toBe(null);
});

it('does not latch contextmenu for a Surface pen with a working standard barrel bit', () => {
	const input = createPenInput();
	input.update(event('pointerdown', 3, 0.5));
	input.update(event('contextmenu', 1, 0.5));
	expect(input.update(event('pointermove', 1, 0.5)).override).toBe(null);
});

describe('Android desktop-site platform detection', () => {
	it('detects Samsung desktop mode and Android client hints without a mobile UA', () => {
		expect(
			usesAndroidPen({
				userAgent: 'Mozilla/5.0 (X11; Linux x86_64) SamsungBrowser/27.0 Chrome/130.0',
				maxTouchPoints: 10
			})
		).toBe(true);
		expect(
			usesAndroidPen({
				userAgent: 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0',
				userAgentData: { platform: 'Android' }
			})
		).toBe(true);
		expect(
			usesAndroidPen({
				userAgent: 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0',
				maxTouchPoints: 5
			})
		).toBe(true);
	});
	it('keeps Windows Surface, Chromebook and non-touch Linux on their original mapping', () => {
		for (const userAgent of [
			'Windows NT 10.0 Chrome/130.0',
			'CrOS x86_64 Chrome/130.0',
			'X11; Linux x86_64 Chrome/130.0'
		])
			expect(
				usesAndroidPen({ userAgent, maxTouchPoints: userAgent.includes('Linux') ? 0 : 10 })
			).toBe(false);
	});
});

describe('Samsung legacy primary hover button', () => {
	it.each([0, 0.5])(
		'erases only the contact preceded by a held hover button, pressure %s',
		(pressure) => {
			const input = createPenInput(() => true);
			expect(input.update(event('pointermove', 1, pressure))).toEqual({
				contact: false,
				override: 'eraser'
			});
			expect(input.update(event('pointerdown', 1, 0.5))).toEqual({
				contact: true,
				override: 'eraser'
			});
			expect(input.update(event('pointermove', 1, 0.5)).override).toBe('eraser');
			input.update(event('pointerup', 0, 0));
			expect(input.update(event('pointerdown', 1, 0.5)).override).toBe(null);
		}
	);
	it('returns immediately on hover release and does not toggle the selected tool', () => {
		const input = createPenInput(() => true);
		input.update(event('pointermove', 1, 0));
		expect(input.update(event('pointermove', 0, 0)).override).toBe(null);
		expect(input.update(event('pointerdown', 1, 0.5)).override).toBe(null);
	});
	it('never infers a barrel from ordinary contact, low pressure or a context menu', () => {
		const input = createPenInput(() => true);
		input.update(event('pointerdown', 1, 0));
		expect(input.update(event('pointermove', 1, 0)).override).toBe(null);
		input.update(event('contextmenu', 1, 0.5));
		expect(input.update(event('pointermove', 1, 0.5)).override).toBe(null);
	});
	it('uses real button masks when supported, including release during contact', () => {
		const input = createPenInput(() => true);
		input.update(event('pointermove', 2, 0));
		expect(input.update(event('pointermove', 1, 0)).override).toBe(null);
		expect(input.update(event('pointerdown', 3, 0.5)).override).toBe('lasso');
		expect(input.update(event('pointermove', 1, 0.5)).override).toBe(null);
	});
	it('clears legacy state on cancellation, blur reset, and a different pointer', () => {
		for (const kind of ['cancel', 'reset', 'pointer']) {
			const input = createPenInput(() => true);
			input.update(event('pointermove', 1, 0));
			if (kind === 'cancel') input.update(event('pointercancel', 0, 0));
			if (kind === 'reset') input.reset();
			expect(
				input.update(event('pointerdown', 1, 0.5, { pointerId: kind === 'pointer' ? 8 : 7 }))
					.override
			).toBe(null);
		}
	});
});
