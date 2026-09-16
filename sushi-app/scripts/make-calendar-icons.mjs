import { chromium } from 'playwright';
import { readFile, writeFile } from 'node:fs/promises';
const svg=await readFile(new URL('../static/ondo-icon.svg',import.meta.url),'utf8');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage();
for(const size of [192,512]) {
 const data=await page.evaluate(async({svg,size})=>{const image=new Image();image.src='data:image/svg+xml;base64,'+btoa(svg);await image.decode();const canvas=document.createElement('canvas');canvas.width=canvas.height=size;canvas.getContext('2d').drawImage(image,0,0,size,size);return canvas.toDataURL('image/png').split(',')[1];},{svg,size});
 await writeFile(new URL(`../static/ondo-${size}.png`,import.meta.url),Buffer.from(data,'base64'));
}
await browser.close();
