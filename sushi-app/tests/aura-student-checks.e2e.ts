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
test('인용을 학생별로 저장하고 전환 후에도 섞지 않는다',async({page})=>{
 const {reports,writes}=await setup(page);
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');
 await surface.click();await page.keyboard.press('Control+Shift+b');
 await expect(surface.locator('blockquote')).toContainText('공통 질문');
 await expect.poll(()=>writes.some(w=>w.id===1&&JSON.stringify(w.content_json).includes('blockquote'))).toBeTruthy();
 await page.getByRole('navigation',{name:'같은 클리닉 학생 전환'}).getByRole('button',{name:/학생나/}).click();
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 await expect(surface.locator('blockquote')).toHaveCount(0);
 await surface.click();await page.keyboard.press('Control+Shift+b');await page.keyboard.press('Control+Shift+b');
 await page.getByRole('navigation',{name:'같은 클리닉 학생 전환'}).getByRole('button',{name:/학생가/}).click();
 await expect(page.getByRole('heading',{name:'학생가',exact:true})).toBeVisible();
 await expect(surface.locator('blockquote')).toContainText('공통 질문');
 expect(JSON.stringify(reports[2].contentJson.richContent)).not.toContain('blockquote');
 expect(JSON.stringify(reports[1].contentJson.richContent)).toContain('blockquote');
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
 await expect(surface).toContainText('공통 질문');await surface.click();await page.keyboard.press('Control+Shift+b');
 await expect.poll(()=>started).toBeTruthy();
 await page.evaluate(()=>{const a=document.createElement('a');a.href='/personal-project/aura/reports/2';a.textContent='다른 학생 링크';a.id='test-student-link';document.querySelector('.editor-panel')!.prepend(a);});
 await page.locator('#test-student-link').click();
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 release();
 await expect(surface.locator('blockquote')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
 await page.waitForTimeout(300);
 await expect(page.getByRole('heading',{name:'학생나',exact:true})).toBeVisible();
});

test('자동 저장과 수동 저장이 새로고침 후에도 남고 단원 양식을 다른 학생에게 추가한다',async({page})=>{
 const {writes}=await setup(page);
 await page.goto('/personal-project/aura/reports/1');
 await page.getByRole('button',{name:'단축키 보기'}).click();
 await expect(page.locator('.shortcut-panel')).toContainText('Ctrl/Cmd+S · 수동 저장');
 await page.locator('.shortcut-panel').getByRole('button',{name:'닫기'}).click();
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');
 await surface.click();await page.keyboard.press('End');await page.keyboard.type(' 세포호흡');
 await expect.poll(()=>writes.some(w=>w.id===1&&JSON.stringify(w.content_json).includes('세포호흡'))).toBeTruthy();
 await page.waitForTimeout(3200);
 expect(writes.filter(w=>w.id===1)).toHaveLength(1);
 await page.reload();
 await expect(surface).toContainText('세포호흡');
 await surface.click();await page.keyboard.press('End');await page.keyboard.type(' ATP');await page.keyboard.press('ControlOrMeta+s');
 await expect.poll(()=>writes.some(w=>w.id===1&&JSON.stringify(w.content_json).includes('ATP'))).toBeTruthy();
 await page.getByRole('textbox',{name:'저장할 단원 양식 이름'}).fill('세포호흡');
 await page.getByRole('button',{name:'현재 내용으로 양식 저장'}).click();
 await page.getByRole('navigation',{name:'같은 클리닉 학생 전환'}).getByRole('button',{name:/학생나/}).click();
 await page.getByRole('combobox',{name:'적용할 단원 양식'}).selectOption({label:'세포호흡'});
 await page.getByRole('button',{name:'선택 내용 추가'}).click();
 await expect(page.locator('.unit-template-tools [role=status]')).toContainText('내용을 뒤에 추가했습니다');
 await expect(surface).toContainText('ATP');
 await expect(surface.locator('h2')).toContainText('세포호흡');
 await expect.poll(()=>writes.some(w=>w.id===2&&JSON.stringify(w.content_json).includes('ATP'))).toBeTruthy();
 await page.reload();
 await expect(surface).toContainText('ATP');
 await expect(page.getByRole('button',{name:'PDF 받기'})).toHaveCount(1);
 await expect(page.getByRole('button',{name:'작성 완료'})).toHaveCount(1);
});

test('서로 다른 들여쓰기 수준을 함께 선택해도 각 문단에서 한 단계씩 증가한다',async({page})=>{
 const {reports,writes}=await setup(page);
 reports[1].contentJson={version:1,schemaVersion:2,documentId:'indent-doc',createdAt:'2026-09-25T00:00:00Z',updatedAt:'2026-09-25T00:00:00Z',blocks:[
  {id:'p1',type:'paragraph',depth:1,children:[{type:'text',text:'첫 단계'}]},
  {id:'p2',type:'paragraph',depth:2,children:[{type:'text',text:'둘째 단계'}]}
 ],richContent:{type:'doc',content:[
  {type:'paragraph',attrs:{id:'p1',indent:1},content:[{type:'text',text:'첫 단계'}]},
  {type:'paragraph',attrs:{id:'p2',indent:2},content:[{type:'text',text:'둘째 단계'}]}
 ]}};
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('둘째 단계');
 await surface.click();await page.keyboard.press('ControlOrMeta+a');await page.keyboard.press('Tab');
 await expect.poll(()=>writes.at(-1)?.content_json?.blocks?.map((block:any)=>block.depth)).toEqual([2,3]);
 await page.reload();
 await expect(surface.locator('p').nth(0)).toHaveAttribute('data-indent','2');
 await expect(surface.locator('p').nth(1)).toHaveAttribute('data-indent','3');
});

test('자동 저장 대기 중 바로 새로고침해도 기기 복구본에서 내용을 되살린다',async({page})=>{
 const {writes}=await setup(page);
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');
 await surface.click();await page.keyboard.press('End');await page.keyboard.type(' 즉시 복구');
 await page.reload();
 await expect(surface).toContainText('즉시 복구');
 await expect.poll(()=>writes.some(w=>w.id===1&&JSON.stringify(w.content_json).includes('즉시 복구'))).toBeTruthy();
});

test('노랑 단축키가 AI 문서에 같은 색으로 저장되고 붙여넣은 색을 지울 수 있다',async({page})=>{
 const {writes}=await setup(page);
 await page.goto('/personal-project/aura/reports/1');
 const surface=page.locator('[contenteditable=true]').first();
 await expect(surface).toContainText('공통 질문');
 await surface.click();await page.keyboard.press('ControlOrMeta+a');await page.keyboard.press('ControlOrMeta+Alt+2');
 await expect.poll(()=>writes.at(-1)?.content_json?.blocks?.[0]?.children?.[0]?.highlightColor).toBe('#fef08a');
 await surface.click();await page.keyboard.press('ControlOrMeta+a');
 await page.evaluate(()=>{
  const data=new DataTransfer();
  data.setData('text/html','<p><span style="color: rgb(220, 38, 38); background-color: rgb(254, 240, 138)">원노트 색상</span></p>');
  data.setData('text/plain','원노트 색상');
  document.querySelector('[contenteditable=true]')?.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
 });
 await expect(surface).toContainText('원노트 색상');
 await surface.click();await page.keyboard.press('ControlOrMeta+a');
 await page.getByRole('button',{name:'색상 도구'}).click();
 await page.getByRole('button',{name:'선택한 글자의 글자색·형광색 모두 제거'}).click();
 await expect.poll(()=>writes.at(-1)?.content_json?.blocks?.[0]?.children?.[0]?.highlightColor).toBeFalsy();
 await page.reload();
 await expect(surface).toContainText('원노트 색상');
});
