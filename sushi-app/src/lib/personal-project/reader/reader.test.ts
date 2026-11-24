import { describe, expect, it, vi } from 'vitest';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { alignTranslations, createSegments, extractPdfSegments, translateSegments } from './reader';

describe('createSegments', () => {
	it('keeps page order and skips blank pages while assigning stable page-based ids', () => {
		expect(createSegments([' First page. ', '', 'Second page.'])).toEqual([
			{ id: 'p1-s1', text: 'First page.' },
			{ id: 'p3-s1', text: 'Second page.' }
		]);
	});

	it('splits long paragraphs into bounded, readable chunks', () => {
		const segments = createSegments(['abcdefghij'], 4);
		expect(segments.map(({ text }) => text)).toEqual(['abcd', 'efgh', 'ij']);
		expect(segments.map(({ id }) => id)).toEqual(['p1-s1', 'p1-s2', 'p1-s3']);
	});
});

describe('alignTranslations', () => {
	it('keeps source order and maps translations by segment id', () => {
		expect(
			alignTranslations(
				[
					{ id: 'p1-s1', text: 'First source.' },
					{ id: 'p2-s1', text: 'Second source.' }
				],
				[
					{ id: 'p2-s1', text: '두 번째 번역.' },
					{ id: 'p1-s1', text: '첫 번째 번역.' }
				]
			)
		).toEqual([
			{ id: 'p1-s1', source: 'First source.', translation: '첫 번째 번역.' },
			{ id: 'p2-s1', source: 'Second source.', translation: '두 번째 번역.' }
		]);
	});

	it('does not invent a translation for a missing response segment', () => {
		expect(alignTranslations([{ id: 'p1-s1', text: 'Source.' }], [])).toEqual([
			{ id: 'p1-s1', source: 'Source.', translation: null }
		]);
	});
});

describe('extractPdfSegments', () => {
	it('extracts text locally and reports page progress', async () => {
		const pdf = await PDFDocument.create();
		const font = await pdf.embedFont(StandardFonts.Helvetica);
		pdf.addPage().drawText('Locally extracted research text.', { font });
		const bytes = await pdf.save();
		const file = new File([new Uint8Array(bytes).buffer as ArrayBuffer], 'research.pdf', {
			type: 'application/pdf'
		});
		const progress: [number, number][] = [];
		expect(
			await extractPdfSegments(file, (current, total) => progress.push([current, total]))
		).toEqual([{ id: 'p1-s1', text: 'Locally extracted research text.' }]);
		expect(progress).toEqual([[1, 1]]);
	});
});

describe('translateSegments', () => {
	it('keeps supplementary characters intact at each context truncation boundary', async () => {
		const sent: Array<{
			id: string;
			text: string;
			context_before?: string;
			context_after?: string;
			previous_translation?: string;
		}> = [];
		const previous = '😀' + 'x'.repeat(999);
		vi.stubGlobal('fetch', async (_input: RequestInfo | URL, init?: RequestInit) => {
			const body = JSON.parse(String(init?.body));
			sent.push(...body.segments);
			return new Response(
				JSON.stringify({ translations: [{ id: body.segments[0].id, text: previous }] }),
				{ status: 200 }
			);
		});
		try {
			const source = [
				{ id: 'a', text: '😀' + 'x'.repeat(499) },
				{ id: 'b', text: 'middle' },
				{ id: 'c', text: 'x'.repeat(499) + '😀' }
			];
			const original = structuredClone(source);
			await translateSegments(source);
			expect(source).toEqual(original);
			expect(sent[1].context_before).toBe('x'.repeat(499));
			expect(sent[1].context_after).toBe('x'.repeat(499));
			expect(sent[1].previous_translation).toBe('x'.repeat(999));
			expect(sent.map(({ id, text }) => ({ id, text }))).toEqual(original);
		} finally {
			vi.unstubAllGlobals();
		}
	});
	it('sends the verified previous result sequentially and rejects a mismatched id', async () => {
		const sent: Array<{ id: string; previous_translation?: string }> = [];
		vi.stubGlobal('fetch', async (_input: RequestInfo | URL, init?: RequestInit) => {
			const body = JSON.parse(String(init?.body));
			sent.push(...body.segments);
			return new Response(
				JSON.stringify({
					translations: [{ id: body.segments[0].id, text: `ko-${body.segments[0].id}` }]
				}),
				{ status: 200 }
			);
		});
		try {
			await translateSegments([
				{ id: 'a', text: 'first' },
				{ id: 'b', text: 'second' }
			]);
			expect(sent).toHaveLength(2);
			expect(sent[1]).toMatchObject({ id: 'b', previous_translation: 'ko-a' });
		} finally {
			vi.unstubAllGlobals();
		}
		vi.stubGlobal(
			'fetch',
			async () =>
				new Response(JSON.stringify({ translations: [{ id: 'wrong', text: 'x' }] }), {
					status: 200
				})
		);
		try {
			await expect(translateSegments([{ id: 'a', text: 'first' }])).rejects.toThrow();
		} finally {
			vi.unstubAllGlobals();
		}
	});
	it('includes adjacent context across request boundaries without changing ids or source', async () => {
		const sent: { id: string; text: string; context_before?: string; context_after?: string }[] =
			[];
		vi.stubGlobal('fetch', async (_input: RequestInfo | URL, init?: RequestInit) => {
			const body = JSON.parse(String(init?.body));
			sent.push(...body.segments);
			return new Response(
				JSON.stringify({
					translations: body.segments.map(({ id }: { id: string }) => ({ id, text: '번역' }))
				}),
				{ status: 200 }
			);
		});
		try {
			const source = [
				{ id: 'p9-s2', text: 'Earlier.' },
				{ id: 'p9-s3', text: 'ROS scav -' },
				{ id: 'p9-s4', text: 'enging by NAC.' }
			];
			const original = structuredClone(source);
			await translateSegments(source);
			expect(source).toEqual(original);
			expect(sent[2]).toMatchObject({
				id: 'p9-s4',
				text: 'enging by NAC.',
				context_before: 'ROS scav -'
			});
			expect(sent[1]).toMatchObject({ id: 'p9-s3', context_after: 'enging by NAC.' });
		} finally {
			vi.unstubAllGlobals();
		}
	});
	it('stops before the next batch when the first request is cancelled', async () => {
		const controller = new AbortController();
		const fetchMock = vi.fn(async () => {
			controller.abort();
			return new Response(JSON.stringify({ translations: [] }), { status: 200 });
		});
		vi.stubGlobal('fetch', fetchMock);
		try {
			const segments = Array.from({ length: 51 }, (_, i) => ({ id: `${i}`, text: 'x' }));
			await expect(
				translateSegments(segments, () => {}, 'shared', controller.signal)
			).rejects.toMatchObject({ name: 'AbortError' });
			expect(fetchMock).toHaveBeenCalledTimes(1);
		} finally {
			vi.unstubAllGlobals();
		}
	});
	it('sends only explicitly selected local translations to the loopback bridge', async () => {
		const fetchMock = vi.fn(
			async () =>
				new Response(JSON.stringify({ translations: [{ id: 'p1-s1', text: '번역' }] }), {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		vi.stubGlobal('fetch', fetchMock);
		try {
			await translateSegments([{ id: 'p1-s1', text: 'synthetic' }], () => {}, 'local');
			expect(fetchMock).toHaveBeenCalledWith(
				'http://127.0.0.1:9011/api/personal/reader/translate',
				expect.objectContaining({ method: 'POST', credentials: 'include' })
			);
		} finally {
			vi.unstubAllGlobals();
		}
	});
	it('keeps requests within the backend segment limit and preserves source order', async () => {
		const seenBatches: Array<Array<{ id: string; text: string }>> = [];
		vi.stubGlobal('fetch', async (_input: RequestInfo | URL, init?: RequestInit) => {
			const body = JSON.parse(String(init?.body));
			seenBatches.push(body.segments);
			return new Response(
				JSON.stringify({
					translations: body.segments.map(({ id }: { id: string }) => ({ id, text: `ko-${id}` }))
				}),
				{ status: 200, headers: { 'Content-Type': 'application/json' } }
			);
		});
		try {
			const segments = Array.from({ length: 51 }, (_, index) => ({
				id: `p1-s${index + 1}`,
				text: `source-${index + 1}`
			}));
			const result = await translateSegments(segments);
			expect(seenBatches.map((batch) => batch.length)).toEqual(Array(51).fill(1));
			expect(result.map(({ id }) => id)).toEqual(segments.map(({ id }) => id));
		} finally {
			vi.unstubAllGlobals();
		}
	});

	it('keeps each translation batch within the backend character limit', async () => {
		const seenBatches: Array<Array<{ id: string; text: string }>> = [];
		vi.stubGlobal('fetch', async (_input: RequestInfo | URL, init?: RequestInit) => {
			const body = JSON.parse(String(init?.body));
			seenBatches.push(body.segments);
			return new Response(
				JSON.stringify({
					translations: body.segments.map(({ id }: { id: string }) => ({ id, text: `ko-${id}` }))
				}),
				{ status: 200, headers: { 'Content-Type': 'application/json' } }
			);
		});
		try {
			const segments = Array.from({ length: 5 }, (_, index) => ({
				id: `p1-s${index + 1}`,
				text: 'x'.repeat(5_000)
			}));
			await translateSegments(segments);
			expect(
				seenBatches.map((batch) => batch.reduce((total, item) => total + item.text.length, 0))
			).toEqual(Array(5).fill(5_000));
		} finally {
			vi.unstubAllGlobals();
		}
	});

	it('posts the reader contract and returns backend translations', async () => {
		const fetchMock = vi.fn(
			async () =>
				new Response(JSON.stringify({ translations: [{ id: 'p1-s1', text: '번역문' }] }), {
					status: 200,
					headers: { 'Content-Type': 'application/json' }
				})
		);
		vi.stubGlobal('fetch', fetchMock);
		try {
			const segments = [{ id: 'p1-s1', text: 'Source text.' }];
			expect(await translateSegments(segments)).toEqual([{ id: 'p1-s1', text: '번역문' }]);
			expect(fetchMock).toHaveBeenCalledWith(
				'/api/personal/reader/translate',
				expect.objectContaining({
					method: 'POST',
					body: JSON.stringify({ segments, target_language: 'ko' })
				})
			);
		} finally {
			vi.unstubAllGlobals();
		}
	});

	it('surfaces an unconfigured translation backend error without inventing text', async () => {
		vi.stubGlobal(
			'fetch',
			async () =>
				new Response(
					JSON.stringify({ detail: { message: 'translation service not configured' } }),
					{
						status: 503,
						headers: { 'Content-Type': 'application/json' }
					}
				)
		);
		try {
			await expect(translateSegments([{ id: 'p1-s1', text: 'Source text.' }])).rejects.toThrow(
				'translation service not configured'
			);
		} finally {
			vi.unstubAllGlobals();
		}
	});
});
