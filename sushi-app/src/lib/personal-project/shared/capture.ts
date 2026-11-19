import { request, PersonalApiError } from './api';
export type Capture = {
	id: string;
	text: string;
	createdAt: string;
	kind: 'inbox' | 'task' | 'note';
	today: string | null;
	done: boolean;
};
export const captureKey = '/documents/netaq-captures-v1';
type Document = { revision: number; data: { items: Capture[] } | null };
export function localDay(d = new Date()) {
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
export async function readCaptures() {
	const doc = await request<Document>(captureKey);
	return doc.data?.items || [];
}
// Every mutation starts with the latest owner-scoped document. A repeated capture ID is a no-op.
export async function changeCaptures(change: (items: Capture[]) => Capture[]) {
	for (let attempt = 0; attempt < 3; attempt++) {
		const doc = await request<Document>(captureKey);
		const items = change(doc.data?.items || []);
		try {
			await request(captureKey, {
				method: 'PUT',
				body: { revision: doc.revision, data: { items } }
			});
			window.dispatchEvent(new Event('netaq-captures-changed'));
			return items;
		} catch (e) {
			if (!(e instanceof PersonalApiError) || e.status !== 409 || attempt === 2) throw e;
		}
	}
	throw new Error('다른 화면의 변경을 불러온 뒤 다시 시도해 주세요.');
}
export async function addCapture(id: string, text: string) {
	const value = text.trim();
	if (!value) throw new Error('기록할 내용을 입력해 주세요.');
	if (value.length > 2000) throw new Error('기록은 2,000자 이내로 입력해 주세요.');
	return changeCaptures((items) =>
		items.some((i) => i.id === id)
			? items
			: [
					...items,
					{
						id,
						text: value,
						createdAt: new Date().toISOString(),
						kind: 'inbox',
						today: null,
						done: false
					}
				]
	);
}
export async function updateCapture(
	id: string,
	patch: Partial<Pick<Capture, 'kind' | 'today' | 'done' | 'text'>>
) {
	if (patch.text !== undefined) {
		const text = patch.text.trim();
		if (!text || text.length > 2000) throw new Error('기록은 1~2,000자로 입력해 주세요.');
		patch = { ...patch, text };
	}
	return changeCaptures((items) => items.map((i) => (i.id === id ? { ...i, ...patch } : i)));
}
export async function deleteCapture(id: string) {
	return changeCaptures((items) => items.filter((i) => i.id !== id));
}
export async function moveCapture(id: string, direction: -1 | 1, day: string) {
	return changeCaptures((items) => {
		const next = [...items];
		const positions = next
			.map((i, n) => (i.today === day && !i.done ? n : -1))
			.filter((i) => i >= 0);
		const from = positions.findIndex((p) => next[p].id === id),
			to = from + direction;
		if (from >= 0 && to >= 0 && to < positions.length) {
			[next[positions[from]], next[positions[to]]] = [next[positions[to]], next[positions[from]]];
		}
		return next;
	});
}
