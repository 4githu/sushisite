import { defineConfig } from '@playwright/test';

const externalBaseUrl = process.env.PLAYWRIGHT_BASE_URL;

export default defineConfig({
	use: { baseURL: externalBaseUrl ?? 'http://127.0.0.1:4173' },
	webServer: externalBaseUrl
		? undefined
		: { command: 'npm run build && npm run preview', port: 4173 },
	testMatch: '**/*.e2e.{ts,js}'
});
