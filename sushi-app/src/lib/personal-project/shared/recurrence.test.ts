import { it, expect } from 'vitest';
import { occurrence, repeatCount } from './recurrence';
it('keeps month-end intent without drifting after February', () => {
	const start = new Date(2028, 0, 31, 10);
	expect(occurrence(start, 1, 1, 'month').getDate()).toBe(29);
	expect(occurrence(start, 2, 1, 'month').getDate()).toBe(31);
});
it('includes the final selected day and honors non-weekly intervals', () => {
	const start = new Date(2026, 10, 16, 9);
	expect(repeatCount(start, new Date(2026, 10, 20, 23, 59), 2, 'day')).toBe(3);
	expect(repeatCount(start, new Date(2026, 11, 31), 2, 'week')).toBe(4);
});
