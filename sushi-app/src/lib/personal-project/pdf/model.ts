export type InkPoint = { x: number; y: number; pressure: number };
export type Stroke = {
	id: string;
	kind: 'pen' | 'highlight';
	color: string;
	width: number;
	points: InkPoint[];
};
export type TextNote = {
	id: string;
	x: number;
	y: number;
	text: string;
	color: string;
	size: number;
};
export type PdfPage = {
	id: string;
	source: number | null;
	rotation: number;
	width: number;
	height: number;
	strokes: Stroke[];
	notes: TextNote[];
};
export type PdfNotebook = { version: 1; pages: PdfPage[] };
export function distance(p: InkPoint, a: InkPoint, b: InkPoint) {
	const dx = b.x - a.x,
		dy = b.y - a.y,
		t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
	return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy);
}
export function erase(strokes: Stroke[], point: InkPoint, radius: number) {
	return strokes.filter(
		(s) =>
			!s.points.some(
				(p, i) => distance(point, p, s.points[Math.max(0, i - 1)]) <= radius + s.width / 2
			)
	);
}
export async function exportPdf(original: Uint8Array, notebook: PdfNotebook) {
	const { PDFDocument, rgb, degrees } = await import('pdf-lib');
	const source = await PDFDocument.load(original);
	const output = await PDFDocument.create();
	const color = (hex: string) =>
		rgb(
			parseInt(hex.slice(1, 3), 16) / 255,
			parseInt(hex.slice(3, 5), 16) / 255,
			parseInt(hex.slice(5, 7), 16) / 255
		);
	let font: import('pdf-lib').PDFFont | undefined;
	if (notebook.pages.some((p) => p.notes.length)) {
		const fontkit = (await import('@pdf-lib/fontkit')).default;
		output.registerFontkit(fontkit);
		const response = await fetch('/fonts/NanumGothic-Regular.ttf');
		if (!response.ok) throw Error('한글 글꼴을 불러오지 못했습니다. 다시 내보내주세요.');
		font = await output.embedFont(await response.arrayBuffer(), { subset: true });
	}
	for (const p of notebook.pages) {
		const page =
			p.source === null
				? output.addPage([p.width, p.height])
				: output.addPage((await output.copyPages(source, [p.source]))[0]);
		page.setRotation(degrees(p.rotation));
		for (const s of p.strokes) {
			for (let i = 0; i < s.points.length; i++) {
				const a = s.points[Math.max(0, i - 1)],
					b = s.points[i];
				page.drawLine({
					start: { x: a.x, y: a.y },
					end: { x: b.x + 0.001, y: b.y },
					thickness: s.width * (s.kind === 'pen' ? Math.max(0.25, b.pressure) : 1),
					color: color(s.color),
					opacity: s.kind === 'highlight' ? 0.25 : 1
				});
			}
		}
		for (const n of p.notes)
			page.drawText(n.text, { x: n.x, y: n.y, size: n.size, font, color: color(n.color) });
	}
	return output.save();
}
