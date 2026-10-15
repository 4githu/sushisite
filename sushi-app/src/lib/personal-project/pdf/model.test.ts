import { expect, it, vi } from 'vitest';
import { PDFDocument } from 'pdf-lib';
import { readFile } from 'node:fs/promises';
import { erase, exportPdf, type PdfNotebook } from './model';
it('preserves coordinates and original vector pages across reorder and rotation', async () => {
	const original = await PDFDocument.create();
	original.addPage([300, 400]).drawText('Original vector text');
	original.addPage([500, 600]);
	const bytes = await original.save();
	const notebook: PdfNotebook = {
		version: 1,
		pages: [
			{
				id: 'second',
				source: 1,
				rotation: 90,
				width: 500,
				height: 600,
				strokes: [],
				notes: [{ id: 'note', x: 40, y: 50, text: '한글 주석', color: '#222222', size: 14 }]
			},
			{
				id: 'first',
				source: 0,
				rotation: 0,
				width: 300,
				height: 400,
				strokes: [
					{
						id: 'ink',
						kind: 'pen',
						color: '#25262b',
						width: 2,
						points: [
							{ x: 20, y: 30, pressure: 0.5 },
							{ x: 40, y: 50, pressure: 1 }
						]
					}
				],
				notes: []
			}
		]
	};
	vi.stubGlobal(
		'fetch',
		async () => new Response(await readFile('static/fonts/NanumGothic-Regular.ttf'))
	);
	try {
		const exported = await PDFDocument.load(await exportPdf(bytes, notebook));
		expect(exported.getPageCount()).toBe(2);
		expect(exported.getPage(0).getRotation().angle).toBe(90);
		expect(exported.getPage(1).getWidth()).toBe(300);
		expect((await PDFDocument.load(bytes)).getPage(0).getRotation().angle).toBe(0);
		expect(notebook.pages[1].strokes[0].points[0]).toEqual({ x: 20, y: 30, pressure: 0.5 });
	} finally {
		vi.unstubAllGlobals();
	}
});
it('erases a segment between sampled points', () => {
	const stroke = {
		id: 'x',
		kind: 'pen' as const,
		color: '#000000',
		width: 2,
		points: [
			{ x: 0, y: 0, pressure: 0.5 },
			{ x: 100, y: 0, pressure: 0.5 }
		]
	};
	expect(erase([stroke], { x: 50, y: 1, pressure: 0 }, 2)).toEqual([]);
	expect(erase([stroke], { x: 50, y: 20, pressure: 0 }, 2)).toEqual([stroke]);
});
