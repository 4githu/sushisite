<script lang="ts">
	import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
	import type { NotebookPage, NotebookItem } from './types';
	import { onMount } from 'svelte';
	let { document, pageNumber }: { document: PDFDocumentProxy; pageNumber: number } = $props();
	let canvas: HTMLCanvasElement,
		visible = $state(false);
	onMount(() => {
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries.some((e) => e.isIntersecting)) {
					visible = true;
					observer.disconnect();
				}
			},
			{ rootMargin: '180px' }
		);
		observer.observe(canvas);
		return () => observer.disconnect();
	});
	$effect(() => {
		const doc = document,
			n = pageNumber,
			show = visible;
		if (!doc || !show) return;
		let cancelled = false,
			task: RenderTask | undefined;
		(async () => {
			try {
				const page = await doc.getPage(n);
				if (cancelled) return;
				const viewport = page.getViewport({ scale: 100 / page.getViewport({ scale: 1 }).width });
				canvas.width = Math.ceil(viewport.width);
				canvas.height = Math.ceil(viewport.height);
				task = page.render({ canvas, viewport });
				await task.promise;
			} catch {}
		})();
		return () => {
			cancelled = true;
			task?.cancel();
		};
	});
</script>

<canvas bind:this={canvas} aria-hidden="true" style="width:100%;height:100%;display:block"></canvas>
