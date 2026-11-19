import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('page thumbnails keep full height and separate rows inside a host with fixed-height buttons',async({page})=>{
 const css=await readFile('src/lib/notebook/notebook.css','utf8');
 await page.setContent(`<style>.host button{height:34px;max-height:34px}${css}</style><div class="host"><div class="netaq-notebook"><aside class="page-rail" style="width:200px;--thumb-min:72px"><div class="thumb-list">${Array.from({length:10},(_,i)=>`<button class="page-thumb"><div class="thumb-paper" style="aspect-ratio:651.968/850.394"></div><span>${i+1}</span></button>`).join('')}</div></aside></div></div>`);
 const boxes=await page.locator('.page-thumb').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height};}));
 expect(boxes[0].height).toBeGreaterThan(100);
 expect(boxes[2].top).toBeGreaterThanOrEqual(boxes[0].bottom);
});
