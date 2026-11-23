import { page } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
vi.mock('$lib/personal-project/shared/auth', () => ({
	privateCacheUser: () => 'synthetic-reader-user'
}));
import { render } from 'vitest-browser-svelte';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import ReaderPage from './+page.svelte';

describe('Reader real PDF extraction in the browser', () => {
	it('does not persist an editor initialization without a user edit', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('Synthetic initialization regression.', { font });
		const bytes = await pdf.save();
		const setItem = vi.spyOn(Storage.prototype, 'setItem');
		try {
			render(ReaderPage);
			const file = new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'initialization.pdf', {
				type: 'application/pdf'
			});
			await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(file);
			await expect
				.element(page.getByText('Synthetic initialization regression.'))
				.toBeInTheDocument();
			render(ReaderPage);
			const inputs = document.querySelectorAll<HTMLInputElement>('input[type=file]');
			const transfer = new DataTransfer();
			transfer.items.add(file);
			inputs[inputs.length - 1].files = transfer.files;
			inputs[inputs.length - 1].dispatchEvent(new Event('change', { bubbles: true }));
			await expect
				.poll(() => document.querySelectorAll('button[aria-label="p1-s1 메모"]').length)
				.toBe(2);
			await new Promise((resolve) => setTimeout(resolve, 500));
			expect(
				setItem.mock.calls.filter(([key]) => key.startsWith('paiper.reader.notes.v2.'))
			).toHaveLength(0);
			(document.querySelector('button[aria-label="p1-s1 메모"]') as HTMLButtonElement).click();
			const note = page.getByLabelText('p1-s1 메모 내용');
			await note.fill('Synthetic tab A preserved note');
			await expect
				.poll(() =>
					setItem.mock.calls.some(
						([key, value]) =>
							key.startsWith('paiper.reader.notes.v2.') &&
							value.includes('Synthetic tab A preserved note')
					)
				)
				.toBe(true);
			await expect.element(page.getByText(/다른 탭에서 변경/)).not.toBeInTheDocument();
		} finally {
			setItem.mockRestore();
		}
	});
	it('opens a synthetic PDF and displays locally extracted text', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('Synthetic browser research text.', { font });
		const bytes = await pdf.save();
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(
			new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'browser-test.pdf', {
				type: 'application/pdf'
			})
		);
		await expect.element(page.getByText('Synthetic browser research text.')).toBeInTheDocument();
		await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
		await expect.element(page.getByTitle('원본 PDF 지면')).toBeInTheDocument();
	});
});
