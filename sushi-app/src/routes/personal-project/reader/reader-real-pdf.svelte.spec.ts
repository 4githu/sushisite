import { page, userEvent } from 'vitest/browser';
import { describe, expect, it, vi } from 'vitest';
vi.mock('$lib/personal-project/shared/auth', () => ({
	privateCacheUser: () => 'synthetic-reader-user'
}));
import { render } from 'vitest-browser-svelte';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import ReaderPage from './+page.svelte';
import attentionUrl from '../../../../tests/fixtures/reader-attention.pdf?url';
import bertUrl from '../../../../tests/fixtures/reader-bert.pdf?url';

describe('Reader real PDF extraction in the browser', () => {
	it.each([
		['attention.pdf', attentionUrl],
		['bert.pdf', bertUrl]
	])(
		'opens actual research PDF %s and renders a selectable text layer',
		async (name, url) => {
			const blob = await (await fetch(url)).blob();
			render(ReaderPage);
			await page
				.getByLabelText(/PDF 열기|다른 PDF 열기/)
				.upload(new File([blob], name, { type: 'application/pdf' }));
			await expect.element(page.getByRole('button', { name: 'PDF 지면 보기' })).toBeInTheDocument();
			await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
			await expect
				.poll(() => document.querySelector('.textLayer')?.textContent?.length ?? 0)
				.toBeGreaterThan(50);
			const span = document.querySelector<HTMLElement>('.textLayer span');
			expect(span?.getBoundingClientRect().height).toBeGreaterThan(0);
			const range = document.createRange();
			range.selectNodeContents(span!);
			const selection = window.getSelection()!;
			selection.removeAllRanges();
			selection.addRange(range);
			await page.getByRole('button', { name: '텍스트 선택 확인' }).click();
			await expect
				.element(page.getByRole('button', { name: '선택 하이라이트 저장' }))
				.toBeEnabled();
			await page.getByRole('button', { name: '선택 하이라이트 저장' }).click();
			await expect.poll(() => document.querySelectorAll('.marks div').length).toBeGreaterThan(0);
			await expect
				.poll(() =>
					Array.from(
						{ length: localStorage.length },
						(_, i) => localStorage.getItem(localStorage.key(i)!) || ''
					).some((v) => v.includes('"kind":"highlight"'))
				)
				.toBe(true);
			const initialLeft = document.querySelector<HTMLElement>('.marks div')!.style.left;
			await page.getByRole('button', { name: '확대' }).click();
			await expect
				.poll(() => document.querySelector<HTMLElement>('.marks div')?.style.left)
				.toBe(initialLeft);
			await page.getByRole('button', { name: '다음 페이지' }).click();
			await expect.element(page.getByLabelText('PDF 페이지')).toHaveValue(2);
		},
		30000
	);
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
	it('renders PDF pages and supports page and zoom controls', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('First rendered page', { font });
		pdf.addPage().drawText('Second rendered page', { font });
		const bytes = await pdf.save();
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(
			new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'two-pages.pdf', {
				type: 'application/pdf'
			})
		);
		await expect.element(page.getByText('First rendered page')).toBeInTheDocument();
		await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
		await expect.element(page.getByLabelText('PDF 페이지')).toHaveValue(1);
		await expect
			.poll(() => document.querySelector('.textLayer')?.textContent)
			.toContain('First rendered page');
		await expect
			.poll(
				() =>
					document.querySelector<HTMLCanvasElement>('[aria-label="원본 PDF 지면"] canvas')?.width ??
					0
			)
			.toBeGreaterThan(0);
		await page.getByRole('button', { name: '다음 페이지' }).click();
		await expect.element(page.getByLabelText('PDF 페이지')).toHaveValue(2);
		await page.getByRole('button', { name: '확대' }).click();
		await expect.element(page.getByText('125%')).toBeInTheDocument();
	});
	it('persists a page-relative region and restores it after reopening the PDF', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('Region annotation test', { font });
		const bytes = await pdf.save();
		const file = new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'region-test.pdf', {
			type: 'application/pdf'
		});
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(file);
		await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
		await expect
			.poll(() => document.querySelector('.textLayer')?.textContent)
			.toContain('Region annotation test');
		await page.getByText('키보드로 영역 선택').click();
		await page.getByRole('button', { name: '좌표 영역 선택' }).click();
		await page.getByRole('button', { name: '영역 주석 저장' }).click();
		await expect
			.poll(() =>
				Array.from(
					{ length: localStorage.length },
					(_, i) => localStorage.getItem(localStorage.key(i)!) || ''
				).some((v) => v.includes('"kind":"region"'))
			)
			.toBe(true);
		await page.getByRole('button', { name: '확대' }).click();
		await expect
			.poll(() => document.querySelector<HTMLElement>('.marks .region')?.style.left)
			.toBe('10%');
		await page.getByLabelText(/다른 PDF 열기/).upload(file);
		await expect.element(page.getByRole('button', { name: 'PDF 지면 보기' })).toBeInTheDocument();
		await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
		await expect
			.poll(() => document.querySelector<HTMLElement>('.marks .region')?.style.left)
			.toBe('10%');
	});
	it('sends a cropped region and appends a mocked explanation to the note', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('Image crop test', { font });
		const bytes = await pdf.save();
		const originalFetch = window.fetch.bind(window);
		let payload!: { image: { mime_type: string; base64: string }; caption: string };
		const fetchSpy = vi.spyOn(window, 'fetch').mockImplementation(async (input, init) => {
			if (String(input).includes('/reader/explain-image')) {
				payload = JSON.parse(String(init?.body));
				return new Response(
					JSON.stringify({ explanation: 'Mock explanation for selected image' }),
					{ status: 200, headers: { 'Content-Type': 'application/json' } }
				);
			}
			return originalFetch(input, init);
		});
		try {
			render(ReaderPage);
			await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(
				new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'crop-test.pdf', {
					type: 'application/pdf'
				})
			);
			await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
			await expect
				.poll(() => document.querySelector('.textLayer')?.textContent)
				.toContain('Image crop test');
			await page.getByRole('button', { name: '영역 선택', exact: true }).click();
			const overlay = document.querySelector<HTMLElement>('.region-overlay')!;
			const source = document.createElement('div'),
				target = document.createElement('div');
			for (const [element, x, y] of [
				[source, 10, 10],
				[target, 40, 30]
			] as const) {
				Object.assign(element.style, {
					position: 'absolute',
					left: `${x}%`,
					top: `${y}%`,
					width: '4px',
					height: '4px'
				});
				overlay.append(element);
			}
			await userEvent.dragAndDrop(source, target);
			await expect
				.element(page.getByRole('button', { name: '선택 이미지 설명 요청' }))
				.toBeInTheDocument();
			const mark = document.querySelector<HTMLElement>('.marks .selected')!;
			expect(parseFloat(mark.style.left)).toBeCloseTo(10, 0);
			expect(parseFloat(mark.style.top)).toBeCloseTo(10, 0);
			expect(parseFloat(mark.style.width)).toBeCloseTo(30, 0);
			expect(parseFloat(mark.style.height)).toBeCloseTo(20, 0);
			await page.getByLabelText('캡션').fill('Synthetic caption');
			await page.getByRole('button', { name: '선택 이미지 설명 요청' }).click();
			await expect
				.element(page.getByText('Mock explanation for selected image'))
				.toBeInTheDocument();
			expect(payload.image.mime_type).toBe('image/jpeg');
			expect(payload.image.base64.startsWith('/9j/')).toBe(true);
			expect(payload.caption).toBe('Synthetic caption');
			const image = new Image();
			image.src = `data:image/jpeg;base64,${payload.image.base64}`;
			await image.decode();
			const canvas = document.querySelector<HTMLCanvasElement>(
				'[aria-label="원본 PDF 지면"] canvas'
			)!;
			expect(image.width).toBeCloseTo(canvas.width * 0.3, -1);
			expect(image.height).toBeCloseTo(canvas.height * 0.2, -1);
			await page.getByRole('button', { name: '설명을 메모에 넣기' }).click();
			await expect
				.poll(() =>
					Array.from(
						{ length: localStorage.length },
						(_, i) => localStorage.getItem(localStorage.key(i)!) || ''
					).some((v) => v.includes('Mock explanation for selected image'))
				)
				.toBe(true);
		} finally {
			fetchSpy.mockRestore();
		}
	});
	it('supports mobile viewport and keyboard page navigation on a real paper', async () => {
		await page.viewport(390, 844);
		try {
			const blob = await (await fetch(attentionUrl)).blob();
			render(ReaderPage);
			await page
				.getByLabelText(/PDF 열기|다른 PDF 열기/)
				.upload(new File([blob], 'mobile-paper.pdf', { type: 'application/pdf' }));
			await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
			await expect
				.poll(() => document.querySelector('.textLayer')?.textContent?.length ?? 0)
				.toBeGreaterThan(50);
			const next = document.querySelector<HTMLButtonElement>('button[aria-label="다음 페이지"]')!;
			next.focus();
			await userEvent.keyboard('{Enter}');
			await expect.element(page.getByLabelText('PDF 페이지')).toHaveValue(2);
			await page.screenshot({ path: 'reader-mobile.png' });
		} finally {
			await page.viewport(1280, 720);
		}
	}, 30000);
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
