import { expect, test } from '@playwright/test';
const report = { id:91,targetId:37,studentName:'합성 학생',schoolId:11,schoolName:'합성 학교',progressStage:'grade1_semester1_midterm',roundNumber:1,roundNumbers:[1],roundLabel:'합성',startTime:'2026-11-01T10:00:00',endTime:'2026-11-01T11:00:00',templateVersion:1,contentJson:{version:1,documentId:'synthetic',createdAt:'2026-11-01T00:00:00Z',updatedAt:'2026-11-01T00:00:00Z',blocks:[{id:'p',type:'paragraph',children:[{type:'text',text:'합성'}]}]},analysisJson:{},sourceNotes:'',questionChecks:{},lectureProgress:5,lectureComprehension:5,memoryBefore:4,memoryAfter:5,assessmentJson:null,generatedReportJson:{schemaVersion:'aura.clinic-report-output.v2',target:{label:'합성'},assessment:null,learningContent:{paragraphs:['합성']},problemSolvingNote:''},aiModel:null,clinicTargets:[{id:37,studentName:'합성 학생',status:'draft'}],status:'draft',submittedAt:null};
for (const scenario of ['success','fallback','failure','partial','unknown','lost','missing','pending'] as const) test(`synthetic delivery ${scenario}`, async ({page}) => {
 const base = test.info().project.use.baseURL;
 if (typeof base !== 'string' || !['localhost','127.0.0.1'].includes(new URL(base).hostname)) throw new Error('local only');
 let sends=0, lookups=0, requestId=''; const unexpected:string[]=[];
 await page.route('**/*', async route => {
  const req=route.request(), url=new URL(req.url()), p=url.pathname, m=req.method();
  if (url.hostname==='fonts.googleapis.com'||url.hostname==='fonts.gstatic.com') return route.abort();
  if (p.endsWith('/api/personal/boards') && m==='GET') return route.fulfill({json:{canAdmin:false}});
  if (p==='/auth/isjwt' && m==='GET') return route.fulfill({json:{sub:'synthetic',data:{id:'synthetic',name:'합성',email:'synthetic@example.invalid'},exp:9999999999}});
  if (p.endsWith('/aura/targets/37/report') && m==='GET') return route.fulfill({json:report});
  if (p.endsWith('/aura/targets/37/attachments') && m==='GET') return route.fulfill({json:[]});
  if (p.endsWith('/aura/ai/models') && m==='GET') return route.fulfill({json:{defaultModel:'',models:[]}});
  if (p.endsWith('/aura/targets/37/ai-reports') && m==='GET') return route.fulfill({json:{targetId:37,results:[]}});
  if (p.endsWith('/aura/targets/37/kakao-clinic/scheduled-deliveries') && m==='GET') return route.fulfill({json:null});
  if (p.endsWith('/aura/kakao-self/status') && m==='GET') return route.fulfill({json:{enabled:true,destination:'나와의 채팅',maxPages:1}});
  if (p.endsWith('/aura/target-reports/91') && m==='PATCH') return route.fulfill({json:report});
  if (p.endsWith('/aura/targets/37/kakao-clinic/send-report') && m==='POST') {
   sends++; requestId=req.headers()['x-delivery-request-id'];
   if (scenario==='lost'||scenario==='missing') return route.abort();
   if (scenario==='failure') return route.fulfill({status:409,json:{detail:{deliveryStatus:'not_started',retryable:true}}});
   if (scenario==='partial'||scenario==='unknown') return route.fulfill({status:409,json:{detail:{deliveryStatus:scenario,retryable:false}}});
   const result=scenario==='fallback'?{sent:true,deliveryStatus:'verified',deliveryFormat:'text',destination:'본계정',fallbackReason:'both_rooms_confirmed_absent'}:{sent:true,deliveryStatus:'verified',destination:'합성 대상',deliveryFormat:'images',sentCount:1,completionStatus:scenario==='pending'?'pending':'completed'};
   return route.fulfill(scenario==='pending'?{status:409,json:{detail:result}}:{json:result});
  }
  if (p.includes('/kakao-clinic/delivery-requests/') && m==='GET') { lookups++; expect(p.endsWith(requestId)).toBe(true); return scenario==='missing'?route.fulfill({status:404,json:{detail:'missing'}}):route.fulfill({json:{deliveryStatus:'unknown',retryable:false}}); }
  if (url.origin!==new URL(base).origin || p.startsWith('/api/') || p.startsWith('/auth/') || m!=='GET') {unexpected.push(`${m} ${p}`);return route.abort();}
  return route.continue();
 });
 await page.goto('/personal-project/aura/reports/37');
 await expect(page.getByRole('heading',{name:'합성 학생',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'카카오톡으로 받기'}).click();
 const status=page.locator('.share-status[role=status]');
 if (scenario==='fallback') await expect(status).toContainText('학생 방에는 발송되지 않았습니다');
 if (scenario==='success') await expect(status).toContainText('합성 대상');
 if (scenario==='pending') await expect(status).toContainText('작성완료');
 if (scenario==='failure') {await expect(status).toContainText('전송 전에 중단');await expect(page.getByRole('button',{name:'카카오톡으로 받기'})).toBeEnabled();}
 if (scenario==='partial') await expect(status).toContainText('일부 전송');
 if (['unknown','lost','missing'].includes(scenario)) await expect(status).toContainText('전송 결과를 확인할 수 없습니다');
 expect(requestId).toMatch(/^[0-9a-f-]{36}$/);
 if (['partial','unknown','lost','missing'].includes(scenario)) {
  await expect(page.getByRole('button',{name:'카카오톡으로 받기'})).toBeDisabled();
  await page.reload(); await expect(page.getByRole('heading',{name:'합성 학생',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'카카오톡으로 받기'})).toBeDisabled();
  await expect.poll(()=>lookups).toBeGreaterThan(0);
 }
 expect(sends).toBe(1); expect(unexpected).toEqual([]);
});
