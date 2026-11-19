import { beforeEach, describe, expect, it, vi } from 'vitest';

const harness = vi.hoisted(() => ({
	draft: null as any,
	writes: [] as Array<{ path: string; payload: any }>,
	failPublish: false,
	beforePublish: null as (() => void) | null
}));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/config/api', () => ({ API_BASE: 'https://backend.test' }));
vi.mock('./odiuser', () => ({ odiuser: { get: () => ({ user_id: 'owner' }) } }));
vi.mock('./template', () => ({ template: {
	get: () => harness.draft,
	set: (value: any) => { harness.draft = value; }
} }));
vi.mock('firebase/storage', () => ({
	ref: (_: unknown, path: string) => path,
	uploadBytes: vi.fn(async () => undefined),
	getDownloadURL: async (path: string) => `https://storage.test/${path}`
}));
vi.mock('firebase/database', () => ({
	ref: (_: unknown, path: string) => path,
	set: async (path: string, payload: any) => {
		harness.beforePublish?.();
		if (harness.failPublish) throw new Error('publish failed');
		harness.writes.push({ path, payload });
	},
	remove: vi.fn(), update: vi.fn(), onValue: vi.fn()
}));
vi.mock('$lib/firebase/client', () => ({ firebaseDatabase: () => ({}), firebaseStorage: () => ({}) }));

import { session } from './session';

let requests: Array<{ url: string; body: any }>;
beforeEach(() => {
	session.clear();
	harness.writes = [];
	harness.failPublish = false;
	harness.beforePublish = null;
	harness.draft = {
		type: 'presentation',
		environment: { title: 'Selected presentation', language: '한국어', duration_minutes: 3 },
		audience: { audience_count: 3, expertise_level: '중간', interest_level: '높음' },
		files: { slide: { storage_path: 'storage/odi/users/owner/slides.pdf' } }
	};
	requests = [];
	vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
		if (url.includes('/odi/files/read')) return new Response('PDF');
		const body = JSON.parse(options?.body as string);
		requests.push({ url, body });
		if (url.endsWith('/state')) return Response.json({ pre_session: { pin_code: '8732', state: 'cancelled' } });
		return Response.json({
			pin_code: '8732', pre_session: { pin_code: '8732', state: 'waiting', session_id: null },
			template: { template: structuredClone(body.template) }
		});
	}));
});

describe.each(['experience', 'regular'])('%s Unity handoff', (mode) => {
	it.each(Array.from({ length: 10 }, (_, i) => i + 1))('preserves %i listeners in PIN and Firebase', async (count) => {
		harness.draft.audience.audience_count = count;
		harness.beforePublish = () => expect(session.get().pin_code).toBeNull();
		if (mode === 'experience') await session.startExperiencePresentation();
		else await session.startFromCurrentTemplate();
		expect(requests).toHaveLength(1);
		expect(requests[0].body.template.audience.audience_count).toBe(count);
		expect(requests[0].body.template.environment.title).toBe('Selected presentation');
		expect(harness.writes[0].path).toBe('presentation_data/8732');
		expect(harness.writes[0].payload.page_3.audience_scale).toBe(count);
		expect(harness.writes[0].payload.status).toBe('ready');
		expect(session.get().pin_code).toBe('8732');
		expect(session.get().pre_session?.state).toBe('waiting');
		expect(requests.some((r) => r.url.endsWith('/finish'))).toBe(false);
	});
});

it('does not display a usable PIN if Firebase publishing fails', async () => {
	harness.failPublish = true;
	await expect(session.startExperiencePresentation()).rejects.toThrow('publish failed');
	expect(session.get().pin_code).toBeNull();
	expect(requests.at(-1)?.body.state).toBe('cancelled');
});

it('uses a new request ID when the user clears and regenerates the PIN', async () => {
	await session.startExperiencePresentation();
	const first = requests[0].body.request_id;
	session.clear();
	await session.startExperiencePresentation();
	expect(requests[1].body.request_id).not.toBe(first);
});
