import { expect, it } from 'vitest';
import { academicSlot, type Term } from './catalog';
it('maps actual terms to cohort slots with a separate leave offset', () => {
	const term = { year: '2026', term: 'U000200001U000300001' } as Term;
	expect(academicSlot(term, 2026)).toBe('1-1');
	expect(academicSlot({ ...term, term: 'U000200002U000300001' }, 2026)).toBe('1-2');
	expect(academicSlot({ ...term, year: '2027' }, 2026, 1)).toBe('1-2');
	expect(academicSlot({ ...term, year: '2025' }, 2026)).toBe('');
});
