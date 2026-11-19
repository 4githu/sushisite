import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { RequestHandler } from './$types';
export const GET: RequestHandler = async () => {
 try {
  const text = await readFile(join(process.cwd(),'..','windows-widget','dist','updater-manifest.json'),'utf8');
  return new Response(text,{headers:{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
 } catch { return new Response(null,{status:204,headers:{'Cache-Control':'no-store'}}); }
};
