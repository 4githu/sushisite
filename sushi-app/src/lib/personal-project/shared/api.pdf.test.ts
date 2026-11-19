import { afterEach, expect, test, vi } from 'vitest';
import { PersonalApiError, personalApi } from './api';

afterEach(() => vi.unstubAllGlobals());

test('PDF 응답을 blob으로 받고 쿠키 및 no-store 요청을 유지한다', async () => {
	const pdf = new Blob(['%PDF-1.7'], { type: 'application/pdf' });
	const fetch = vi.fn().mockResolvedValue(new Response(pdf));
	vi.stubGlobal('fetch', fetch);
	expect(await personalApi.targetReportPdf(42)).toEqual(pdf);
	expect(fetch).toHaveBeenCalledWith(
		expect.stringContaining('/aura/targets/42/report.pdf'),
		expect.objectContaining({ credentials: 'include', cache: 'no-store' })
	);
});

test('PDF 401은 인증 무효 이벤트를 알리고 인증 오류로 분류한다', async () => {
	const window = new EventTarget();
	const listener = vi.fn();
	window.addEventListener('personal-auth-invalid', listener);
	vi.stubGlobal('window', window);
	vi.stubGlobal(
		'fetch',
		vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: '만료' }), { status: 401 }))
	);
	await expect(personalApi.targetReportPdf(42)).rejects.toMatchObject({
		status: 401,
		code: 'authentication_required'
	});
	expect(listener).toHaveBeenCalledOnce();
});

test('PDF 네트워크 실패는 연결 오류로 분류하며 인증 무효 이벤트를 보내지 않는다', async () => {
	const window = new EventTarget();
	const listener = vi.fn();
	window.addEventListener('personal-auth-invalid', listener);
	vi.stubGlobal('window', window);
	vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
	await expect(personalApi.targetReportPdf(42)).rejects.toMatchObject({
		status: 0,
		code: 'backend_unreachable'
	});
	expect(listener).not.toHaveBeenCalled();
});

test('PDF 서버 오류의 detail과 code를 보존한다', async () => {
	vi.stubGlobal(
		'fetch',
		vi
			.fn()
			.mockResolvedValue(
				new Response(JSON.stringify({ detail: { code: 'pdf_failed', message: 'PDF 생성 실패' } }), {
					status: 422
				})
			)
	);
	await expect(personalApi.targetReportPdf(42)).rejects.toMatchObject({
		status: 422,
		code: 'pdf_failed',
		message: 'PDF 생성 실패'
	});
});
