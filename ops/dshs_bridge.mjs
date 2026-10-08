// JSON stdin/stdout adapter. Only the configured private board is reachable.
import { createRequire } from 'node:module';
import { readFile, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'sushi-app/package.json'));
const {chromium}=require('playwright');
const config=JSON.parse(await readFile(path.join(root,'sushi-fast/.runtime/dshs-credentials.json'),'utf8'));
const base='https://test.dshs.app', board='/board/nSW86Tx';
let input='';for await(const chunk of process.stdin)input+=chunk;
const job=JSON.parse(input),browser=await chromium.launch({headless:true});
let committed=false;
try{
 const context=await browser.newContext({acceptDownloads:true});const page=await context.newPage();page.setDefaultTimeout(20000);
 await page.goto(base+board);
 if(new URL(page.url()).pathname==='/login'){
  await page.locator('input:not([type=hidden]):visible').first().fill(config.email);await page.getByRole('button',{name:'다음',exact:true}).click();
  await page.locator('input[type=password]').fill(config.password);await page.getByRole('button',{name:'다음',exact:true}).click();
  await page.waitForURL(url=>url.pathname!='/login');await page.goto(base+board);
 }
 await page.getByRole('heading',{name:'자료공유 게시판',exact:true}).first().waitFor();
 if(job.command==='read'){
  const links=new Set();let complete=false;
  for(let i=0;i<100;i++){
   const current=await page.locator(`a[href^="${board}/post/"]`).evaluateAll(nodes=>nodes.map(n=>n.getAttribute('href')));
   current.forEach(x=>links.add(x));
   const next=page.getByRole('button',{name:'다음',exact:true});
   if(!await next.count()||!await next.isEnabled()){complete=true;break;}
   await next.click();
   await page.waitForFunction(({old,selector})=>JSON.stringify([...document.querySelectorAll(selector)].map(n=>n.getAttribute('href')))!==JSON.stringify(old),{old:current,selector:`a[href^="${board}/post/"]`});
  }
  if(!complete)throw Error('게시판 100페이지 한도를 초과했습니다. 커서를 갱신하지 않습니다.');
  const posts=[];let bytes=0;
  const accountBytes=n=>{bytes+=n;if(bytes>64*1024*1024)throw Error('한 번의 첨부 수집 64MB 제한을 초과했습니다.');};
  for(const href of [...links].reverse()){
   if(job.baseline||(job.seen||[]).includes(href))continue;
   if(posts.length>=10)break;
   await page.goto(base+href);const content=page.locator('.prose .tiptap');await content.waitFor();
   const images=[];for(const img of await content.locator('img').all()){if(images.length>=10)throw Error('이미지 10장 한도를 초과했습니다.'); const png=await img.screenshot({timeout:15000});if(png.length>8*1024*1024)throw Error('이미지 크기 한도를 초과했습니다.');accountBytes(png.length);images.push(png.toString('base64'));}
   const files=[];
   const downloads=await page.getByRole('button',{name:'다운로드',exact:true}).all();
   if(downloads.length>10)throw Error('첨부파일 10개 한도를 초과했습니다.');
   for(const button of downloads){
    const pending=page.waitForEvent('download');await button.click();const download=await pending;
    const file=await download.path();if(!file)throw Error('첨부파일 다운로드 실패');
    if((await stat(file)).size>20*1024*1024)throw Error('첨부파일 20MB 한도를 초과했습니다.');
    accountBytes((await stat(file)).size);files.push({name:path.basename(download.suggestedFilename()),data:(await readFile(file)).toString('base64')});await download.delete();
   }
   posts.push({images,files,id:href,url:base+href,title:await page.locator('h1').innerText(),text:await content.innerText(),assets:await content.locator('img').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('src')))});
  }
  console.log(JSON.stringify({posts,ids:[...links],complete}));
 }else if(job.command==='publish'||job.command==='verify'){
  // Check a stable source link before writing; uncertain submissions are never retried blindly.
  if(!/^https:\/\/netaq\.chobab\.app\/personal-project\/calendar\/boards\?board=4&post=\d+$/.test(job.source))throw Error('허용되지 않은 출처');
  if(job.command==='publish'){
  await page.goto(base+board+'/submit');
  await page.locator('input:not([type=hidden]):not([type=checkbox]):not([type=file]):visible').first().fill(job.title);
  const editor=page.locator('[contenteditable=true]').first();await editor.fill(job.text+'\n\n'+job.source);
  if(job.files?.length){
   if(job.files.length>20)throw Error('첨부파일 20개 한도를 초과했습니다.');
   await page.getByRole('button',{name:'추가',exact:true}).click();
   await page.getByRole('menuitem',{name:'파일',exact:true}).click();
   for(const file of job.files){
    if((await stat(file)).size>20*1024*1024)throw Error('DSHS 첨부는 파일당 20MB 이하입니다.');
    await page.locator('input[type=file]').last().setInputFiles(file);
    await page.getByRole('button',{name:/^1개 업로드$/}).click();
    await page.getByRole('button',{name:'게시하기',exact:true}).waitFor({state:'visible'});
   }
  }
  committed=true;await page.getByRole('button',{name:'게시하기',exact:true}).click();
  await page.waitForURL(url=>url.pathname===board||url.pathname.startsWith(board+'/post/'));
  }
  if(new URL(page.url()).pathname===board){
   const matches=await page.locator(`a[href^="${board}/post/"]`).filter({has:page.getByRole('heading',{name:job.title,exact:true})}).all();
   let found=false;
   for(const match of matches){
    const href=await match.getAttribute('href');
    const detail=await context.newPage();await detail.goto(base+href);
    const content=detail.locator('.prose .tiptap');await content.waitFor();
    if((await content.innerText()).includes(job.source)){await page.goto(base+href);found=true;await detail.close();break;}
    await detail.close();
   }
   if(!found)throw Error('게시 결과를 확인하지 못했습니다. 중복 게시하지 말고 원격 게시판을 확인해주세요.');
  }
  if(!((await page.locator('.prose .tiptap').innerText()).includes(job.source)))throw Error('게시된 출처가 일치하지 않습니다.');
  console.log(JSON.stringify({published:true,url:page.url()}));
 }else throw Error('지원하지 않는 명령');
}catch(e){console.log(JSON.stringify({error:String(e.message||e).split('Call log:')[0].slice(0,500),uncertain:committed}));process.exitCode=1;}
finally{await browser.close();}
