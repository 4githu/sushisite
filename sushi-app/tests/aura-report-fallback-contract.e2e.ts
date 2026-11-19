import { expect, test } from '@playwright/test';

// All requests are local or synthetic; no Kakao or live API access is allowed.
test('fallback displays image delivery to self and allows resend', async ({ page }) => {
  const base = test.info().project.use.baseURL;
  if (typeof base !== 'string' || !['localhost', '127.0.0.1'].includes(new URL(base).hostname)) throw new Error('local base URL required');
  const report = {
    id: 91, targetId: 37, studentName: '합성 학생', schoolId: 11, schoolName: '합성 학교',
    progressStage: 'grade1_semester1_midterm', roundNumber: 1, roundNumbers: [1], roundLabel: '합성 1회차',
    startTime: '2026-11-01T10:00:00', endTime: '2026-11-01T11:00:00', templateVersion: 1,
    contentJson: { version: 1, documentId: 'synthetic', createdAt: '2026-11-01T00:00:00Z', updatedAt: '2026-11-01T00:00:00Z', blocks: [{ id: 'p', type: 'paragraph', children: [{ type: 'text', text: '합성' }] }] },
    analysisJson: {}, sourceNotes: '', questionChecks: {}, lectureProgress: 5, lectureComprehension: 5, memoryBefore: 4, memoryAfter: 5, assessmentJson: null,
    generatedReportJson: { schemaVersion: 'aura.clinic-report-output.v2', target: { label: '합성' }, assessment: null, learningContent: { paragraphs: ['합성 내용'] }, problemSolvingNote: '' },
    aiModel: null, clinicTargets: [{ id: 37, studentName: '합성 학생', status: 'draft' }], status: 'draft', submittedAt: null
  };
  let sends = 0;
  const unexpected: string[] = [];
  await page.route('**/*', async route => {
    const req = route.request(); const url = new URL(req.url()); const p = url.pathname; const m = req.method();
    if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') return route.abort();
    if (p.endsWith('/api/personal/boards') && m === 'GET') return route.fulfill({ json: { canAdmin: false } });
    if (p === '/auth/isjwt' && m === 'GET') return route.fulfill({ json: { sub: 'synthetic', data: { id: 'synthetic', name: '합성 사용자', email: 'synthetic@example.invalid' }, exp: 9999999999 } });
    if (p.endsWith('/aura/targets/37/report') && m === 'GET') return route.fulfill({ json: report });
    if (p.endsWith('/aura/targets/37/attachments') && m === 'GET') return route.fulfill({ json: [] });
    if (p.endsWith('/aura/ai/models') && m === 'GET') return route.fulfill({ json: { defaultModel: '', models: [] } });
    if (p.endsWith('/aura/targets/37/ai-reports') && m === 'GET') return route.fulfill({ json: { targetId: 37, results: [] } });
    if (p.endsWith('/aura/targets/37/kakao-clinic/scheduled-deliveries') && m === 'GET') return route.fulfill({ json: null });
    if (p.endsWith('/aura/kakao-self/status') && m === 'GET') return route.fulfill({ json: { enabled: true, destination: '나와의 채팅', maxPages: 1 } });
    if (p.endsWith('/aura/target-reports/91') && m === 'PATCH') return route.fulfill({ json: report });
    if (p.endsWith('/aura/targets/37/kakao-clinic/send-report') && m === 'POST') {
      sends++; return route.fulfill({ json: { sent: true, sentCount: 1, deliveryStatus: 'verified', deliveryFormat: 'images', destination: '본계정', fallbackReason: 'both_rooms_confirmed_absent' } });
    }
    if (url.origin !== new URL(base).origin || p.startsWith('/api/') || p.startsWith('/auth/') || m !== 'GET') { unexpected.push(`${m} ${p}`); return route.abort(); }
    return route.continue();
  });
  await page.goto('/personal-project/aura/reports/37');
  await expect(page.getByRole('heading', { name: '합성 학생', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '카카오톡으로 받기' }).click();
  await expect(page.getByText('본계정에 리포트 이미지 1장을 대체 전송했습니다. 학생 방에는 발송되지 않았습니다.')).toBeVisible();
  expect(sends).toBe(1);
  const resend = page.getByRole('button', { name: '카카오톡으로 받기' });
  await expect(resend).toBeEnabled();
  await resend.click();
  await expect.poll(() => sends).toBe(2);
  expect(unexpected).toEqual([]);
});
