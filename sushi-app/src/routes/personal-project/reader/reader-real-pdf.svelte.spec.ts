import { page } from 'vitest/browser';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import ReaderPage from './+page.svelte';

describe('Reader real PDF extraction in the browser', () => {
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
