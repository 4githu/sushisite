import { json } from '@sveltejs/kit';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { RequestHandler } from './$types';
export const GET: RequestHandler = async () => {
 let version='0.11.0';
 try {const data=JSON.parse(await readFile(join(process.cwd(),'..','windows-widget','dist','updater-manifest.json'),'utf8'));if (/^\d+\.\d+\.\d+$/.test(data.version)) version=data.version;} catch {}
 const parts=version.split('.').map(Number);
 return json({android:{version:'2.6.1',code:17},windows:{version,code:parts[0]*10000+parts[1]+(parts[2]>0?1:0)}},{headers:{'Cache-Control':'no-store'}});
};
