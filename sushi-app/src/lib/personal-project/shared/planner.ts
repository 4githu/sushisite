import type { CalendarEvent } from './types';

export function taskDeadline(event: CalendarEvent) {
	return event.taskDueAt || event.endTime || event.startTime;
}
export function taskWaiting(event: CalendarEvent, at = Date.now()) {
	return Boolean(event.taskAvailableFrom && +new Date(event.taskAvailableFrom) > at);
}
export function taskTiming(event: CalendarEvent) {
	const date = (value: string) => new Date(value).toLocaleString('ko-KR', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
	return `${event.taskAvailableFrom ? date(event.taskAvailableFrom) + '부터 · ' : ''}${date(taskDeadline(event))} 마감`;
}

export function categoryPaths(value: string | null | undefined): string[] {
	return [
		...new Set(
			(value || '')
				.split(',')
				.map((path) =>
					path
						.split('>')
						.map((part) => part.trim())
						.filter(Boolean)
						.join(' > ')
				)
				.filter(Boolean)
		)
	];
}
export function eventCategories(event: CalendarEvent): string[] {
	return categoryPaths(event.categoryName).length
		? categoryPaths(event.categoryName)
		: [event.type === 'aura' ? '아우라' : event.type === 'google' ? 'Google' : '개인'];
}
export function categoryHidden(event: CalendarEvent, hidden: string[]): boolean {
	return eventCategories(event).every((path) =>
		hidden.some((h) => path === h || path.startsWith(h + ' > '))
	);
}
export function safeEventUrl(url?: string | null): string | null {
	return url && !/[\s\\]/.test(url) && (/^https?:\/\//i.test(url) || /^\/(?!\/)/.test(url))
		? url
		: null;
}


export type CalendarProject = { id: number; name: string; parent_id?: number | null; isolate_tasks?: number | boolean };
export function inProject(event: CalendarEvent, selected: string, projects: CalendarProject[]) {
    if (selected === 'all') return true;
    if (!selected) return !event.projectId;
    let id = event.projectId;
    const seen = new Set<number>();
    while (id && !seen.has(id)) {
        if (String(id) === selected) return true;
        seen.add(id);
        id = projects.find(p => p.id === id)?.parent_id;
    }
    return false;
}
export function isolatedProject(event: CalendarEvent, projects: CalendarProject[]): string | null {
    let id = event.projectId;
    const seen = new Set<number>();
    let isolated: CalendarProject | undefined;
    while (id && !seen.has(id)) {
        seen.add(id);
        const project = projects.find(p => p.id === id);
        if (project?.isolate_tasks) isolated = project;
        id = project?.parent_id;
    }
    return isolated ? `프로젝트 · ${isolated.name}` : event.type === 'aura' ? '아우라' : null;
}
export function taskGroups(tasks: CalendarEvent[], projects: CalendarProject[], mode: 'time' | 'theme') {
    const groups = new Map<string, { name: string; isolated: boolean; tasks: CalendarEvent[] }>();
    for (const event of [...tasks].sort((a,b) => +new Date(taskDeadline(a)) - +new Date(taskDeadline(b)) || a.id - b.id)) {
        const isolated = isolatedProject(event, projects);
        const name = isolated || (mode === 'theme' ? eventCategories(event)[0] : '시간순');
        const key = `${Boolean(isolated)}:${name}`;
        if (!groups.has(key)) groups.set(key, { name, isolated: Boolean(isolated), tasks: [] });
        groups.get(key)!.tasks.push(event);
    }
    return [...groups.values()].sort((a,b) => Number(a.isolated) - Number(b.isolated));
}

export function readTaskMode(): 'time' | 'theme' {
    try { return localStorage.getItem('ondo.task-mode') === 'theme' ? 'theme' : 'time'; } catch { return 'time'; }
}
export function saveTaskMode(mode: 'time' | 'theme') {
    try { localStorage.setItem('ondo.task-mode', mode); } catch { /* optional preference */ }
}
