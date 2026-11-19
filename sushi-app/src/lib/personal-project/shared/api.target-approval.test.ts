import { afterEach, expect, test, vi } from 'vitest';
import { PersonalApiError, personalApi, targetRepricingPreview } from './api';

afterEach(() => vi.unstubAllGlobals());

const proposal = { code: 'repricing_approval_required', changes: [{ roundId: 12, oldAmount: 30000, newAmount: 40000, delta: 10000, paid: true, hasSnapshot: true }] };

test('학생 추가는 서버가 제안한 정확한 금액 쌍만 승인 payload로 보낸다', async () => {
 const fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 201 }));
 vi.stubGlobal('fetch', fetch);
 await personalApi.addRoundTarget(12, '합성 학생', [30000, 40000]);
 expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', body: JSON.stringify({ student_name: '합성 학생', approved_price_change: [30000, 40000] }) });
});

test('학생 삭제는 항상 confirm=true이고 승인 쌍은 query로 전달한다', async () => {
 const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
 vi.stubGlobal('fetch', fetch);
 await personalApi.deleteRoundTarget(15);
 await personalApi.deleteRoundTarget(15, [30000, 40000]);
 expect(fetch.mock.calls[0][0]).toContain('/aura/targets/15?confirm=true');
 expect(fetch.mock.calls[1][0]).toContain('confirm=true&approved_old_amount=30000&approved_new_amount=40000');
});

test('재가격 제안만 승인 대상으로 추출하며 일반 409는 제외한다', () => {
 expect(targetRepricingPreview(new PersonalApiError(409, '승인', proposal.code, proposal), 12)).toEqual(proposal.changes[0]);
 expect(targetRepricingPreview(new PersonalApiError(409, '리포트가 있는 학생은 제거할 수 없습니다.'), 12)).toBeNull();
 expect(targetRepricingPreview(new PersonalApiError(409, '승인', proposal.code, proposal), 13)).toBeNull();
 expect(targetRepricingPreview(new PersonalApiError(409, '승인', proposal.code, { changes: [null] }), 12)).toBeNull();
 expect(targetRepricingPreview(new PersonalApiError(409, '승인', proposal.code, { changes: [{ ...proposal.changes[0], delta: 1 }] }), 12)).toBeNull();
});

test('첨부 업로드는 원본 파일과 MIME을 쿠키 포함 요청으로 보존한다', async () => {
 const file = new File(['image'], 'synthetic.png', { type: 'image/png' });
 const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 4, kind: 'blank_test', name: 'synthetic.png', mimeType: 'image/png' })));
 vi.stubGlobal('fetch', fetch);
 await expect(personalApi.uploadTargetReportAttachment(15, 'blank_test', file)).resolves.toMatchObject({ id: 4 });
 expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', credentials: 'include', body: file, headers: { 'Content-Type': 'image/png' } });
});

test('첨부 401은 인증 무효화, fetch 거부는 backend_unreachable로 분류한다', async () => {
 const window = new EventTarget();
 const listener = vi.fn();
 window.addEventListener('personal-auth-invalid', listener);
 vi.stubGlobal('window', window);
 const file = new File(['image'], 'synthetic.png', { type: 'image/png' });
 vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
 await expect(personalApi.uploadTargetReportAttachment(15, 'blank_test', file)).rejects.toMatchObject({ status: 401, code: 'authentication_required' });
 expect(listener).toHaveBeenCalledOnce();
 vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
 await expect(personalApi.uploadTargetReportAttachment(15, 'blank_test', file)).rejects.toMatchObject({ status: 0, code: 'backend_unreachable' });
 expect(listener).toHaveBeenCalledOnce();
});
