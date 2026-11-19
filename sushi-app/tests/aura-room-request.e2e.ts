import {expect,test,type Page} from '@playwright/test';
const round=(id:number,date:string,name:string)=>({id,schoolId:1,schoolName:'합성고',progressStage:'grade1_semester1_midterm',roundNumber:id,roundNumbers:[id],roundLabel:`${id}회`,eventId:id,startTime:`${date}T10:30:00+09:00`,endTime:`${date}T12:30:00+09:00`,modality:'in_person',attendanceStatus:'scheduled',description:'',targets:[{id,studentName:name,report:null}],amount:0,paymentStatus:'pending'});
async function setup(page:Page){
 await page.clock.install({time:new Date('2026-11-06T10:00:00+09:00')});
 const rows=[round(1,'2026-11-02','월학생'),round(2,'2026-11-06','금학생'),round(3,'2026-11-08','일학생')];
 await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'1',data:{id:'1',name:'합성'},exp:9999999999}}));
 await page.route('**/api/personal/**',r=>{
  const path=new URL(r.request().url()).pathname;
  if(path.endsWith('/aura/rounds'))return r.fulfill({json:rows});
  if(path.endsWith('/aura/schools'))return r.fulfill({json:[{id:1,name:'합성고',currentStage:'grade1_semester1_midterm'}]});
  return r.fulfill({json:[]});
 });
 await page.goto('/personal-project/aura');await expect(page.locator('.slot.busy').first()).toBeVisible();
}
const dayButton=(page:Page,day:number)=>page.getByRole('button',{name:`2026. 11. ${day}. 강의실 배정 요청문 만들기`});

test('과거·오늘·미래 날짜를 누르면 해당 날짜의 문구가 보이고 실제 클립보드로 복사된다',async({page,context})=>{
 await context.grantPermissions(['clipboard-read','clipboard-write']);await setup(page);
 for(const [day,name] of [[2,'월학생'],[6,'금학생'],[8,'일학생']] as const){
  await dayButton(page,day).click();const dialog=page.getByRole('dialog');const text=dialog.getByRole('textbox',{name:'강의실 배정 요청문'});
  await expect(text).toHaveValue(new RegExp(name));await expect(text).toHaveValue(new RegExp(`11/${day}`));
  const expected=await text.inputValue();await dialog.getByRole('button',{name:'복사하기'}).click();
  await expect(dialog.getByRole('button',{name:'복사됨'})).toBeVisible();
  expect(await page.evaluate(()=>navigator.clipboard.readText())).toBe(expected);
  await dialog.getByRole('button',{name:'닫기'}).click();await expect(dayButton(page,day)).toBeFocused();
 }
});

test('복사 API가 차단되면 문구를 선택해 대체 복사를 시도하며 긴 내부 안내가 없다',async({page})=>{
 await setup(page);await page.evaluate(()=>{Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('denied')}}});const previous=document.execCommand.bind(document);document.execCommand=((command:string)=>{(window as any).__copyFallback={command,text:(document.activeElement as HTMLTextAreaElement)?.value};return command==='copy'?true:previous(command)}) as typeof document.execCommand;});
 await dayButton(page,8).click();const dialog=page.getByRole('dialog');await expect(dialog.getByRole('textbox')).toHaveValue(/일학생/);
 await dialog.getByRole('button',{name:'복사하기'}).click();await expect(dialog.getByRole('button',{name:'복사됨'})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__copyFallback)).toMatchObject({command:'copy',text:expect.stringContaining('일학생')});
 await expect(dialog).not.toContainText('다음날');await expect(dialog).not.toContainText('복사 전용');
});

test('빈 날짜는 명확한 빈 상태이고 모바일·데스크톱에서 문구와 복사 버튼이 화면 안에 있다',async({page})=>{
 await setup(page);await dayButton(page,5).click();await expect(page.getByRole('dialog')).toContainText('이날은 강의실이 필요한 대면 수업이 없습니다.');await expect(page.getByRole('button',{name:'복사하기'})).toBeDisabled();await page.getByRole('button',{name:'닫기'}).click();
 for(const [width,height,label] of [[1280,800,'desktop'],[390,844,'mobile']] as const){
  await page.setViewportSize({width,height});await dayButton(page,8).click();const d=page.getByRole('dialog');await expect(d.getByRole('textbox')).toHaveValue(/일학생/);await expect(d.getByRole('button',{name:'복사하기'})).toBeInViewport();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:`test-results/aura-room-request-${label}.png`});await page.keyboard.press('Escape');await expect(d).toHaveCount(0);
 }
});
