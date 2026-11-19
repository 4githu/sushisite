import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { join } from 'node:path';
import { Readable } from 'node:stream';
import type { RequestHandler } from './$types';
export const GET: RequestHandler = async ({params}) => {
 if (!/^\d+\.\d+\.\d+$/.test(params.version)) return new Response(null,{status:404});
 const file=join(process.cwd(),'..','windows-widget','dist',`NETAQ-${params.version}-x64-setup.exe`);
 try {const info=await stat(file);return new Response(Readable.toWeb(createReadStream(file)) as ReadableStream<Uint8Array>,{headers:{'Content-Type':'application/vnd.microsoft.portable-executable','Content-Length':String(info.size),'Cache-Control':'public, max-age=31536000, immutable','X-Content-Type-Options':'nosniff'}});}
 catch {return new Response(null,{status:404});}
};
