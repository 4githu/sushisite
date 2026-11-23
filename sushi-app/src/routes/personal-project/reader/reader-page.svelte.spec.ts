import { page, userEvent } from 'vitest/browser';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';
import ReaderPage from './+page.svelte';
import { extractPdfSegments, translateSegments } from '$lib/personal-project/reader/reader';
import { PersonalApiError } from '$lib/personal-project/shared/api';

const navigation = vi.hoisted(() => ({ before: null as null | ((nav: { cancel: () => void }) => void) }));
vi.mock('$app/navigation', () => ({ beforeNavigate: (fn: typeof navigation.before) => { navigation.before = fn; } }));

vi.mock('$lib/personal-project/shared/auth', () => ({
	privateCacheUser: () => 'synthetic-race-user'
}));

vi.mock('$lib/personal-project/reader/reader', async (importOriginal) => {
	const actual = await importOriginal<typeof import('$lib/personal-project/reader/reader')>();
	return {
		...actual,
		extractPdfSegments: vi
			.fn()
			.mockResolvedValue([{ id: 'p1-s1', text: 'Synthetic source text.' }]),
		translateSegments: vi.fn().mockResolvedValue([{ id: 'p1-s1', text: '합성 번역문.' }])
	};
});

describe('Reader application workspace', () => {
	it('shows a compact app header rather than a landing page or pairing prototype', async () => {
		render(ReaderPage);
		await expect.element(page.getByRole('link', { name: '논문 목록' })).toBeInTheDocument();
		await expect.element(page.getByText('READ AT YOUR OWN PACE · 01')).not.toBeInTheDocument();
		await expect.element(page.getByLabelText(/번역 경로/)).not.toBeInTheDocument();
	});
});

describe('Reader transfer consent', () => {
	it('does not overwrite a different tab and keeps the local draft exportable', async () => {
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(new File(['conflict'], 'conflict.pdf', { type: 'application/pdf' }));
		await page.getByRole('button', { name: 'p1-s1 메모' }).click();
		await page.getByLabelText('p1-s1 메모 내용').fill('first');
		await expect.poll(() => Object.keys(localStorage).some((k) => k.startsWith('paiper.reader.notes.v2.') && localStorage.getItem(k)?.includes('first'))).toBe(true);
		const key = Object.keys(localStorage).find((k) => k.startsWith('paiper.reader.notes.v2.') && localStorage.getItem(k)?.includes('first'))!;
		const other = JSON.stringify({ notes: { 'p1-s1': 'other tab' } });
		localStorage.setItem(key, other);
		await page.getByLabelText('p1-s1 메모 내용').fill('local draft');
		expect(localStorage.getItem(key)).toBe(other);
		await expect.element(page.getByText(/다른 탭에서 변경/)).toBeInTheDocument();
		await expect.element(page.getByLabelText('p1-s1 메모 내용')).toHaveValue('local draft');
	});

	it('blocks internal navigation after a storage write fails and user declines', async () => {
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(new File(['nav'], 'nav.pdf', { type: 'application/pdf' }));
		await page.getByRole('button', { name: 'p1-s1 메모' }).click();
		const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
		try {
			await page.getByLabelText('p1-s1 메모 내용').fill('unsaved');
			const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
			const cancel = vi.fn();
			expect(navigation.before).toBeTypeOf('function');
			navigation.before?.({ cancel });
			expect(cancel).toHaveBeenCalled();
			confirm.mockRestore();
		} finally { set.mockRestore(); }
	});

	it('aborts an active translation when another PDF is selected', async () => {
		let signal: AbortSignal | undefined;
		vi.mocked(translateSegments).mockImplementationOnce((_s, _p, _path, value) => { signal = value; return new Promise(() => {}); });
		render(ReaderPage);
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(new File(['a'], 'a.pdf', { type: 'application/pdf' }));
		await page.getByRole('checkbox', { name: /텍스트 전송에 동의/ }).click();
		await page.getByRole('button', { name: /Translate to Korean/ }).click();
		await page.getByLabelText(/PDF 열기|다른 PDF 열기/).upload(new File(['b'], 'b.pdf', { type: 'application/pdf' }));
		expect(signal?.aborted).toBe(true);
	});
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('does not let an older extraction overwrite a newer PDF', async () => {
		let resolveFirst!: (value: { id: string; text: string }[]) => void;
		vi.mocked(extractPdfSegments)
			.mockImplementationOnce(
				() =>
					new Promise((resolve) => {
						resolveFirst = resolve;
					})
			)
			.mockResolvedValueOnce([{ id: 'p1-s1', text: 'Second document' }]);
		render(ReaderPage);
		function select(name: string) {
			const input = page.getByLabelText(/PDF 열기|다른 PDF 열기/).element() as HTMLInputElement;
			const transfer = new DataTransfer();
			transfer.items.add(new File([name], name, { type: 'application/pdf' }));
			input.files = transfer.files;
			input.dispatchEvent(new Event('change', { bubbles: true }));
		}
		select('first.pdf');
		await expect.poll(() => !!resolveFirst).toBe(true);
		select('second.pdf');
		await expect.element(page.getByText('Second document')).toBeInTheDocument();
		resolveFirst([{ id: 'p1-s1', text: 'Stale first document' }]);
		await new Promise((resolve) => setTimeout(resolve, 50));
		await expect.element(page.getByText('Second document')).toBeInTheDocument();
		await expect.element(page.getByText('Stale first document')).not.toBeInTheDocument();
	});

	it('uses the existing shared route after explicit consent without a localhost choice', async () => {
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['synthetic'], 'test.pdf', { type: 'application/pdf' }));
		await expect.element(page.getByLabelText(/번역 경로/)).not.toBeInTheDocument();
		await page.getByRole('checkbox', { name: /텍스트 전송에 동의/ }).click();
		await page.getByRole('button', { name: /Translate to Korean/ }).click();
		await expect.poll(() => vi.mocked(translateSegments).mock.calls.length).toBe(1);
		expect(vi.mocked(translateSegments).mock.calls[0][2]).toBe('shared');
	});

	it('shows connection needed for provider-unavailable and permits retry', async () => {
		vi.mocked(translateSegments).mockRejectedValueOnce(
			new PersonalApiError(503, 'generic', 'translation_provider_unavailable')
		);
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['synthetic'], 'unavailable.pdf', { type: 'application/pdf' }));
		await page.getByRole('checkbox', { name: /텍스트 전송에 동의/ }).click();
		await page.getByRole('button', { name: /Translate to Korean/ }).click();
		await expect.element(page.getByRole('alert')).toHaveTextContent('번역 연결이 필요합니다');
		await page.getByRole('button', { name: /Translate to Korean/ }).click();
		await expect.element(page.getByText('합성 번역문.')).toBeInTheDocument();
	});

	it('opens the PDF viewer with the keyboard', async () => {
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['pdf'], 'keyboard.pdf', { type: 'application/pdf' }));
		const button = page.getByRole('button', { name: 'PDF 지면 보기' });
		await button.element().focus();
		await userEvent.keyboard('{Enter}');
		await expect.element(page.getByTitle('원본 PDF 지면')).toBeInTheDocument();
	});

	it('offers the original PDF for visual inspection without uploading it', async () => {
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['synthetic file bytes'], 'synthetic.pdf', { type: 'application/pdf' }));
		await page.getByRole('button', { name: 'PDF 지면 보기' }).click();
		await expect.element(page.getByTitle('원본 PDF 지면')).toBeInTheDocument();
	});

	it('keeps a segment note while switching reading layouts', async () => {
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['synthetic file bytes'], 'synthetic.pdf', { type: 'application/pdf' }));
		await page.getByRole('button', { name: 'p1-s1 메모' }).click();
		await page.getByLabelText('p1-s1 메모 내용').fill('합성 메모');
		await page.getByRole('button', { name: '원문만' }).click();
		await expect.element(page.getByLabelText('p1-s1 메모 내용')).toHaveValue('합성 메모');
	});

	it('lets readers switch to source-only reading and back without losing translation', async () => {
		render(ReaderPage);
		await page
			.getByLabelText(/PDF 열기|다른 PDF 열기/)
			.upload(new File(['synthetic file bytes'], 'synthetic.pdf', { type: 'application/pdf' }));
		await page.getByRole('checkbox', { name: /텍스트 전송에 동의/ }).click();
		await page.getByRole('button', { name: /Translate to Korean/ }).click();
		await expect.element(page.getByText('합성 번역문.')).toBeInTheDocument();
		await page.getByRole('button', { name: '원문만' }).click();
		await expect.element(page.getByText('Synthetic source text.')).toBeInTheDocument();
		await expect.element(page.getByText('합성 번역문.')).not.toBeInTheDocument();
		await page.getByRole('button', { name: '나란히' }).click();
		await expect.element(page.getByText('합성 번역문.')).toBeInTheDocument();
	});

	it('discloses the OpenAI text transfer accessibly before consent and keeps consent and send separate', async () => {
		render(ReaderPage);
		const fileInput = page.getByLabelText(/PDF 열기|다른 PDF 열기/);
		await fileInput.upload(
			new File(['synthetic file bytes'], 'synthetic.pdf', { type: 'application/pdf' })
		);
		await expect.poll(() => vi.mocked(extractPdfSegments).mock.calls.length).toBe(1);

		const disclosure = page.getByRole('region', { name: '번역 전 데이터 처리 안내' });
		await expect.element(disclosure).toBeInTheDocument();
		await expect.element(disclosure).toHaveTextContent(/PDF 텍스트는 이 브라우저에서 추출/);
		await expect.element(disclosure).toHaveTextContent(/인증된 Sushi 서버/);
		await expect.element(disclosure).toHaveTextContent(/번역 제공자/);
		await expect.element(disclosure).toHaveTextContent(/PDF 파일 자체는 전송하지 않습니다/);

		const checkbox = page.getByRole('checkbox', { name: /텍스트 전송에 동의/ });
		const translateButton = page.getByRole('button', { name: /Translate to Korean/ });
		expect(
			(disclosure.element().compareDocumentPosition(checkbox.element()) &
				Node.DOCUMENT_POSITION_FOLLOWING) !==
				0
		).toBe(true);
		await expect.element(checkbox).not.toBeChecked();
		await expect.element(translateButton).toBeDisabled();
		expect(translateSegments).not.toHaveBeenCalled();

		await checkbox.click();
		await expect.element(translateButton).toBeEnabled();
		expect(translateSegments).not.toHaveBeenCalled();
		await translateButton.click();
		await expect.poll(() => vi.mocked(translateSegments).mock.calls.length).toBe(1);
	});
});
