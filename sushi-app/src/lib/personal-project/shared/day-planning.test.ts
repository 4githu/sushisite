import { describe, it, expect } from 'vitest';
import { positionDay, validBlocks, clockLabel } from './day-planning';
import type { CalendarEvent } from './types';
const event = (id: number, start: string, end: string) =>
	({
		id,
		title: '일정 ' + id,
		startTime: '2026-11-16T' + start + ':00',
		endTime: '2026-11-16T' + end + ':00',
		status: 'passive',
		isAllDay: false,
		type: 'personal'
	}) as CalendarEvent;
describe('daily time planning', () => {
	it('uses actual duration and separate lanes for overlapping appointments and plans', () => {
		const p = positionDay(
			'2026-11-16',
			[event(1, '09:30', '10:45'), event(2, '10:00', '11:00')],
			[{ id: 'p', taskKey: 'event:3', title: '계획', start: 660, duration: 120 }]
		);
		expect(p[0].until - p[0].from).toBe(75 * 60000);
		expect(p[0].columns).toBe(2);
		expect(p[1].lane).not.toBe(p[0].lane);
		expect(p[2].columns).toBe(1);
		expect(p[2].until - p[2].from).toBe(120 * 60000);
	});
	it('clips an overnight appointment at the next-day 02:00 boundary', () => {
		const e = { ...event(1, '23:00', '23:30'), endTime: '2026-11-17T03:00:00' };
		const p = positionDay('2026-11-16', [e], []);
		expect(p[0].until - p[0].from).toBe(3 * 3600000);
		expect(clockLabel(1530)).toBe('익일 01:30');
	});
	it('does not turn an undated task or deadline into occupied time', () => {
		expect(
			positionDay(
				'2026-11-16',
				[{ ...event(1, '00:00', '23:59'), status: 'todo', taskUnplanned: true }],
				[]
			)
		).toHaveLength(0);
	});
	it('rejects malformed and out-of-range stored plans', () => {
		expect(
			validBlocks([
				{ id: 'x', taskKey: 'event:1', title: 'a', start: 1500, duration: 60 },
				{ id: 'bad', taskKey: 'event:1', title: 'b', start: 1500, duration: 90 },
				{ id: 'bad2', taskKey: 'event:1', title: 'b', start: 500, duration: -1 }
			])
		).toHaveLength(1);
	});
});
