import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import english from '$lib/odi/i18n/copy.json';
import { translations } from '$lib/odi/i18n';

type Entry = { id: string; korean: string; english: string; section: string; path: string };
type Change = { id: string; english: string };
type State = { version: number; overrides: Record<string, string>; history: Array<{at: string; actor: string; id: string; before: string; after: string}> };
const storeDir = () => process.env.REHEAR_TRANSLATION_DIR || join(process.cwd(), '.runtime', 'rehear-translations');
const file = () => join(storeDir(), 'published.json');
export function entries(): Entry[] {
  const nav = Object.entries(translations.ko).map(([id, korean]) => ({id: `nav:${id}`, korean, english: translations.en[id as keyof typeof translations.en], section:'메뉴', path:'/odi'}));
  const body = Object.entries(english).map(([korean, value]) => ({id:`copy:${korean}`, korean, english:value, ...classify(korean)}));
  return [...nav, ...body];
}
function classify(s: string): {section:string;path:string} {
  if (/비밀번호|이메일|계정|로그인|인증|닉네임|약관|회원/.test(s)) return {section:'로그인·계정',path:'/odi'};
  if (/면접/.test(s)) return {section:'면접 설정',path:'/odi/session/interview'};
  if (/청중|발표|업로드|세션 설정|자료|PIN/.test(s)) return {section:'발표·세션',path:'/odi/session/presentation'};
  if (/리포트|결과|평가|점수|피드백|질문|분석/.test(s)) return {section:'리포트',path:'/odi/report'};
  if (/연습|훈련|녹음/.test(s)) return {section:'연습',path:'/odi/practice'};
  if (/템플릿|주제/.test(s)) return {section:'템플릿',path:'/odi/templates'};
  return {section:'공통',path:'/odi'};
}
export async function readState(): Promise<State> {
  try {
    const state = JSON.parse(await readFile(file(), 'utf8'));
    if (!Number.isSafeInteger(state.version) || !state.overrides || typeof state.overrides !== 'object' || !Array.isArray(state.history)) throw new Error('Invalid translation data');
    return state;
  } catch (err: any) {
    if (err?.code === 'ENOENT') return {version:0,overrides:{},history:[]};
    throw err;
  }
}
let pending: Promise<unknown> = Promise.resolve();
export async function publish(expectedVersion: number, change: Change, actor: string) {
  const operation = pending.then(async () => {
    const state = await readState();
    if (state.version !== expectedVersion) return {conflict:true as const, state};
    const available = entries();
    const source = available.find((e) => e.id === change.id);
    if (!source || typeof change.english !== 'string' || !change.english.trim() || change.english.length > 2000 || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(change.english)) throw new Error('Invalid translation');
    const next = change.english.trim();
    const before = state.overrides[change.id] ?? source.english;
    if (next === before) return {conflict:false as const,state};
    if (next === source.english) delete state.overrides[change.id]; else state.overrides[change.id] = next;
    state.version += 1;
    state.history.push({at:new Date().toISOString(),actor,id:change.id,before,after:next});
    state.history = state.history.slice(-500);
    await mkdir(storeDir(), {recursive:true,mode:0o700});
    const temp = join(storeDir(), `.translation-${randomUUID()}.tmp`);
    await writeFile(temp, JSON.stringify(state), {mode:0o600,flag:'wx'});
    await rename(temp,file());
    return {conflict:false as const,state};
  });
  pending = operation.catch(() => {});
  return operation;
}
export async function authorized(cookie: string | null): Promise<{email:string}|null> {
  if (!cookie) return null;
  let allowed: string[] = [], ids: string[] = [];
  try {
    const config = JSON.parse(await readFile(join(storeDir(), 'reviewers.json'), 'utf8'));
    allowed = Array.isArray(config.emails) ? config.emails.map((x: unknown) => String(x).trim().toLowerCase()) : [];
    ids = Array.isArray(config.account_ids) ? config.account_ids.map((x: unknown) => String(x)) : [];
  } catch (e: any) { if (e?.code !== 'ENOENT') throw e; }
  if (!allowed.length && !ids.length) return null;
  const response = await fetch('http://127.0.0.1:8000/auth/isjwt?key=mainauth', {headers:{cookie},signal:AbortSignal.timeout(5000)});
  if (!response.ok) return null;
  const account = await response.json();
  const email = String(account?.data?.email || '').trim().toLowerCase();
  const id = String(account?.sub || '');
  if (!email || !id || String(account?.data?.id || '') !== id) return null;
  if (!ids.includes(id) && !(account?.data?.email_verified === true && allowed.includes(email))) return null;
  return {email};
}

export async function reviewerEmails(): Promise<string[]> {
  try {
    const config = JSON.parse(await readFile(join(storeDir(), 'reviewers.json'), 'utf8'));
    return Array.isArray(config.emails) ? config.emails.filter((x: unknown) => typeof x === 'string') : [];
  } catch (e: any) { if (e?.code === 'ENOENT') return []; throw e; }
}
export async function changeReviewer(emailInput: string, action: 'add' | 'remove', actor: string) {
  const operation = pending.then(async () => {
    const email = emailInput.trim().toLowerCase();
    if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error('Invalid email');
    const path = join(storeDir(), 'reviewers.json');
    const config = JSON.parse(await readFile(path, 'utf8'));
    const emails: string[] = Array.isArray(config.emails) ? config.emails : [];
    const updated = action === 'add' ? [...new Set([...emails, email])] : emails.filter((x: string) => x !== email);
    if (updated.length > 50) throw new Error('Too many reviewers');
    config.emails = updated;
    config.history = [...(Array.isArray(config.history) ? config.history : []), {at:new Date().toISOString(),actor,action,email}].slice(-200);
    const temp = join(storeDir(), `.reviewers-${randomUUID()}.tmp`);
    await writeFile(temp, JSON.stringify(config), {mode:0o600,flag:'wx'});
    await rename(temp,path);
    return updated;
  });
  pending = operation.catch(() => {});
  return operation;
}
