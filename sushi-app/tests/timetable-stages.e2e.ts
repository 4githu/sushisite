import {test,expect} from '@playwright/test';
test('학년 버튼과 실제 연도를 독립적으로 저장하고 추가 학년을 유지한다',async({page})=>{
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
