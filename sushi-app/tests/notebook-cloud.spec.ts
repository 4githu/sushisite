import { test, expect } from '@playwright/test';
const base = 'http://127.0.0.1:5194/';
test('account-backed notebooks save through the shared API and reopen in another browser context', async ({
	browser
}) => {
	const docs = new Map<string, { revision: number; data: any }>();
	async function device() {
		const context = await browser.newContext();
		await context.route('**/auth/isjwt?*', (route) =>
			route.fulfill({
				json: { sub: 'qa', data: { id: 'notebook-synthetic-qa', name: '테스트' }, exp: 9999999999 }
			})
		);
		await context.route('**/api/personal/documents/**', async (route) => {
			const key = decodeURIComponent(
				new URL(route.request().url()).pathname.split('/documents/')[1]
			);
			if (route.request().method() === 'PUT') {
				const body = route.request().postDataJSON(),
					existing = docs.get(key);
				if ((existing?.revision || 0) !== body.revision)
					return route.fulfill({ status: 409, json: { detail: 'revision conflict' } });
				const value = { data: body.data, revision: body.revision + 1 };
				docs.set(key, value);
				return route.fulfill({ json: { revision: value.revision } });
			}
			return route.fulfill({ json: docs.get(key) || { data: null, revision: 0 } });
		});
		return context;
	}
	const first = await device(),
		p = await first.newPage();
	await p.goto(base);
	await p.getByRole('textbox', { name: '노트 제목', exact: true }).fill('계정 간 공유 확인');
	await p.getByRole('button', { name: '텍스트', exact: true }).click();
	await p.locator('.paper').click({ position: { x: 90, y: 90 } });
	await p.locator('.paper [contenteditable=true]').fill('두 번째 기기에서 읽는 필기');
	await expect
		.poll(() => docs.get('note:current:v2')?.data?.pages?.[0]?.chunks?.length || 0)
		.toBeGreaterThan(0);
	await expect
		.poll(() => docs.get('notes:library:v1')?.data.notebooks[0].sections[0].notes[0].title)
		.toBe('계정 간 공유 확인');
	const second = await device(),
		q = await second.newPage();
	await q.goto(base);
	await expect(q.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'계정 간 공유 확인'
	);
	await expect(q.locator('.text-object')).toContainText('두 번째 기기에서 읽는 필기');
	await first.close();
	await second.close();
});
test('opening the account library never uploads an existing local notebook automatically', async ({
	page
}) => {
	const writes: any[] = [];
	await page.route('**/auth/isjwt?*', (r) =>
		r.fulfill({ json: { sub: 'qa', data: { id: 'notebook-synthetic-qa' }, exp: 9999999999 } })
	);
	await page.route('**/api/personal/documents/**', (r) => {
		if (r.request().method() === 'PUT') {
			writes.push(r.request().postDataJSON());
			return r.fulfill({ json: { revision: 1 } });
		}
		return r.fulfill({ json: { data: null, revision: 0 } });
	});
	await page.goto(base + '?workspace=1');
	await page.locator('.paper').waitFor();
	await page.evaluate(async () => {
		const db = await new Promise<IDBDatabase>((resolve) => {
			const r = indexedDB.open('netaq-notes', 1);
			r.onsuccess = () => resolve(r.result);
		});
		await new Promise<void>((resolve) => {
			const tx = db.transaction('workspace', 'readwrite');
			tx.objectStore('workspace').put(
				{
					title: '로컬 전용 합성 테스트',
					pages: [
						{
							w: 794,
							h: 1123,
							items: [
								{
									kind: 'text',
									id: 'generated',
									x: 1,
									y: 1,
									w: 20,
									h: 20,
									html: '<p>SYNTHETIC_LOCAL_ONLY</p>'
								}
							]
						}
					]
				},
				'current'
			);
			tx.oncomplete = () => resolve();
		});
		db.close();
	});
	await page.goto(base);
	await expect(
		page.getByRole('button', { name: 'NETAQ 계정으로 복사', exact: true })
	).toBeVisible();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'첫 번째 페이지'
	);
	await expect(page.locator('.save-state')).toContainText('서버에 저장됨');
	expect(JSON.stringify(writes)).not.toContain('SYNTHETIC_LOCAL_ONLY');
	expect(JSON.stringify(writes)).not.toContain('로컬 전용 합성 테스트');
});
