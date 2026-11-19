import { expect, it } from 'vitest';
import { partialErase, inPolygon, copyInk, pasteInk } from './ink';
import type { Stroke } from './model';
const stroke: Stroke = {
	id: 'original',
	kind: 'pen',
	color: '#000000',
	width: 3,
	points: [
		{ x: 0, y: 0, pressure: 0.5 },
		{ x: 100, y: 0, pressure: 0.5 }
	]
};
it('splits a long segment at the eraser without deleting unaffected ends', () => {
	const r = partialErase([stroke], { x: 50, y: 0, pressure: 0.5 }, 10);
	expect(r).toHaveLength(2);
	expect(r[0].points[0].x).toBe(0);
	expect(r[1].points.at(-1)?.x).toBe(100);
	expect(r.flatMap((s) => s.points).every((p) => Math.abs(p.x - 50) > 10)).toBe(true);
});
it('copies independently with new identities and supports polygon selection', () => {
	copyInk([stroke]);
	const pasted = pasteInk();
	expect(pasted[0].id).not.toBe(stroke.id);
	expect(stroke.points[0].x).toBe(0);
	expect(pasted[0].points[0].x).toBe(18);
	expect(
		inPolygon({ x: 5, y: 5, pressure: 1 }, [
			{ x: 0, y: 0, pressure: 1 },
			{ x: 10, y: 0, pressure: 1 },
			{ x: 10, y: 10, pressure: 1 },
			{ x: 0, y: 10, pressure: 1 }
		])
	).toBe(true);
});
