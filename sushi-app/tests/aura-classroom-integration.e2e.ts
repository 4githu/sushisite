import { expect, test } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { createServer } from 'node:net';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';

const fast = resolve(process.cwd(), '../sushi-fast');
const kstDay = (date: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
const tomorrow = new Date(Date.now() + 86_400_000);
const ymd = kstDay(tomorrow);
const dateLabel = new Intl.DateTimeFormat('ko-KR').format(tomorrow);
const iso = (clock: string) => `${ymd}T${clock}+09:00`;

async function freePort(): Promise<number> {
  const server = createServer();
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('No local test port');
  const port = address.port;
  await new Promise<void>(resolve => server.close(() => resolve()));
  return port;
}

test('실제 Svelte → 격리 FastAPI/SQLite → 단일 mock Kakao 아웃박스', async ({ page, request }) => {
  const root = mkdtempSync(resolve(tmpdir(), 'aura-integration-'));
  const port = await freePort();
  const backend = `http://127.0.0.1:${port}`;
  let server: ChildProcess | undefined;
  try {
    server = spawn(resolve(fast, '.venv/bin/python'), ['-m', 'uvicorn', 'personal_project.tests.aura_integration_server:app', '--host', '127.0.0.1', '--port', String(port)], {
      cwd: fast, stdio: 'ignore', env: { ...process.env, PERSONAL_PROJECT_DB_PATH: resolve(root, 'aura.sqlite'), AURA_INTEGRATION_ROOT: root, PYTHONPATH: fast }
    });
    await expect.poll(async () => {
      try { return (await request.get(`${backend}/openapi.json`, { timeout: 1000 })).status(); }
      catch { return 0; }
    }, { timeout: 20000 }).toBe(200);
    const api = `${backend}/api/personal/aura`;
    const createSchool = await request.post(`${api}/schools`, { data: { admission_year: 2026, school_name: '합성검증고' } });
    expect(createSchool.status()).toBe(201);
    const sid = (await createSchool.json()).id;
    const create = async (number: number, start: string, end: string, modality: string) => {
      const response = await request.post(`${api}/rounds`, { data: {
        school_id: sid, round_number: number, student_names: [`합성${number}`], start_time: iso(start), end_time: iso(end), modality,
        progress_stage: 'grade1_semester1', allow_overlap: true
      } });
      expect(response.status(), await response.text()).toBe(201);
      return (await response.json()).id as number;
    };
    const onsite = await create(1, '10:00:00', '11:00:00', 'unverified');
    const near = await create(2, '11:59:59', '12:29:59', 'remote');
    const far = await create(3, '12:00:00', '12:30:00', 'remote');
    await page.route('**/auth/isjwt?key=mainauth', route => route.fulfill({ json: { sub: '301', data: { id: '301', name: '합성 계정' }, exp: 9999999999 } }));
    await page.route('**/api/personal/**', async route => {
      const path = new URL(route.request().url()).pathname;
      const response = await route.fetch({ url: backend + path + new URL(route.request().url()).search });
      await route.fulfill({ response });
    });
    await page.goto('/personal-project/aura');
    await expect(page.locator('.round-row').first()).toBeVisible();
    const previewButton = page.getByRole('button', { name: `${dateLabel} 강의실 배정 요청문 만들기` });
    await previewButton.click();
    await expect(page.getByRole('button', { name: '복사하기' })).toBeDisabled();
    await page.getByRole('button', { name: '닫기' }).click();
    await page.locator('.slot.busy').first().click();
    await page.getByLabel(/진행 방식/).selectOption('in_person');
    await page.getByRole('button', { name: '일정 수정' }).click();
    await expect.poll(async () => (await (await request.get(`${api}/rounds/${onsite}`)).json()).modality).toBe('in_person');
    await previewButton.click();
    const uiText = await page.getByRole('textbox', { name: '강의실 배정 요청문' }).inputValue();
    expect(uiText).toContain('합성2 (비대면)');
    expect(uiText).not.toContain('합성3');
    expect(uiText).not.toContain('강의실 불필요');
    const first = await (await request.post(`${backend}/__test/classroom-tick`)).json();
    expect(first.result.state).toBe('succeeded');
    expect(first.result.roundIds).toEqual([onsite, near]);
    expect(first.result.nearbyRemoteRounds[0].gapSeconds).toBe(3599);
    expect(first.calls.map((call: {command: string}) => call.command)).toEqual(['search', 'send']);
    expect(first.calls[1].text).toBe(uiText);
    const second = await (await request.post(`${backend}/__test/classroom-tick`)).json();
    expect(second.result.id).toBe(first.result.id);
    expect(second.calls).toEqual([]);
    expect(far).not.toBe(near);
  } finally {
    server?.kill();
    rmSync(root, { recursive: true, force: true });
  }
});
