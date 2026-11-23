import { page } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import LocalPairingPrototype from './LocalPairingPrototype.svelte';
import { createFakePairingTransport } from './pairing-prototype';

const successfulTransport = () => {
	const transport = createFakePairingTransport();
	vi.spyOn(transport, 'pair');
	return transport;
};

describe('local pairing prototype', () => {
	it('is off by default and does not call the fake transport', async () => {
		const transport = successfulTransport();
		render(LocalPairingPrototype, { props: { transport } });

		await expect.element(page.getByRole('checkbox', { name: /실험 UI 표시/ })).not.toBeChecked();
		await expect.element(page.getByRole('button', { name: /가상 페어링 확인/ })).toBeDisabled();
		expect(transport.pair).not.toHaveBeenCalled();
	});

	it('states clearly that the experiment is not a live subscription connection', async () => {
		render(LocalPairingPrototype);

		await expect.element(page.getByText(/실험 기능/)).toBeInTheDocument();
		await expect.element(page.getByText(/실제 연결이 아닙니다/)).toBeInTheDocument();
		await expect
			.element(page.getByText(/구독 제공자 연결이나 번역은 제공하지 않으며/))
			.toBeInTheDocument();
	});

	it('shows a fake success without exposing pairing codes or session tokens', async () => {
		const transport = successfulTransport();
		render(LocalPairingPrototype, { props: { transport } });

		await page.getByRole('checkbox', { name: /실험 UI 표시/ }).click();
		await page.getByRole('button', { name: /가상 페어링 확인/ }).click();

		await expect.element(page.getByRole('status')).toHaveTextContent(/가상 응답 확인/);
		await expect.element(page.getByRole('status')).toHaveTextContent(/실제 연결 아님/);
		expect(transport.pair).toHaveBeenCalledOnce();
		expect(document.body.textContent).not.toMatch(/pairing_code|session_token|Bearer|fake-secret/);
		expect(document.body.textContent).not.toContain('not-a-real-session-token');
	});

	it('shows a sanitized fake failure without rendering transport details', async () => {
		const transport = createFakePairingTransport('failure');
		vi.spyOn(transport, 'pair');
		render(LocalPairingPrototype, { props: { transport } });

		await page.getByRole('checkbox', { name: /실험 UI 표시/ }).click();
		await page.getByRole('button', { name: /가상 페어링 확인/ }).click();

		await expect.element(page.getByRole('alert')).toHaveTextContent(/가상 요청 실패/);
		expect(document.body.textContent).not.toContain('FAKE_PAIRING_UNAVAILABLE');
		expect(document.body.textContent).not.toContain('fake-secret');
	});
});
