import {test,expect} from '@playwright/test';
const start='2026-11-08T10:00:00+09:00';
const row=(id:number)=>({id,schoolId:1,schoolName:'합성',progressStage:'grade1_semester1_midterm',roundNumber:id,roundNumbers:[id],roundLabel:`${id}회차`,startTime:start,endTime:'2026-11-08T11:00:00+09:00',description:'',modality:'in_person',seriesGroupId:'series',seriesIndex:id-1,targets:[{id,studentName:'합성학생',report:null}],amount:30000,attendanceStatus:'scheduled',paymentStatus:'pending'});
for(const scope of ['following','all'] as const) test(`${scope}: 선택한 반복 범위로 삭제하고 확인 후 목록을 갱신한다`,async({page})=>{
 let rows=[row(1),row(2),row(3)];const deletes:string[]=[];
 await page.clock.install({time:new Date('2026-11-06T09:00:00+09:00')});
 await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'1',data:{id:'1',name:'합성'},exp:9999999999}}));
 await page.route('**/api/personal/**',r=>{const u=new URL(r.request().url());if(u.pathname.endsWith('/aura/rounds')&&r.request().method()==='GET')return r.fulfill({json:rows});if(u.pathname.endsWith('/aura/schools'))return r.fulfill({json:[{id:1,name:'합성',currentStage:'grade1_semester1_midterm'}]});if(r.request().method()==='DELETE'){deletes.push(u.searchParams.get('scope')??'this');rows=[];return r.fulfill({status:204,body:''});}return r.fulfill({json:[]});});
 await page.goto('/personal-project/aura');await page.locator('.slot.busy').first().click();
 await page.getByLabel('반복 일정 수정 범위').selectOption(scope);
 page.once('dialog',d=>d.accept());await page.locator('form.modal .danger-button').click();
 await expect.poll(()=>deletes).toEqual([scope]);await expect(page.locator('form.modal')).toHaveCount(0);
});
