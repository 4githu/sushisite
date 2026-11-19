import { it, expect } from 'vitest';
import { createPaperPage, paperFor, validPaper } from './paper';
it('new paper inserted in a PDF has no PDF source and owns its settings', () => {
	const template = { pattern: 'blank', color: 'black' } as const;
	const a = createPaperPage(template),
		b = createPaperPage(template);
	expect(a.source).toBe(null);
	expect(a.id).not.toBe(b.id);
	expect(a.paper).not.toBe(b.paper);
	expect(a.items).not.toBe(b.items);
	expect(paperFor(a)).toEqual(template);
});
it('legacy pages retain white ruled paper and invalid settings do not enter the renderer', () => {
	expect(paperFor({ w: 794, h: 1123, items: [] })).toEqual({ pattern: 'ruled', color: 'white' });
	expect(validPaper({ pattern: 'script', color: 'red' })).toBe(false);
});
