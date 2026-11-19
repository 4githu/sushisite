import { describe, it, expect, vi, beforeEach } from 'vitest';
vi.mock('./api', () => ({
	request: vi.fn(),
	PersonalApiError: class extends Error {
		status: number;
		constructor(s: number) {
			super();
			this.status = s;
		}
	}
}));
import { request, PersonalApiError } from './api';
import { addCapture, moveCapture, localDay, type Capture } from './capture';
const req = vi.mocked(request);
beforeEach(() => {
	vi.resetAllMocks();
	vi.stubGlobal('window', { dispatchEvent: vi.fn() });
});
describe('private captures', () => {
	it('uses local calendar date rather than UTC', () => {
		const d = new Date(2026, 10, 16, 0, 1);
		expect(localDay(d)).toBe('2026-11-16');
	});
	it('retries a conflicting revision with current records without losing another tab', async () => {
		req
			.mockResolvedValueOnce({ revision: 1, data: { items: [] } })
			.mockRejectedValueOnce(new PersonalApiError(409, 'conflict'))
			.mockResolvedValueOnce({ revision: 2, data: { items: [{ id: 'other', text: '다른 화면' }] } })
			.mockResolvedValueOnce({ revision: 3 });
		const items = await addCapture('fixed', '새 기록');
		expect(items.map((x) => x.id)).toEqual(['other', 'fixed']);
		expect(req.mock.calls[3][1]?.body).toMatchObject({
			revision: 2,
			data: {
				items: expect.arrayContaining([
					expect.objectContaining({ id: 'fixed', kind: 'inbox', today: null })
				])
			}
		});
	});
	it('does not duplicate a capture when retrying after a lost response', async () => {
		const saved = { id: 'same', text: '기록' };
		req
			.mockResolvedValueOnce({ revision: 1, data: { items: [saved] } })
			.mockResolvedValueOnce({ revision: 2 });
		const items = await addCapture('same', '기록');
		expect(items).toHaveLength(1);
	});
	it('reorders only selected unfinished tasks without changing deadlines or other records', async () => {
		const records = [
			{ id: 'a', today: '2026-11-16', done: false },
			{ id: 'other', today: null, done: false },
			{ id: 'b', today: '2026-11-16', done: false }
		] as Capture[];
		req
			.mockResolvedValueOnce({ revision: 1, data: { items: records } })
			.mockResolvedValueOnce({ revision: 2 });
		const next = await moveCapture('b', -1, '2026-11-16');
		expect(next.map((x) => x.id)).toEqual(['b', 'other', 'a']);
		expect(next[1]).toEqual(records[1]);
	});
});
