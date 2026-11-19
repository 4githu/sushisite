import { getStroke } from 'perfect-freehand';
import type { Stroke } from './model';
export function outlinePath(
	stroke: Stroke,
	project: (x: number, y: number) => number[] = (x, y) => [x, y]
) {
	const outline = getStroke(
		stroke.points.map((p) => [p.x, p.y, p.pressure]),
		{
			size: stroke.width,
			thinning: 0.35,
			smoothing: 0.5,
			streamline: 0.15,
			simulatePressure: false,
			last: true
		}
	);
	return (
		outline
			.map((p, i) => {
				const [x, y] = project(p[0], p[1]);
				return `${i ? 'L' : 'M'}${x},${y}`;
			})
			.join(' ') + ' Z'
	);
}
