import { distance, type Stroke, type InkPoint } from './model';
let clipboard: Stroke[] = [];
export function copyInk(strokes: Stroke[]) {
	clipboard = structuredClone(strokes);
}
export function pasteInk(dx = 18, dy = 18): Stroke[] {
	return clipboard.map((s) => ({
		...s,
		id: crypto.randomUUID(),
		points: s.points.map((p) => ({ ...p, x: p.x + dx, y: p.y + dy }))
	}));
}
export function inPolygon(p: InkPoint, poly: InkPoint[]) {
	let inside = false;
	for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
		const a = poly[i],
			b = poly[j];
		if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x)
			inside = !inside;
	}
	return inside;
}
export function partialErase(strokes: Stroke[], center: InkPoint, radius: number): Stroke[] {
	const result: Stroke[] = [];
	for (const stroke of strokes) {
		if (
			!stroke.points.some(
				(p, i) => distance(center, p, stroke.points[Math.max(0, i - 1)]) <= radius
			)
		) {
			result.push(stroke);
			continue;
		}
		let part: InkPoint[] = [];
		const flush = () => {
			if (part.length) result.push({ ...stroke, id: crypto.randomUUID(), points: part });
			part = [];
		};
		for (let i = 0; i < stroke.points.length; i++) {
			const a = stroke.points[Math.max(0, i - 1)],
				b = stroke.points[i],
				n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / Math.max(1, radius / 3)));
			for (let j = i ? 1 : 0; j <= n; j++) {
				const t = j / n,
					p = {
						x: a.x + (b.x - a.x) * t,
						y: a.y + (b.y - a.y) * t,
						pressure: a.pressure + (b.pressure - a.pressure) * t
					};
				if (Math.hypot(p.x - center.x, p.y - center.y) <= radius) flush();
				else part.push(p);
			}
		}
		flush();
	}
	return result;
}
