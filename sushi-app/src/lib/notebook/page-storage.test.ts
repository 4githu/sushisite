import { it, expect } from 'vitest';
import { packPage, unpackPage } from './page-storage';
it('round trips a textbook page with Korean text and bounds every API chunk', async () => {
	const items = Array.from({ length: 1400 }, (_, i) => ({
		id: String(i),
		kind: 'stroke',
		points: Array.from({ length: 80 }, (_, j) => ({
			x: Math.sin(i + j) * 600,
			y: (i + j) % 800,
			p: 0.5
		}))
	}));
	const data = [...items, { id: 'text', kind: 'text', html: '<p>한글 수식과 메모</p>' }];
	const packed = await packPage(data);
	expect(
		packed.chunks.every(
			(c) => new TextEncoder().encode(JSON.stringify({ blob: c })).length < 500000
		)
	).toBe(true);
	expect(await unpackPage(packed.chunks)).toEqual(data);
});
it('produces stable content keys for unchanged pages', async () => {
	const data = [{ id: '1', text: '내용' }];
	expect((await packPage(data)).hash).toBe((await packPage(data)).hash);
});
