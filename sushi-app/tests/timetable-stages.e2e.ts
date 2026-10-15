import {test,expect} from '@playwright/test';
const apiOrigin=process.env.STUDENT_TEST_API_URL||'';
test.skip(!apiOrigin,'Requires the isolated student_test_server.py fixture.');
test('학년 버튼과 실제 연도를 독립적으로 저장하고 추가 학년을 유지한다',async({page})=>{
 await page.route('**/api/personal/**',async r=>{const u=new URL(r.request().url());return r.fulfill({response:await r.fetch({url:apiOrigin+u.pathname+u.search})});});
 await page.route('**/auth/isjwt?key=mainauth',r=>r.fulfill({json:{sub:'7890',data:{id:'7890',name:'검수 계정',email:'review@example.com'},exp:9999999999}}));

 await page.goto('/personal-project/calendar/student/timetable');
 await page.getByRole('button',{name:'4-2',exact:true}).click();
 const term=page.getByRole('combobox',{name:'학기',exact:true});
 await term.selectOption('2028_U000200002U000300001');
 await expect(term).toHaveValue('2028_U000200002U000300001');
 await page.getByRole('button',{name:'1-1',exact:true}).click();
 await page.getByRole('button',{name:'4-2',exact:true}).click();
 await expect(term).toHaveValue('2028_U000200002U000300001');
 await page.getByRole('button',{name:'학년 추가',exact:true}).click();
 await expect(page.getByRole('button',{name:'5-겨울',exact:true})).toBeVisible();
 await page.reload();await expect(page.getByRole('button',{name:'5-겨울',exact:true})).toBeVisible();
 await expect(term).toHaveValue('2028_U000200002U000300001');
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(391);
 await page.screenshot({path:'/private/tmp/timetable-stages-mobile.png',fullPage:true});
});
