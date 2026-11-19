export type RepeatUnit = 'day' | 'week' | 'month';
export function occurrence(start: Date, index: number, interval: number, unit: RepeatUnit): Date {
	const date = new Date(start);
	if (unit === 'month') {
		const day = date.getDate();
		date.setDate(1);
		date.setMonth(date.getMonth() + index * interval);
		date.setDate(Math.min(day, new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate()));
	} else date.setDate(date.getDate() + index * interval * (unit === 'week' ? 7 : 1));
	return date;
}
export function repeatCount(start: Date, until: Date, interval: number, unit: RepeatUnit) {
	let count = 0;
	while (count < 365 && occurrence(start, count, interval, unit) <= until) count++;
	return count;
}
