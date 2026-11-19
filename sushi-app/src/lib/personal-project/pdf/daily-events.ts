import type { CalendarEvent } from '../shared/types';

export function dailyEventLayout(events: CalendarEvent[], date: string) {
	const start = new Date(`${date}T08:00:00`).getTime();
	const end = start + 18 * 3600000;
	const rows = events
		.filter((e) => !e.isAllDay)
		.map((event) => ({
			event,
			start: Math.max(start, new Date(event.startTime).getTime()),
			end: Math.min(
				end,
				new Date(event.endTime || event.startTime).getTime() + (event.endTime ? 0 : 30 * 60000)
			),
			column: 0,
			columns: 1
		}))
		.filter((e) => e.end > e.start)
		.sort((a, b) => a.start - b.start || a.end - b.end);
	let group: typeof rows = [],
		until = 0;
	const finish = () => {
		const count = Math.max(1, ...group.map((e) => e.column + 1));
		group.forEach((e) => (e.columns = count));
		group = [];
	};
	for (const row of rows) {
		if (row.start >= until) finish();
		const taken = new Set(group.filter((e) => e.end > row.start).map((e) => e.column));
		while (taken.has(row.column)) row.column++;
		group.push(row);
		until = Math.max(until, row.end);
	}
	finish();
	return rows.map((r) => ({
		...r,
		x: 44 + (r.column * 364) / r.columns,
		y: 22 + (((r.start - start) / 60000) * 2) / 3,
		width: 364 / r.columns - 3,
		height: Math.max(8, (((r.end - r.start) / 60000) * 2) / 3)
	}));
}
