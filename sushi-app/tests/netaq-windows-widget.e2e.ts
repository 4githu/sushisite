import { test, expect } from '@playwright/test';
import { _electron as electron } from 'playwright';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const require = createRequire(import.meta.url);
test('native desktop widget: IPC, capture retry, offline content and revoked privacy', async () => {
	const app = await electron.launch({
		executablePath: require('../../windows-widget/node_modules/electron'),
		args: [resolve('../windows-widget/test/launch.cjs')],
		timeout: 20000
	});
	try {
		const page = await app.firstWindow();
		await expect(page.getByText('생명과학 세미나', { exact: true })).toBeVisible();
		expect(
			await page.evaluate(() => ({
				node: typeof (window as any).require,
				secret: (window as any).netaq.token
			}))
		).toEqual({ node: 'undefined', secret: undefined });
		await page.getByRole('checkbox', { name: '자료 보내기 완료', exact: true }).check();
		await expect
			.poll(() =>
				app.evaluate(() =>
					((globalThis as any).widgetTestWrites || []).filter((w: any) => w.path.endsWith('/task'))
				)
			)
			.toHaveLength(1);
		await app.evaluate(() => {
			(globalThis as any).widgetTestFailCapture = true;
		});
		await page.getByRole('textbox', { name: '빠른 기록', exact: true }).fill('응답 실패에도 보존');
		await page.getByRole('button', { name: '기록', exact: true }).click();
		await expect(page.getByRole('alert')).not.toBeEmpty();
		await expect(page.getByRole('textbox', { name: '빠른 기록', exact: true })).toHaveValue(
			'응답 실패에도 보존'
		);
		await page.getByRole('button', { name: '기록', exact: true }).click();
		await expect(page.getByRole('status')).toContainText('정리함에 기록했어요');
		const writes = await app.evaluate(() =>
			((globalThis as any).widgetTestWrites || []).filter((w: any) => w.path.endsWith('/capture'))
		);
		expect(writes[0].body.id).toBe(writes[1].body.id);
		await app.evaluate(() => {
			(globalThis as any).widgetTestOffline = true;
		});
		await page.getByRole('button', { name: '새로고침', exact: true }).click();
		await expect(page.getByRole('alert')).toContainText('인터넷');
		await expect(page.getByText('생명과학 세미나', { exact: true })).toBeVisible();
		await page.screenshot({
			path: '/Users/sagi/Documents/Codex/2026-11-11/netaq/outputs/netaq-windows-widget.png',
			fullPage: true
		});
		await app.evaluate(() => {
			(globalThis as any).widgetTestOffline = false;
			(globalThis as any).widgetTestRevoked = true;
		});
		await page.getByRole('button', { name: '새로고침', exact: true }).click();
		await expect(page.getByRole('heading', { name: '계정 연결', exact: true })).toBeVisible();
		await expect(page.getByText('생명과학 세미나', { exact: true })).toHaveCount(0);
	} finally {
		await app.close();
	}
});
