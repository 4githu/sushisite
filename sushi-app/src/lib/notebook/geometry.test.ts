import { test, expect } from 'vitest';
const assert = { equal: (actual: unknown, expected: unknown) => expect(actual).toBe(expected) };
import { selectedByLasso } from './geometry';
const square = [
	{ x: 0, y: 0 },
	{ x: 10, y: 0 },
	{ x: 10, y: 10 },
	{ x: 0, y: 10 }
];
test('crossing stroke with both ends outside is selected only by touch mode', () => {
	const points = [
		{ x: -5, y: 5 },
		{ x: 15, y: 5 }
	];
	assert.equal(Boolean(selectedByLasso(points, square, 'touch')), true);
	assert.equal(selectedByLasso(points, square, 'inside'), false);
});
test('fully contained and boundary strokes are included', () => {
	for (const pts of [
		[
			{ x: 2, y: 2 },
			{ x: 8, y: 8 }
		],
		[
			{ x: 0, y: 0 },
			{ x: 10, y: 0 }
		]
	])
		assert.equal(selectedByLasso(pts, square, 'inside'), true);
});
test('concave lasso rejects a stroke crossing a notch despite contained endpoints', () => {
	const poly = [
			{ x: 0, y: 0 },
			{ x: 10, y: 0 },
			{ x: 10, y: 10 },
			{ x: 7, y: 10 },
			{ x: 7, y: 3 },
			{ x: 3, y: 3 },
			{ x: 3, y: 10 },
			{ x: 0, y: 10 }
		],
		pts = [
			{ x: 1, y: 8 },
			{ x: 9, y: 8 }
		];
	assert.equal(selectedByLasso(pts, poly, 'inside'), false);
	assert.equal(Boolean(selectedByLasso(pts, poly, 'touch')), true);
});
test('disjoint stroke excluded in both modes', () => {
	for (const mode of ['touch', 'inside'])
		assert.equal(
			Boolean(
				selectedByLasso(
					[
						{ x: 20, y: 20 },
						{ x: 30, y: 30 }
					],
					square,
					mode
				)
			),
			false
		);
});

test('large selection bounds do not overflow argument limits', async () => {
	const { bounds } = await import('./geometry');
	const points = Array.from({length: 150000}, (_, i) => ({x:i, y:i % 37}));
	const result = bounds([{id:'large', kind:'stroke', points, width:2, color:'#000'}] as any);
	expect(result?.x).toBe(-5);
	expect(result?.w).toBe(150009);
});
