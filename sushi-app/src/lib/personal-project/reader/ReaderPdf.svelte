<script lang="ts">
	import { onMount } from 'svelte';
	import 'pdfjs-dist/web/pdf_viewer.css';
	import type { PDFDocumentProxy, PDFDocumentLoadingTask, RenderTask, TextLayer } from 'pdfjs-dist';
	import { request } from '$lib/personal-project/shared/api';
	import { relativeRect, type ReaderAnnotation, type ReaderRect } from './annotations';
	let {
		url,
		annotations = [],
		onchange = () => {},
		onnote = () => {}
	}: {
		url: string;
		annotations?: ReaderAnnotation[];
		onchange?: (value: ReaderAnnotation[]) => void;
		onnote?: (value: string) => void;
	} = $props();
	let documentPdf = $state.raw<PDFDocumentProxy>();
	let pageNumber = $state(1),
		zoom = $state(1),
		error = $state(''),
		ready = $state(false);
	let canvas: HTMLCanvasElement, textContainer: HTMLDivElement, sheet: HTMLDivElement;
	let textLayer: TextLayer | undefined, renderTask: RenderTask | undefined;
	let sequence = 0;
	let selected = $state<{ rects: ReaderRect[]; text: string } | null>(null);
	let regionMode = $state(false),
		start: { x: number; y: number } | null = null;
	let left = $state(10),
		top = $state(10),
		width = $state(30),
		height = $state(20);
	function selectByCoordinates() {
		if (!ready) return;
		const values = [left, top, width, height].map(Number);
		if (
			values.some((v) => !Number.isFinite(v)) ||
			values[0] < 0 ||
			values[1] < 0 ||
			values[2] <= 0 ||
			values[3] <= 0 ||
			values[0] + values[2] > 100 ||
			values[1] + values[3] > 100
		) {
			error = '영역 좌표는 페이지 안의 0–100% 범위여야 합니다.';
			return;
		}
		error = '';
		selected = {
			rects: [
				{ x: values[0] / 100, y: values[1] / 100, width: values[2] / 100, height: values[3] / 100 }
			],
			text: ''
		};
	}
	let caption = $state(''),
		context = $state(''),
		explanation = $state(''),
		explaining = $state(false);
	let controller: AbortController | undefined;
	onMount(() => {
		let disposed = false;
		let loading: PDFDocumentLoadingTask | undefined;
		void (async () => {
			try {
				const pdfjs = await import('pdfjs-dist');
				pdfjs.GlobalWorkerOptions.workerSrc = new URL(
					'pdfjs-dist/build/pdf.worker.min.mjs',
					import.meta.url
				).href;
				if (disposed) return;
				loading = pdfjs.getDocument({ url });
				const pdf = await loading.promise;
				if (!disposed) documentPdf = pdf;
			} catch {
				if (!disposed) error = 'PDF 지면을 불러오지 못했습니다.';
			}
		})();
		return () => {
			disposed = true;
			sequence++;
			controller?.abort();
			renderTask?.cancel();
			textLayer?.cancel();
			void loading?.destroy();
		};
	});
	$effect(() => {
		const pdf = documentPdf,
			page = pageNumber,
			scale = zoom;
		if (!pdf || !canvas) return;
		const version = ++sequence;
		ready = false;
		renderTask?.cancel();
		textLayer?.cancel();
		void (async () => {
			try {
				const pdfPage = await pdf.getPage(page);
				if (version !== sequence) return;
				const viewport = pdfPage.getViewport({ scale });
				canvas.width = Math.ceil(viewport.width);
				canvas.height = Math.ceil(viewport.height);
				const ctx = canvas.getContext('2d');
				if (!ctx) throw new Error('Canvas unavailable');
				renderTask = pdfPage.render({ canvasContext: ctx, canvas, viewport });
				await renderTask.promise;
				if (version !== sequence) return;
				const { TextLayer } = await import('pdfjs-dist');
				if (version !== sequence) return;
				// PDF.js owns the children of this otherwise empty text-layer container.
				// eslint-disable-next-line svelte/no-dom-manipulating
				textContainer.replaceChildren();
				textContainer.style.setProperty('--scale-factor', String(scale));
				textContainer.style.setProperty('--total-scale-factor', String(viewport.scale));
				textLayer = new TextLayer({
					textContentSource: pdfPage.streamTextContent(),
					container: textContainer,
					viewport
				});
				await textLayer.render();
				if (version === sequence) {
					error = '';
					ready = true;
				}
			} catch {
				if (version === sequence) error = 'PDF 지면을 표시하지 못했습니다.';
			}
		})();
		return () => {
			sequence++;
			renderTask?.cancel();
			textLayer?.cancel();
		};
	});
	function captureSelection() {
		if (!ready) return;
		const selection = window.getSelection();
		if (
			!selection ||
			selection.isCollapsed ||
			!textContainer.contains(selection.anchorNode) ||
			!textContainer.contains(selection.focusNode)
		)
			return;
		const rects = Array.from(selection.getRangeAt(0).getClientRects())
			.map((r) => relativeRect(r, sheet.getBoundingClientRect()))
			.filter((r) => r.width > 0 && r.height > 0);
		if (rects.length) selected = { rects, text: selection.toString() };
	}
	function addAnnotation(kind: ReaderAnnotation['kind']) {
		if (!ready || !selected) return;
		onchange([
			...annotations,
			{
				id: crypto.randomUUID(),
				page: pageNumber,
				kind,
				rects: selected.rects,
				text: selected.text
			}
		]);
		selected = null;
		window.getSelection()?.removeAllRanges();
	}
	function point(event: PointerEvent) {
		const box = sheet.getBoundingClientRect();
		return {
			x: Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)),
			y: Math.min(1, Math.max(0, (event.clientY - box.top) / box.height))
		};
	}
	function begin(event: PointerEvent) {
		if (!ready || !regionMode) return;
		event.preventDefault();
		start = point(event);
		sheet.setPointerCapture(event.pointerId);
	}
	function end(event: PointerEvent) {
		if (!ready || !start || !regionMode) return;
		const last = point(event);
		const rect = {
			x: Math.min(start.x, last.x),
			y: Math.min(start.y, last.y),
			width: Math.abs(last.x - start.x),
			height: Math.abs(last.y - start.y)
		};
		start = null;
		if (rect.width > 0.005 && rect.height > 0.005) selected = { rects: [rect], text: '' };
		regionMode = false;
	}
	async function explain() {
		if (!ready || !selected || selected.rects.length !== 1 || explaining) return;
		const r = selected.rects[0],
			cropped = document.createElement('canvas');
		cropped.width = Math.max(1, Math.round(r.width * canvas.width));
		cropped.height = Math.max(1, Math.round(r.height * canvas.height));
		cropped
			.getContext('2d')
			?.drawImage(
				canvas,
				r.x * canvas.width,
				r.y * canvas.height,
				r.width * canvas.width,
				r.height * canvas.height,
				0,
				0,
				cropped.width,
				cropped.height
			);
		const data = cropped.toDataURL('image/jpeg', 0.8).split(',')[1];
		if (data.length > 1048576) {
			error = '선택 영역이 너무 큽니다. 축소 후 다시 선택하세요.';
			return;
		}
		controller?.abort();
		controller = new AbortController();
		explaining = true;
		error = '';
		explanation = '';
		try {
			const result = await request<{ explanation: string }>('/reader/explain-image', {
				method: 'POST',
				signal: controller.signal,
				body: {
					image: { mime_type: 'image/jpeg', base64: data },
					caption,
					context,
					target_language: 'Korean'
				}
			});
			if (typeof result.explanation !== 'string') throw new Error('응답 형식이 올바르지 않습니다.');
			explanation = result.explanation;
		} catch (cause) {
			if (!controller.signal.aborted)
				error = cause instanceof Error ? cause.message : '이미지 설명 요청에 실패했습니다.';
		} finally {
			explaining = false;
		}
	}
	function changePage(value: number) {
		const next = Math.max(
			1,
			Math.min(documentPdf?.numPages || 1, Number.isFinite(value) ? Math.trunc(value) : 1)
		);
		if (next === pageNumber) return;
		ready = false;
		regionMode = false;
		start = null;
		selected = null;
		explanation = '';
		controller?.abort();
		pageNumber = next;
	}
</script>

<section aria-label="원본 PDF 지면" title="원본 PDF 지면" class="pdf-viewer" aria-busy={!ready}>
	<div class="controls">
		<button
			type="button"
			aria-label="이전 페이지"
			disabled={pageNumber <= 1}
			onclick={() => changePage(pageNumber - 1)}>이전</button
		>
		<label
			>페이지 <input
				aria-label="PDF 페이지"
				type="number"
				min="1"
				max={documentPdf?.numPages || 1}
				value={pageNumber}
				onchange={(event) => changePage(Number(event.currentTarget.value))}
			/></label
		><span>/ {documentPdf?.numPages || '…'}</span>
		<button
			type="button"
			aria-label="다음 페이지"
			disabled={!documentPdf || pageNumber >= documentPdf.numPages}
			onclick={() => changePage(pageNumber + 1)}>다음</button
		>
		<button type="button" aria-label="축소" disabled={zoom <= 0.5} onclick={() => (zoom -= 0.25)}
			>−</button
		><span>{Math.round(zoom * 100)}%</span><button
			type="button"
			aria-label="확대"
			disabled={zoom >= 2}
			onclick={() => (zoom += 0.25)}>+</button
		>
		<button type="button" disabled={!ready} onclick={captureSelection}>텍스트 선택 확인</button
		><button
			type="button"
			disabled={!ready || !selected?.text}
			onclick={() => addAnnotation('highlight')}>선택 하이라이트 저장</button
		>
		<button
			type="button"
			aria-pressed={regionMode}
			disabled={!ready}
			onclick={() => {
				regionMode = !regionMode;
				selected = null;
			}}>영역 선택</button
		><button
			type="button"
			disabled={!ready || !selected || !!selected.text}
			onclick={() => addAnnotation('region')}>영역 주석 저장</button
		>
	</div>
	<details>
		<summary>키보드로 영역 선택</summary>
		<div class="controls">
			<label>왼쪽 % <input type="number" min="0" max="100" bind:value={left} /></label><label
				>위 % <input type="number" min="0" max="100" bind:value={top} /></label
			><label>너비 % <input type="number" min="1" max="100" bind:value={width} /></label><label
				>높이 % <input type="number" min="1" max="100" bind:value={height} /></label
			><button type="button" disabled={!ready} onclick={selectByCoordinates}>좌표 영역 선택</button>
		</div>
	</details>
	{#if error}<p role="alert">{error}</p>{/if}
	<div class="page">
		<div
			class="sheet"
			bind:this={sheet}
			onpointerdown={begin}
			onpointerup={end}
			onpointercancel={() => (start = null)}
			role="presentation"
		>
			<canvas bind:this={canvas}></canvas>
			<div
				class="textLayer"
				bind:this={textContainer}
				onmouseup={captureSelection}
				onkeyup={captureSelection}
				role="presentation"
			></div>
			<div class="marks" aria-hidden="true">
				{#each annotations.filter((a) => a.page === pageNumber) as annotation (annotation.id)}{#each annotation.rects as r, i (i)}<div
							class:region={annotation.kind === 'region'}
							style={`left:${r.x * 100}%;top:${r.y * 100}%;width:${r.width * 100}%;height:${r.height * 100}%`}
						></div>{/each}{/each}{#if selected}{#each selected.rects as r, i (i)}<div
							class="selected"
							style={`left:${r.x * 100}%;top:${r.y * 100}%;width:${r.width * 100}%;height:${r.height * 100}%`}
						></div>{/each}{/if}
			</div>
			{#if regionMode}<div class="region-overlay" aria-hidden="true"></div>{/if}
		</div>
	</div>
	{#if selected && !selected.text}<div class="controls">
			<label>캡션 <input bind:value={caption} maxlength="2000" /></label><label
				>문맥 <input bind:value={context} maxlength="6000" /></label
			><button type="button" disabled={explaining} onclick={explain}>선택 이미지 설명 요청</button
			><small>선택한 이미지와 캡션·문맥이 인증된 서버와 설정된 제공자로 전송됩니다.</small>
		</div>{/if}
	{#if explanation}<p>{explanation}</p>
		<button
			type="button"
			onclick={() =>
				onnote(
					`${pageNumber}쪽 그림${caption.trim() ? ` · ${caption.trim()}` : ''}\n${explanation}`
				)}>설명을 메모에 넣기</button
		>{/if}
	{#if annotations.some((a) => a.page === pageNumber)}<ul>
			{#each annotations.filter((a) => a.page === pageNumber) as annotation (annotation.id)}<li>
					{annotation.kind === 'highlight' ? '하이라이트' : '영역'}
					{annotation.text}<button
						type="button"
						onclick={() => onchange(annotations.filter((a) => a.id !== annotation.id))}>삭제</button
					>
				</li>{/each}
		</ul>{/if}
</section>

<style>
	.pdf-viewer {
		border-top: 1px solid #dfe5e3;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding: 0.75rem;
	}
	.controls input[type='number'] {
		width: 4rem;
	}
	.controls button {
		padding: 0.4rem 0.6rem;
		min-height: 44px;
	}
	.page {
		overflow: auto;
		max-height: 75vh;
		background: #eef1ef;
		padding: 1rem;
	}
	.sheet {
		position: relative;
		width: max-content;
		margin: auto;
	}
	canvas {
		display: block;
		background: white;
	}
	.marks {
		position: absolute;
		inset: 0;
		pointer-events: none;
	}
	.marks div {
		position: absolute;
		background: #ffe10055;
	}
	.marks div.region {
		background: #35a0ff22;
		border: 2px solid #1374cf;
		box-sizing: border-box;
	}
	.marks div.selected {
		background: #35a0ff44;
	}
	.region-overlay {
		position: absolute;
		inset: 0;
		cursor: crosshair;
		touch-action: none;
	}
</style>
