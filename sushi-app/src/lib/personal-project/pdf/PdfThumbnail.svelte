<script lang="ts">
	import { onMount } from 'svelte';
	import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist';
	import type { PdfPage } from './model';
	import { outlinePath } from './ink-path';
	let { document, page }: { document: PDFDocumentProxy; page: PdfPage } = $props();
	let canvas: HTMLCanvasElement;
	let failed = $state(false);
	onMount(() => {
		let disposed = false,
			task: RenderTask | undefined;
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					observer.disconnect();
					void render();
				}
			},
			{ rootMargin: '120px' }
		);
		observer.observe(canvas);
		async function render() {
			let loadedPage: PDFPageProxy | undefined;
			try {
				const source = await document.getPage((page.source ?? 0) + 1);
				loadedPage = source;
				if (disposed) return;
				const v = source.getViewport({
					scale: 1,
					rotation: page.sourceReady === false ? source.rotate : page.rotation
				});
				const scale = 98 / v.width;
				const viewport = source.getViewport({ scale, rotation: v.rotation });
				canvas.width = Math.ceil(viewport.width);
				canvas.height = Math.ceil(viewport.height);
				const ctx = canvas.getContext('2d')!;
				task = source.render({ canvas, canvasContext: ctx, viewport });
				await task.promise;
				if (disposed) return;
				for (const s of page.strokes) {
					ctx.fillStyle = s.color;
					ctx.strokeStyle = s.color;
					ctx.globalAlpha = s.kind === 'highlight' ? 0.25 : 1;
					if (s.geometry === 'outline') {
						const d = outlinePath(s, (x, y) => viewport.convertToViewportPoint(x, y));
						ctx.fill(new Path2D(d));
					} else {
						ctx.lineWidth = s.width * scale;
						ctx.lineCap = 'round';
						ctx.beginPath();
						s.points.forEach((p, i) => {
							const [x, y] = viewport.convertToViewportPoint(p.x, p.y);
							if (i) ctx.lineTo(x, y);
							else ctx.moveTo(x, y);
						});
						ctx.stroke();
					}
				}
				ctx.globalAlpha = 1;
				for (const n of page.notes) {
					const [x, y] = viewport.convertToViewportPoint(n.x, n.y);
					ctx.fillStyle = n.color;
					ctx.font = `${n.size * scale}px sans-serif`;
					ctx.fillText(n.text, x, y);
				}
			} catch (e) {
				if (!disposed && (e as Error).name !== 'RenderingCancelledException') failed = true;
			} finally {
				loadedPage?.cleanup();
			}
		}
		return () => {
			disposed = true;
			observer.disconnect();
			task?.cancel();
		};
	});
</script>

<canvas bind:this={canvas} aria-label={failed ? '미리보기 없음' : '페이지 미리보기'}></canvas>

<style>
	canvas {
		display: block;
		width: 98px;
		max-width: 100%;
		height: auto;
		min-height: 120px;
		background: white;
	}
</style>
