import type { InkPoint, NotebookItem } from './types';
export function segmentDistance(p: InkPoint, a: InkPoint, b: InkPoint) {
	const dx = b.x - a.x,
		dy = b.y - a.y,
		t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
	return Math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy);
}
export function inside(p: InkPoint, poly: InkPoint[]) {
	if (poly.some((a, i) => segmentDistance(p, a, poly[(i + 1) % poly.length]) < 0.01)) return true;
	let c = false;
	for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
		const a = poly[i],
			b = poly[j];
		if (a.y > p.y !== b.y > p.y && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) c = !c;
	}
	return c;
}
function intersections(a: InkPoint, b: InkPoint, c: InkPoint, d: InkPoint) {
	const rx = b.x - a.x,
		ry = b.y - a.y,
		sx = d.x - c.x,
		sy = d.y - c.y,
		den = rx * sy - ry * sx;
	if (Math.abs(den) < 1e-8) return [];
	const t = ((c.x - a.x) * sy - (c.y - a.y) * sx) / den,
		u = ((c.x - a.x) * ry - (c.y - a.y) * rx) / den;
	return t >= 0 && t <= 1 && u >= 0 && u <= 1 ? [t] : [];
}
export function createLassoSelector(poly: InkPoint[], mode: string) {
	let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	for (const p of poly) { minX = Math.min(minX,p.x); minY = Math.min(minY,p.y); maxX = Math.max(maxX,p.x); maxY = Math.max(maxY,p.y); }
	const edges = poly.map((a,i) => { const b=poly[(i+1)%poly.length]; return {a,b,minX:Math.min(a.x,b.x),maxX:Math.max(a.x,b.x),minY:Math.min(a.y,b.y),maxY:Math.max(a.y,b.y)}; });
	const pointInside = (p: InkPoint) => {
		let contained = false;
		for (const edge of edges) {
			const {a,b,minX,maxX,minY,maxY}=edge;
			if (p.y < minY-0.01 || p.y > maxY+0.01) continue;
			if (p.x >= minX-0.01 && p.x <= maxX+0.01 && segmentDistance(p,a,b)<0.01) return true;
			if ((a.y>p.y)!==(b.y>p.y) && p.x < ((b.x-a.x)*(p.y-a.y))/(b.y-a.y)+a.x) contained=!contained;
		}
		return contained;
	};
	return (points: InkPoint[]) => {
		if (poly.length < 3 || !points.length) return false;
		let left = Infinity, top = Infinity, right = -Infinity, bottom = -Infinity;
		for (const p of points) { left = Math.min(left,p.x); top = Math.min(top,p.y); right = Math.max(right,p.x); bottom = Math.max(bottom,p.y); }
		const epsilon = 0.01;
		if (right < minX-epsilon || left > maxX+epsilon || bottom < minY-epsilon || top > maxY+epsilon) return false;
		if (mode !== 'touch' && (left < minX-epsilon || right > maxX+epsilon || top < minY-epsilon || bottom > maxY+epsilon)) return false;
		return selectedByLassoExact(points, poly, mode, pointInside);
	};
}
export function selectedByLasso(points: InkPoint[], poly: InkPoint[], mode: string) {
	return createLassoSelector(poly, mode)(points);
}
function selectedByLassoExact(points: InkPoint[], poly: InkPoint[], mode: string, pointInside: (p: InkPoint) => boolean) {
	if (poly.length < 3 || !points.length) return false;
	if (mode === 'touch') {
		return (
			points.some(pointInside) ||
			points.some(
				(b, i) =>
					i &&
					poly.some(
						(c, j) => intersections(points[i - 1], b, c, poly[(j + 1) % poly.length]).length
					)
			)
		);
	}
	if (!points.every(pointInside)) return false;
	return points.every((b, i) => {
		if (!i) return true;
		const a = points[i - 1],
			ts = [
				0,
				1,
				...poly.flatMap((c, j) => intersections(a, b, c, poly[(j + 1) % poly.length]))
			].sort((a, b) => a - b);
		return ts.every(
			(t, j) =>
				!j ||
				pointInside(
					{
						x: a.x + ((b.x - a.x) * (t + ts[j - 1])) / 2,
						y: a.y + ((b.y - a.y) * (t + ts[j - 1])) / 2
					}
				)
		);
	});
}
export function bounds(objects: NotebookItem[]) {
	let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
	const include = (x: number, y: number) => { minX = Math.min(minX,x); minY = Math.min(minY,y); maxX = Math.max(maxX,x); maxY = Math.max(maxY,y); };
	for (const o of objects) {
		if (o.kind === 'stroke') for (const point of o.points) include(point.x,point.y);
		else { include(o.x,o.y); include(o.x+o.w,o.y+o.h); }
	}
	if (minX === Infinity) return null;
	return {x:minX-5,y:minY-5,w:Math.max(24,maxX-minX+10),h:Math.max(24,maxY-minY+10)};
}
