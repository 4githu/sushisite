import { test, expect } from '@playwright/test';
test('drive notebook hierarchy opens an owned page and shows shared account storage', async ({
	page
}) => {
	const book = {
		id: 'book-qa',
		title: '전공 노트',
		sections: [
			{
				id: 'section-qa',
				title: '역학',
				notes: [
					{
						id: 'page-qa',
						title: '운동의 법칙',
						paper: { pattern: 'ruled', color: 'white' },
						updatedAt: 1
					}
				]
			}
		]
	};
	const catalog = {
		version: 1,
		notebooks: [book],
		active: { notebook: book.id, section: 'section-qa', note: 'page-qa' },
		defaults: { pattern: 'ruled', color: 'white' }
	};
	await page.route('**/auth/isjwt?*', (r) =>
		r.fulfill({
			json: { sub: 'qa', data: { id: 'drive-notes-synthetic', name: '확인' }, exp: 9999999999 }
		})
	);
	await page.route('**/api/personal/**', (r) => {
		const path = decodeURIComponent(new URL(r.request().url()).pathname);
		let json: any = {};
		if (path.endsWith('/drive/status'))
			json = {
				quotaBytes: 524288000,
				usedBytes: 10240,
				fileBytes: 4096,
				noteBytes: 4096,
				noteHistoryBytes: 1024,
				attachmentBytes: 2048,
				googleAccounts: [],
				transferDays: 15
			};
		else if (path.endsWith('/drive/items')) json = [];
		else if (path.endsWith('/drive/library'))
			json = { folders: [], allFolders: [], trail: [], placements: {}, shared: [] };
		else if (path.endsWith('/boards')) json = { canAdmin: false };
		else if (path.endsWith('/documents/notes:library:v1')) json = { data: catalog, revision: 1 };
		else if (path.includes('/documents/note:'))
			json = {
				data: {
					engine: 'netaq-notebook-v2',
					title: '운동의 법칙',
					pages: [{ id: 'paper', w: 794, h: 1123, source: null, items: [] }]
				},
				revision: 1
			};
		return r.fulfill({ json });
	});
	await page.goto('http://127.0.0.1:5195/personal-project/calendar/drive');
	await page.getByRole('tab', { name: '보관함', exact: true }).click();
	await expect(page.locator('.drive-storage-breakdown')).toContainText('노트·저장기록 4.0 KB');
	await page.locator('.drive-notebooks>summary').click();
	await page.locator('.notebook-branch>summary').click();
	await page.locator('.section-branch>summary').click();
	await expect(page.getByRole('link', { name: '운동의 법칙' })).toBeVisible();
	await page.screenshot({ path: '/tmp/notes-drive-folder-desktop.png' });
	await page.getByRole('link', { name: '운동의 법칙' }).click();
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'운동의 법칙'
	);
	await expect(page.getByRole('combobox', { name: '노트북 선택' })).toHaveValue('book-qa');
});
test('quota rejection keeps the current note and offers drive management in another tab', async ({
	page
}) => {
	const catalog = {
		version: 1,
		notebooks: [
			{
				id: 'b',
				title: '노트북',
				sections: [
					{
						id: 's',
						title: '섹션',
						notes: [
							{
								id: 'n',
								title: '페이지',
								paper: { pattern: 'ruled', color: 'white' },
								updatedAt: 1
							}
						]
					}
				]
			}
		],
		active: { notebook: 'b', section: 's', note: 'n' },
		defaults: { pattern: 'ruled', color: 'white' }
	};
	await page.route('**/auth/isjwt?*', (r) =>
		r.fulfill({ json: { sub: 'qa', data: { id: 'drive-notes-synthetic' }, exp: 9999999999 } })
	);
	await page.route('**/api/personal/**', (r) => {
		const path = decodeURIComponent(new URL(r.request().url()).pathname);
		if (path.endsWith('/documents/notes:library:v1'))
			return r.fulfill({ json: { data: catalog, revision: 1 } });
		if (path.includes('/documents/note:')) {
			if (r.request().method() === 'PUT') {
				const body = r.request().postDataJSON();
				if (body.data.title === '공간 초과 확인')
					return r.fulfill({ status: 413, json: { detail: '개인 저장 공간이 부족합니다' } });
				return r.fulfill({ json: { revision: 1 } });
			}
			return r.fulfill({
				json: {
					data: {
						engine: 'netaq-notebook-v2',
						title: '페이지',
						pages: [{ id: 'p', source: null, w: 794, h: 1123, items: [] }]
					},
					revision: 1
				}
			});
		}
		return r.fulfill({ json: {} });
	});
	await page.goto('http://127.0.0.1:5195/personal-project/notes');
	await page.getByRole('textbox', { name: '노트 제목', exact: true }).fill('공간 초과 확인');
	const link = page.getByRole('link', { name: '드라이브 용량 확인 ↗', exact: true });
	await expect(link).toBeVisible();
	await expect(link).toHaveAttribute('target', '_blank');
	await expect(page.getByRole('textbox', { name: '노트 제목', exact: true })).toHaveValue(
		'공간 초과 확인'
	);
	await expect(page.locator('.save-state')).toContainText('저장 공간 부족');
});
