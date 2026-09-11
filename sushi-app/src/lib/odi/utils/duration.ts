const DECIMAL_PLACES = 2;
const SCALE = 10 ** DECIMAL_PLACES;

export type DurationUnit = 'minutes' | 'seconds';

export function roundDuration(value: number): number {
	if (!Number.isFinite(value)) return 0;
	return Math.round((value + Number.EPSILON) * SCALE) / SCALE;
}

export function minutesToSeconds(minutes: number): number {
	return roundDuration(minutes * 60);
}

export function secondsToMinutes(seconds: number): number {
	return roundDuration(seconds / 60);
}

export function formatDurationInput(value: number): string {
	return String(roundDuration(value));
}

export function formatDurationMinutes(minutes: number): string {
	return `${formatDurationInput(minutes)}분`;
}
