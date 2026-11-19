import type { PdfNotebook, Stroke, InkPoint } from './model';

/** Lazy source metadata keeps opening cost independent of the number of pages. */
export function emptyNotebook(pageCount: number): PdfNotebook {
	return {
		version: 1,
		pages: Array.from({ length: pageCount }, (_, source) => ({
			id: crypto.randomUUID(),
			source,
			rotation: 0,
			width: 0,
			height: 0,
			sourceReady: false,
			strokes: [],
			notes: []
		}))
	};
}
/** Each backing store is limited to 64 MB; ink remains vector data at every zoom. */
export function backingScale(width: number, height: number, dpr: number) {
	return Math.min(dpr || 1, Math.sqrt(16_000_000 / (width * height)));
}
export function strokePath(stroke: Stroke, project: (p: InkPoint) => number[]) {
	if (stroke.points.length === 1) {
		const [x, y] = project(stroke.points[0]);
		return `M${x},${y}l0.001,0`;
	}
	return stroke.points
		.map((p, i) => {
			const [x, y] = project(p);
			return `${i ? 'L' : 'M'}${x},${y}`;
		})
		.join(' ');
}
