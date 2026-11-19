import type { InkPoint } from './types';
export function centerline(points: InkPoint[]) {
	if (!points.length) return '';
	const first = points[0];
	if (points.length === 1) return `M${first.x},${first.y}l0.01,0`;
	return points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ');
}
export function horizontalPageSwipe(
	mode: string,
	start: { x: number; y: number },
	end: { x: number; y: number },
	pinched: boolean
) {
	const dx = end.x - start.x,
		dy = end.y - start.y;
	return (mode === 'paged' || mode === 'horizontal') &&
		!pinched &&
		Math.abs(dx) > 80 &&
		Math.abs(dx) > Math.abs(dy) * 1.5
		? dx < 0
			? 1
			: -1
		: 0;
}
