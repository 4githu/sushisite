import {test,expect} from '@playwright/test';
test('게시판 목록과 채널 탭, 상단 글 작업, 관리자 복구를 구분한다',async({page})=>{
 const boards=[{id:1,name:'자료 공유',parent_id:null,realm:'other',post_count:1,permissions:{read:true,post:true,manage:true}},{id:2,name:'강의자료',parent_id:1,realm:'other',permissions:{read:true,post:true,manage:true}}];
 await page.route('**/api/personal/boards**',async r=>{
  const p=new URL(r.request().url()).pathname;
  if(p.endsWith('/management'))return r.fulfill({json:{members:[{id:7890,name:'검수 계정',manager:true,locked:true}],archived:[{id:3,name:'보관 채널'}]}});
  if(p.endsWith('/restore')){boards.push({id:3,name:'보관 채널',parent_id:1,realm:'other',permissions:{read:true,post:true,manage:true}});return r.fulfill({json:{saved:true}});}
  if(p.endsWith('/posts/10'))return r.fulfill({json:{id:10,board_id:1,title:'샘플 글',author_id:7890,author_name:'검수 계정',created_at:'2026-10-08',revision:1,canEdit:true,canManage:true,canComment:true,comments:[],document:{version:1,schemaVersion:2,blocks:[],richContent:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'샘플 본문'}]}]}}}});
  if(p.endsWith('/posts'))return r.fulfill({json:{posts:[{id:10,title:'샘플 글',author_name:'검수 계정',created_at:'2026-10-08',comments:0}],total:1}});
  return r.fulfill({json:{boards,canCreate:true,canAdmin:true}});
 });
 await page.goto('/personal-project/calendar/boards');
 await expect(page.locator('.board-directory a')).toHaveCount(1);
 await page.locator('.board-directory a').click();
 await expect(page.getByRole('navigation',{name:'게시판 채널'}).getByRole('link')).toHaveCount(2);
 await page.getByRole('link',{name:'강의자료',exact:true}).click();await expect(page).toHaveURL(/board=2/);
 await page.getByRole('link',{name:'일반',exact:true}).click();
 await page.getByRole('button',{name:'게시판·채널 설정',exact:true}).click();
 await expect(page.getByRole('combobox',{name:'검수 계정 게시판 권한'})).toHaveValue('manager');
 await page.getByRole('button',{name:'보관 채널 복구',exact:true}).click();
 await expect(page.getByRole('navigation',{name:'게시판 채널'}).getByRole('link',{name:'보관 채널',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'게시판·채널 설정',exact:true}).click();
 await page.getByRole('link',{name:/샘플 글/}).click();
 await expect(page.getByRole('button',{name:'글 수정',exact:true})).toBeVisible();
 await expect(page.locator('.post-detail [contenteditable=false]')).toContainText('샘플 본문');
 await page.screenshot({path:'/private/tmp/boards-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
 await page.screenshot({path:'/private/tmp/boards-mobile.png',fullPage:true});
});
