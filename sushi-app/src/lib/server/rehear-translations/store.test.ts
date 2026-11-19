import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { authorized, entries, publish, readState } from './store';
import { GET, POST } from '../../../routes/rehear-translations/+server';
let directory: string;
const handler = (request: Request) => ({request,url:new URL(request.url)}) as any;
beforeEach(async () => { directory = await mkdtemp(join(tmpdir(),'rehear-review-test-')); process.env.REHEAR_TRANSLATION_DIR = directory; });
afterEach(async () => { delete process.env.REHEAR_TRANSLATION_DIR; vi.unstubAllGlobals(); await rm(directory,{recursive:true,force:true}); });
describe('translation review permissions and publication', () => {
  it('fails closed for missing, unverified and unlisted identities', async () => {
    await writeFile(join(directory,'reviewers.json'),JSON.stringify({emails:['reviewer@example.com']}));
    expect(await authorized(null)).toBeNull();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'6',data:{id:6,email:'reviewer@example.com',email_verified:false}}),{status:200})));
    expect(await authorized('mainauth=token')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'7',data:{id:7,email:'other@example.com',email_verified:true}}),{status:200})));
    expect(await authorized('mainauth=token')).toBeNull();
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'6',data:{id:6,email:'reviewer@example.com',email_verified:true}}),{status:200})));
    expect(await authorized('mainauth=token')).toEqual({email:'reviewer@example.com'});
    await writeFile(join(directory,'reviewers.json'),JSON.stringify({account_ids:[6]}));
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'6',data:{id:6,email:'reviewer@example.com',email_verified:false}}),{status:200})));
    expect(await authorized('mainauth=token')).toEqual({email:'reviewer@example.com'});
  });
  it('persists valid edits, rejects unknown keys, and prevents lost updates', async () => {
    const entry = entries().find(e=>e.id === 'nav:home')!;
    await expect(publish(0,{id:'copy:not-a-real-key',english:'x'},'test')).rejects.toThrow();
    const results = await Promise.all([publish(0,{id:entry.id,english:'Start page'},'a'),publish(0,{id:entry.id,english:'Landing'},'b')]);
    expect(results.filter(r=>r.conflict)).toHaveLength(1);
    const data = await readState();
    expect(data.version).toBe(1); expect(data.overrides[entry.id]).toBe('Start page');
    expect(data.history[0]).toMatchObject({actor:'a',before:entry.english,after:'Start page'});
    const reset = await publish(1,{id:entry.id,english:entry.english},'a');
    expect(reset.state.overrides[entry.id]).toBeUndefined();
    expect(JSON.parse(await readFile(join(directory,'published.json'),'utf8')).version).toBe(2);
  });
  it('allows the approved account to publish and public readers see the new copy', async () => {
    await writeFile(join(directory,'reviewers.json'),JSON.stringify({account_ids:[6]}));
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'6',data:{id:6,email:'reviewer@example.com',email_verified:false}}),{status:200})));
    const response = await POST(handler(new Request('https://rehear.kr/rehear-translations',{method:'POST',headers:{origin:'https://rehear.kr','content-type':'application/json',cookie:'mainauth=valid'},body:JSON.stringify({version:0,id:'nav:home',english:'Start page'})})));
    expect(response.status).toBe(200);
    const result = await GET(handler(new Request('https://rehear.kr/rehear-translations')));
    expect(await result.json()).toEqual({version:1,overrides:{'nav:home':'Start page'}});
  });
  it('lets an approved reviewer add and remove another verified-email reviewer', async () => {
    await writeFile(join(directory,'reviewers.json'),JSON.stringify({account_ids:[6]}));
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({sub:'6',data:{id:6,email:'owner@example.com',email_verified:false}}),{status:200})));
    const request = (action: string, email: string) => new Request('https://rehear.kr/rehear-translations',{method:'POST',headers:{origin:'https://rehear.kr','content-type':'application/json',cookie:'mainauth=valid'},body:JSON.stringify({action,email})});
    const added = await POST(handler(request('add-reviewer','COLLEAGUE@example.com')));
    expect(added.status).toBe(200); expect((await added.json()).reviewers).toEqual(['colleague@example.com']);
    const invalid = await POST(handler(request('add-reviewer','bad address'))); expect(invalid.status).toBe(400);
    const removed = await POST(handler(request('remove-reviewer','colleague@example.com')));
    expect((await removed.json()).reviewers).toEqual([]);
    expect(JSON.parse(await readFile(join(directory,'reviewers.json'),'utf8')).account_ids).toEqual([6]);
  });
  it('rejects cross-origin and unauthenticated writes while public reads exclude history', async () => {
    const cross = await POST(handler(new Request('https://rehear.kr/rehear-translations',{method:'POST',headers:{origin:'https://evil.example','content-type':'application/json'},body:'{}'})));
    expect(cross.status).toBe(403);
    const unauthorized = await POST(handler(new Request('https://rehear.kr/rehear-translations',{method:'POST',headers:{origin:'https://rehear.kr','content-type':'application/json'},body:JSON.stringify({version:0,id:'nav:home',english:'Test'})})));
    expect(unauthorized.status).toBe(403);
    const result = await GET(handler(new Request('https://rehear.kr/rehear-translations')));
    expect(await result.json()).toEqual({version:0,overrides:{}});
  });
});
