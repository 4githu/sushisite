import {test,expect,type Page} from '@playwright/test';
async function setup(page:Page){
 await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'1',data:{id:'1',name:'테스트',email:'test@example.com'},exp:9999999999}}));
 const reports:Record<number,any>={};const writes:any[]=[];
 for(const id of [1,2])reports[id]={id,targetId:id,studentName:id===1?'학생가':'학생나',schoolId:1,schoolName:'검증고',progressStage:'accepted',roundNumber:1,roundNumbers:[1],roundLabel:'1회차',templateVersion:1,status:'draft',sourceNotes:'',questionChecks:{},lectureProgress:5,lectureComprehension:5,memoryBefore:4,memoryAfter:5,assessmentJson:null,generatedReportJson:null,aiModel:null,clinicTargets:[{id:1,studentName:'학생가',status:'draft'},{id:2,studentName:'학생나',status:'draft'}],contentJson:{version:1,documentId:'same-template',createdAt:'2026-09-25T00:00:00Z',updatedAt:'2026-09-25T00:00:00Z',blocks:[{id:'shared-question',type:'paragraph',children:[{type:'text',text:'공통 질문'}]}]}};
 await page.route('**/api/personal/**',async r=>{
  const path=new URL(r.request().url()).pathname;
  if(path.endsWith('/ai/models'))return r.fulfill({json:{models:[],defaultModel:''}});
  if(path.endsWith('/ai-reports'))return r.fulfill({json:{results:[]}});
  if(path.endsWith('/status'))return r.fulfill({json:{enabled:false,connected:false}});
  if(path.endsWith('/attachments'))return r.fulfill({json:[]});
  const get=path.match(/targets\/(\d+)\/report$/);if(get)return r.fulfill({json:reports[+get[1]]});
  const patch=path.match(/target-reports\/(\d+)$/);if(patch){const id=+patch[1],body=r.request().postDataJSON();writes.push({id,...body});reports[id]={...reports[id],contentJson:body.content_json,questionChecks:body.question_checks};return r.fulfill({json:reports[id]});}
  return r.fulfill({json:[]});
 });return {reports,writes};
}
test('Ctrl Alt Q 체크를 학생별로 저장하고 전환 후에도 섞지 않는다',async({page})=>{
 const {reports,writes}=await setup(page);
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');
 await surface.click();await page.keyboard.press('Control+Alt+q');
 await expect(surface.locator('.question-check')).toHaveAttribute('aria-pressed','true');
 await expect.poll(()=>writes.some(w=>w.id===1&&w.question_checks['shared-question']===true)).toBeTruthy();
 await page.getByRole('navigation',{name:'같은 클리닉 학생 전환'}).getByRole('button',{name:/학생나/}).click();
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 await expect(surface.locator('.question-check')).toHaveAttribute('aria-pressed','false');
 await surface.click();await page.keyboard.press('Control+Alt+q');await page.keyboard.press('Control+Alt+q');
 await page.getByRole('navigation',{name:'같은 클리닉 학생 전환'}).getByRole('button',{name:/학생가/}).click();
 await expect(page.getByRole('heading',{name:'학생가',exact:true})).toBeVisible();
 await expect(surface.locator('.question-check')).toHaveAttribute('aria-pressed','true');
 expect(reports[2].questionChecks['shared-question']).toBe(false);
 expect(reports[1].questionChecks['shared-question']).toBe(true);
 await page.screenshot({path:'/private/tmp/aura-checks-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:'/private/tmp/aura-checks-mobile.png',fullPage:true});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('이전 학생의 늦은 저장 응답이 새 학생 화면을 덮지 않는다',async({page})=>{
 await setup(page);
 let release!:()=>void;const gate=new Promise<void>(resolve=>release=resolve);let started=false;
 await page.route('**/api/personal/aura/target-reports/1',async r=>{started=true;await gate;await r.fallback();});
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');await surface.click();await page.keyboard.press('Control+Alt+q');
 await expect.poll(()=>started).toBeTruthy();
 await page.evaluate(()=>{const a=document.createElement('a');a.href='/personal-project/aura/reports/2';a.textContent='다른 학생 링크';a.id='test-student-link';document.querySelector('.editor-panel')!.prepend(a);});
 await page.locator('#test-student-link').click();
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 release();
 await expect(surface.locator('.question-check')).toHaveAttribute('aria-pressed','false');
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 await page.waitForTimeout(300);
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
});
