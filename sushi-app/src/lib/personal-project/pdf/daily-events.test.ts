import { describe, expect, it } from 'vitest';
import { dailyEventLayout } from './daily-events';
import type { CalendarEvent } from '../shared/types';

const event = (id: number, start: string, end: string | null) =>
	({ id, title: '일정', startTime: start, endTime: end, isAllDay: false }) as CalendarEvent;
describe('daily events on the drawing paper', () => {
	it('clips early and following-day events to 08:00–02:00', () => {
		const rows = dailyEventLayout(
			[
				event(1, '2026-10-01T07:30:00', '2026-10-01T09:00:00'),
				event(2, '2026-10-02T01:00:00', '2026-10-02T03:00:00'),
				event(3, '2026-10-01T02:00:00', '2026-10-01T03:00:00')
			],
			'2026-10-01'
		);
		expect(rows.map((r) => [r.event.id, r.y, r.height])).toEqual([
			[1, 22, 40],
			[2, 702, 40]
		]);
	});
	it('separates overlapping events but reuses the full width for touching events', () => {
		const rows = dailyEventLayout(
			[
				event(1, '2026-10-01T09:00:00', '2026-10-01T10:00:00'),
				event(2, '2026-10-01T09:30:00', '2026-10-01T10:00:00'),
				event(3, '2026-10-01T10:00:00', '2026-10-01T11:00:00')
			],
			'2026-10-01'
		);
		expect(rows.map((r) => r.columns)).toEqual([2, 2, 1]);
		expect(rows[1].x).toBeGreaterThan(rows[0].x + rows[0].width);
	});
	it('gives open-ended events 30 minutes and excludes all-day or invalid dates', () => {
		const rows = dailyEventLayout(
			[
				event(1, '2026-10-01T15:00:00', null),
				{ ...event(2, '2026-10-01T00:00:00', null), isAllDay: true },
				event(3, 'invalid', null)
			],
			'2026-10-01'
		);
		expect(rows).toHaveLength(1);
		expect(rows[0].height).toBe(20);
	});
});
