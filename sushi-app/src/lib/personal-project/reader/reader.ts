import { request } from '$lib/personal-project/shared/api';

export type ReaderSegment = { id: string; text: string };
export type ReaderTranslation = { id: string; text: string };
export type ReaderEntry = { id: string; source: string; translation: string | null };

// Bound provider requests after a real-paper batch failed with HTTP 502.
const MAX_TRANSLATION_SEGMENTS = 2;
const MAX_TRANSLATION_CHARS = 20_000;
const MAX_SEGMENT_CHARS = 5_000;

export function alignTranslations(
	segments: ReaderSegment[],
	translations: ReaderTranslation[]
): ReaderEntry[] {
	const byId = new Map(translations.map(({ id, text }) => [id, text]));
	return segments.map(({ id, text }) => ({
		id,
		source: text,
		translation: byId.get(id) ?? null
	}));
}

export function createSegments(pageTexts: string[], maxLength = 1200): ReaderSegment[] {
	const segments: ReaderSegment[] = [];
	pageTexts.forEach((pageText, pageIndex) => {
		const paragraphs = pageText
			.split(/\n\s*\n/)
			.map((paragraph) => paragraph.replace(/\s+/g, ' ').trim())
			.filter(Boolean);
		let segmentIndex = 0;
		for (const paragraph of paragraphs) {
			let remaining = paragraph;
			while (remaining.length > maxLength) {
				let splitAt = remaining.lastIndexOf(' ', maxLength);
				if (splitAt < maxLength * 0.55) splitAt = maxLength;
				segments.push({
					id: `p${pageIndex + 1}-s${++segmentIndex}`,
					text: remaining.slice(0, splitAt).trim()
				});
				remaining = remaining.slice(splitAt).trim();
			}
			if (remaining) {
				segments.push({ id: `p${pageIndex + 1}-s${++segmentIndex}`, text: remaining });
			}
		}
	});
	return segments;
}

export async function extractPdfSegments(
	file: File,
	onProgress: (current: number, total: number) => void = () => {}
): Promise<ReaderSegment[]> {
	const pdfjs =
		typeof window === 'undefined'
			? await import('pdfjs-dist/legacy/build/pdf.mjs')
			: await import('pdfjs-dist');
	if (typeof window !== 'undefined') {
		pdfjs.GlobalWorkerOptions.workerSrc = new URL(
			'pdfjs-dist/build/pdf.worker.min.mjs',
			import.meta.url
		).href;
	}
	const bytes = new Uint8Array(await file.arrayBuffer());
	const loadingTask = pdfjs.getDocument({ data: bytes });
	const document = await loadingTask.promise;
	const pages: string[] = [];
	try {
		for (let pageNumber = 1; pageNumber <= document.numPages; pageNumber += 1) {
			const page = await document.getPage(pageNumber);
			const content = await page.getTextContent();
			const items = content.items as { str?: unknown }[];
			pages.push(
				items
					.map((item) => (typeof item.str === 'string' ? item.str : ''))
					.filter(Boolean)
					.join(' ')
			);
			onProgress(pageNumber, document.numPages);
		}
	} finally {
		await loadingTask.destroy();
	}
	return createSegments(pages);
}

export async function translateSegments(
	segments: ReaderSegment[],
	onProgress: (completed: number, total: number) => void = () => {},
	path: 'shared' | 'local' = 'shared',
	signal?: AbortSignal
): Promise<ReaderTranslation[]> {
	const contextualSegments: (ReaderSegment & {
		context_before?: string;
		context_after?: string;
	})[] =
		path === 'shared'
			? segments.map((segment, index) => ({
					...segment,
					...(index > 0 ? { context_before: segments[index - 1].text.slice(-500) } : {}),
					...(index + 1 < segments.length
						? { context_after: segments[index + 1].text.slice(0, 500) }
						: {})
				}))
			: segments;
	const batches: (typeof contextualSegments)[] = [];
	let batch: typeof contextualSegments = [];
	let batchChars = 0;
	for (const segment of contextualSegments) {
		const contextChars =
			(segment.context_before?.length ?? 0) + (segment.context_after?.length ?? 0);
		if (segment.text.length > MAX_SEGMENT_CHARS) {
			throw new Error(
				'번역할 한 구간은 최대 5000자까지 허용됩니다. / A translation segment can contain at most 5000 characters.'
			);
		}
		if (
			batch.length >= (path === 'shared' ? 1 : MAX_TRANSLATION_SEGMENTS) ||
			batchChars + segment.text.length + contextChars > MAX_TRANSLATION_CHARS
		) {
			batches.push(batch);
			batch = [];
			batchChars = 0;
		}
		batch.push(segment);
		batchChars += segment.text.length + contextChars;
	}
	if (batch.length) batches.push(batch);

	const translations: ReaderTranslation[] = [];
	for (const currentBatch of batches) {
		signal?.throwIfAborted();
		const previous = translations.at(-1)?.text;
		const requestBatch =
			path === 'shared' && previous
				? [{ ...currentBatch[0], previous_translation: previous.slice(-1000) }]
				: currentBatch;
		const body = { segments: requestBatch, target_language: 'ko' };
		let response: { translations: ReaderTranslation[] };
		if (path === 'local') {
			let result: Response;
			try {
				result = await fetch('http://127.0.0.1:9011/api/personal/reader/translate', {
					method: 'POST',
					signal,
					credentials: 'include',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify(body)
				});
			} catch {
				signal?.throwIfAborted();
				throw new Error(
					'로컬 번역 서버에 연결하지 못했습니다. 서버와 브라우저 출처 설정을 확인해 주세요.'
				);
			}
			if (!result.ok)
				throw new Error(
					`로컬 번역 요청에 실패했습니다 (${result.status}). 같은 로컬 호스트의 로그인과 서버 설정을 확인해 주세요.`
				);
			response = await result.json();
		} else {
			response = await request<{ translations: ReaderTranslation[] }>('/reader/translate', {
				method: 'POST',
				signal,
				body
			});
		}
		signal?.throwIfAborted();
		if (
			!Array.isArray(response?.translations) ||
			response.translations.length !== currentBatch.length ||
			response.translations.some(
				(item, index) =>
					!item ||
					item.id !== currentBatch[index].id ||
					typeof item.text !== 'string' ||
					!item.text.trim()
			)
		) {
			throw new Error('번역 서버 응답 형식이 올바르지 않습니다. / Invalid translation response.');
		}
		translations.push(...response.translations);
		onProgress(translations.length, segments.length);
	}
	return translations;
}
