import { request, PersonalApiError } from './api';
import { verifiedPrivateOwner, samePrivateOwner } from './private-owner';
import type { CalendarEvent } from './types';
export type TimeBlock = {
	id: string;
	taskKey: string;
	title: string;
	start: number;
	duration: number;
};
export const planPath = (date: string) => `/documents/netaq-time-plan-v1:${date}`;
export function clockLabel(minute: number) {
	return `${minute >= 1440 ? '익일 ' : ''}${String(Math.floor(minute / 60) % 24).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;
}
export function validBlocks(value: unknown): TimeBlock[] {
	if (!Array.isArray(value)) return [];
	return value.filter((b): b is TimeBlock =>
		Boolean(
			b &&
			typeof b.id === 'string' &&
			typeof b.taskKey === 'string' &&
			typeof b.title === 'string' &&
			Number.isInteger(b.start) &&
			Number.isInteger(b.duration) &&
			b.start >= 480 &&
			b.duration >= 15 &&
			b.start + b.duration <= 1560
		)
	);
}
export async function readPlan(date: string) {
	const doc = await request<{ revision: number; data: { blocks?: TimeBlock[] } | null }>(
		planPath(date)
	);
	return validBlocks(doc.data?.blocks);
}
export async function changePlan(date: string, change: (blocks: TimeBlock[]) => TimeBlock[]) {
	const account = await verifiedPrivateOwner();
	for (let attempt = 0; attempt < 3; attempt++) {
		const doc = await request<{ revision: number; data: { blocks?: TimeBlock[] } | null }>(
			planPath(date)
		);
		if (!(await samePrivateOwner(account)))
			throw new Error('계정이 바뀌었어요. 다시 연결해주세요.');
		const blocks = change(validBlocks(doc.data?.blocks));
		if (validBlocks(blocks).length !== blocks.length)
			throw new Error('계획 시간은 오전 8시부터 다음 날 오전 2시 사이로 정해주세요.');
		try {
			await request(planPath(date), {
				method: 'PUT',
				body: { revision: doc.revision, data: { blocks } }
			});
			return blocks;
		} catch (e) {
			if (!(e instanceof PersonalApiError) || e.status !== 409 || attempt === 2) throw e;
		}
	}
	throw new Error('다른 화면의 변경을 불러온 뒤 다시 시도해주세요.');
}
export type TimelineItem = {
	key: string;
	title: string;
	from: number;
	until: number;
	event?: CalendarEvent;
	block?: TimeBlock;
	lane: number;
	columns: number;
};
export function positionDay(
	date: string,
	events: CalendarEvent[],
	blocks: TimeBlock[]
): TimelineItem[] {
	const midnight = +new Date(date + 'T00:00:00'),
		from = midnight + 480 * 60000,
		until = midnight + 1560 * 60000;
	const items: TimelineItem[] = [
		...events
			.filter(
				(e) => e.status === 'passive' && !e.isAllDay && !e.timeUnspecified && !e.taskUnplanned
			)
			.map((event) => ({
				key: 'event:' + event.id,
				title: event.title,
				from: +new Date(event.startTime),
				until: event.endTime ? +new Date(event.endTime) : +new Date(event.startTime) + 3600000,
				event,
				lane: 0,
				columns: 1
			})),
		...blocks.map((block) => ({
			key: 'plan:' + block.id,
			title: block.title,
			from: midnight + block.start * 60000,
			until: midnight + (block.start + block.duration) * 60000,
			block,
			lane: 0,
			columns: 1
		}))
	]
		.filter(
			(e) => Number.isFinite(e.from) && Number.isFinite(e.until) && e.from < until && e.until > from
		)
		.map((e) => ({ ...e, from: Math.max(e.from, from), until: Math.min(e.until, until) }))
		.sort((a, b) => a.from - b.from || b.until - a.until);
	let group: TimelineItem[] = [],
		lanes: number[] = [],
		end = 0;
	const finish = () => {
		for (const item of group) item.columns = lanes.length;
	};
	for (const item of items) {
		if (item.from >= end) {
			finish();
			group = [];
			lanes = [];
			end = 0;
		}
		let lane = lanes.findIndex((e) => e <= item.from);
		if (lane < 0) lane = lanes.length;
		item.lane = lane;
		lanes[lane] = Math.max(item.until, item.from + (24 / 64) * 3600000);
		end = Math.max(end, lanes[lane]);
		group.push(item);
	}
	finish();
	return items;
}
