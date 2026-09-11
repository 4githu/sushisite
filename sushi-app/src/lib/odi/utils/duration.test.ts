import { describe, expect, it } from 'vitest';
import { minutesToSeconds, secondsToMinutes } from './duration';

describe('duration conversion', () => {
	it('converts decimal minutes to seconds', () => {
		expect(minutesToSeconds(2.5)).toBe(150);
		expect(minutesToSeconds(2.05)).toBe(123);
	});

	it('converts seconds to decimal minutes rounded to two places', () => {
		expect(secondsToMinutes(30)).toBe(0.5);
		expect(secondsToMinutes(59)).toBe(0.98);
		expect(secondsToMinutes(125)).toBe(2.08);
	});
});
