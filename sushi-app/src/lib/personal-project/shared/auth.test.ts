import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { checkPersonalAuth, invalidatePersonalAuth, logoutPersonal } from './auth';
const user = { sub: '1', data: { id: '1' }, exp: Math.floor(Date.now() / 1000) + 3600 };
beforeEach(() => {
	invalidatePersonalAuth();
	vi.stubGlobal('window', new EventTarget());
	vi.stubGlobal('localStorage', { setItem: vi.fn() });
});
afterEach(() => vi.unstubAllGlobals());
it('coalesces concurrent checks and caches only a successful short-lived result', async () => {
	const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(user)));
	vi.stubGlobal('fetch', fetcher);
	const results = await Promise.all([checkPersonalAuth(), checkPersonalAuth()]);
	expect(results).toEqual([user, user]);
	expect(await checkPersonalAuth()).toEqual(user);
	expect(fetcher).toHaveBeenCalledTimes(1);
});
it('does not cache network failures or unauthorized responses', async () => {
	const fetcher = vi
		.fn()
		.mockRejectedValueOnce(new Error('offline'))
		.mockResolvedValueOnce(new Response('', { status: 401 }))
		.mockResolvedValueOnce(new Response(JSON.stringify(user)));
	vi.stubGlobal('fetch', fetcher);
	await expect(checkPersonalAuth()).rejects.toThrow();
	expect(await checkPersonalAuth()).toBeNull();
	expect(await checkPersonalAuth()).toEqual(user);
	expect(fetcher).toHaveBeenCalledTimes(3);
});
it('prevents an in-flight check from restoring a logged-out identity', async () => {
	let resolve!: (response: Response) => void;
	vi.stubGlobal(
		'fetch',
		vi
			.fn()
			.mockImplementationOnce(() => new Promise<Response>((r) => (resolve = r)))
			.mockResolvedValueOnce(new Response('{}'))
	);
	const pending = checkPersonalAuth();
	await logoutPersonal();
	resolve(new Response(JSON.stringify(user)));
	expect(await pending).toBeNull();
});
