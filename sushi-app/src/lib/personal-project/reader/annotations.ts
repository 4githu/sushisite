export type ReaderRect = { x: number; y: number; width: number; height: number };
export type ReaderAnnotation = {
	id: string;
	page: number;
	kind: 'highlight' | 'region';
	rects: ReaderRect[];
	text: string;
};

export function relativeRect(rect: DOMRect, page: DOMRect): ReaderRect {
	const left = Math.max(page.left, rect.left),
		top = Math.max(page.top, rect.top);
	const right = Math.min(page.right, rect.right),
		bottom = Math.min(page.bottom, rect.bottom);
	return {
		x: (left - page.left) / page.width,
		y: (top - page.top) / page.height,
		width: Math.max(0, right - left) / page.width,
		height: Math.max(0, bottom - top) / page.height
	};
}
