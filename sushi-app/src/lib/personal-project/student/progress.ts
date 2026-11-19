export type CourseProgress = { planned: string[]; completed: string[] };
export const courseKey = (code: string) => code.trim().toUpperCase();
export function courseState(progress: CourseProgress, code: string) {
	const key = courseKey(code);
	return progress.completed.includes(key)
		? 'completed'
		: progress.planned.includes(key)
			? 'planned'
			: 'unplanned';
}
