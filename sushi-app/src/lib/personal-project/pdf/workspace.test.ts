import { expect, it } from 'vitest';
import { PDFDocument, degrees } from 'pdf-lib';
import { emptyNotebook, backingScale } from './workspace';
import { outlinePath } from './ink-path';
import { intersectsLasso } from './ink';
import { exportPdf, type Stroke } from './model';
const stroke: Stroke = {
	id: 's',
	kind: 'pen',
	geometry: 'outline',
	width: 3,
	color: '#242424',
	points: [
		{ x: 10, y: 20, pressure: 0.2 },
		{ x: 50, y: 20, pressure: 0.8 },
		{ x: 90, y: 30, pressure: 0.5 }
	]
};
it('opens a large notebook without preloading page metadata and bounds retina backing memory', () => {
	const notebook = emptyNotebook(864);
	expect(notebook.pages).toHaveLength(864);
	expect(notebook.pages.every((p) => !p.sourceReady && p.width === 0)).toBe(true);
	expect(8000 * 8000 * backingScale(8000, 8000, 3) ** 2).toBeLessThanOrEqual(16_000_001);
});
it('lasso finds a sparse segment that crosses the selection polygon', () => {
	const polygon = [
		{ x: 30, y: 0, pressure: 1 },
		{ x: 40, y: 0, pressure: 1 },
		{ x: 40, y: 40, pressure: 1 },
		{ x: 30, y: 40, pressure: 1 }
	];
	expect(
		intersectsLasso({ ...stroke, points: [stroke.points[0], stroke.points[2]] }, polygon)
	).toBe(true);
	expect(intersectsLasso({ ...stroke, points: [{ x: 200, y: 200, pressure: 1 }] }, polygon)).toBe(
		false
	);
});
it('exports pressure contours as vector paths and retains unvisited source rotations', async () => {
	const doc = await PDFDocument.create();
	doc.addPage([595, 842]);
	doc.addPage([800, 400]).setRotation(degrees(90));
	const notebook = emptyNotebook(2);
	notebook.pages[0].strokes = [stroke];
	const bytes = await exportPdf(await doc.save(), notebook);
	const result = await PDFDocument.load(bytes);
	expect(result.getPageCount()).toBe(2);
	expect(result.getPage(1).getRotation().angle).toBe(90);
	expect(outlinePath(stroke)).toMatch(/^M.* Z$/);
	expect(outlinePath(stroke)).not.toContain('NaN');
});
