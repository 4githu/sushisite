<script lang="ts">
	import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
	import { paperFor, paperColors } from './paper';
	import type { NotebookPage, NotebookItem } from './types';
	import { onMount } from 'svelte';
	import { centerline } from './ink-render';
	import { getStroke } from 'perfect-freehand';
	let {
		pdf,
		page,
		zoom,
		index,
		onactivate
	}: {
		pdf: PDFDocumentProxy | null;
		page: NotebookPage;
		zoom: number;
		index: number;
		onactivate: (i: number, e?: PointerEvent) => void;
	} = $props();
	let el: HTMLDivElement,
		canvas: HTMLCanvasElement,
		visible = $state(false),
		task: RenderTask | undefined,
		token = 0;
	const path = (o: NotebookItem) => {
		const pts = getStroke(
			o.points.map((p: { x: number; y: number; p?: number }) => [p.x, p.y, p.p ?? 0.5]),
			{
				size: o.width,
				thinning: o.highlight ? 0 : 0.45,
				streamline: 0.08,
				last: true,
				simulatePressure: false
			}
		);
		return pts.length ? 'M' + pts.map((p) => p.join(',')).join('L') + 'Z' : '';
	};
	onMount(() => {
		const obs = new IntersectionObserver(
			(es) => {
				visible = es[0].isIntersecting;
			},
			{ rootMargin: '250px' }
		);
		obs.observe(el);
		return () => {
			obs.disconnect();
			task?.cancel();
		};
	});
	$effect(() => {
		const doc = pdf,
			p = page,
			v = visible,
			z = zoom;
		const t = ++token;
		task?.cancel();
		if (!v) {
			canvas.width = 1;
			canvas.height = 1;
			return;
		}
		if (!doc || p.source === null) return;
		(async () => {
			try {
				const pg = await doc.getPage((p.source ?? index) + 1);
				if (t !== token) return;
				const vp = pg.getViewport({
					scale: Math.min(1.5, z * devicePixelRatio),
					rotation: p.rotation ?? pg.rotate
				});
				canvas.width = Math.ceil(vp.width);
				canvas.height = Math.ceil(vp.height);
				task = pg.render({ canvas, viewport: vp });
				await task.promise;
			} catch {}
		})();
	});
</script>

<div
	bind:this={el}
	class="passive-page"
	style:--paper-background={paperColors[paperFor(page).color]}
	style:--paper-foreground={paperFor(page).color === 'black' ? '#eeeeee' : '#242529'}
	style:width={page.w * zoom + 'px'}
	style:height={page.h * zoom + 'px'}
	role="button"
	tabindex="0"
	aria-label={index + 1 + ' 페이지에서 필기'}
	onpointerdown={(e) => onactivate(index, e)}
	onkeydown={(e) => {
		if (e.key === 'Enter') onactivate(index);
	}}
>
	<canvas bind:this={canvas}></canvas>
	{#if (!pdf || page.source === null) && paperFor(page).pattern === 'ruled'}<svg
			viewBox={'0 0 ' + page.w + ' ' + page.h}
			aria-hidden="true"
			>{#each Array.from({ length: Math.max(0, Math.floor((page.h - 117) / 32)) }, (_, i) => 75 + i * 32) as y (y)}<line
					x1="42"
					x2={page.w - 42}
					y1={y}
					y2={y}
					stroke={paperFor(page).color === 'black' ? '#ffffff26' : '#e9ebef'}
					stroke-width="1"
				/>{/each}</svg
		>{/if}
	<svg class="passive-ink" viewBox={'0 0 ' + page.w + ' ' + page.h} aria-hidden="true"
		>{#each page.items.filter((o) => o.kind === 'stroke') as o (o.id)}<path
				d={o.uniform ? centerline(o.points) : path(o)}
				stroke={o.uniform ? o.color : undefined}
				stroke-width={o.width}
				stroke-linecap="round"
				stroke-linejoin="round"
				fill={o.uniform ? 'none' : o.color}
				opacity={o.highlight ? 0.3 : 1}
			/>{/each}</svg
	>
	{#each page.items.filter((o) => o.kind !== 'stroke') as o (o.id)}<div
			class="passive-object"
			class:passive-image={o.kind === 'image'}
			style:left={(o.x / page.w) * 100 + '%'}
			style:top={(o.y / page.h) * 100 + '%'}
			style:width={(o.w / page.w) * 100 + '%'}
			style:font-size={16 * zoom * (o.textScale || 1) + 'px'}
		>
			{#if o.kind === 'image'}<img src={o.src} alt="" />{:else if o.kind === 'text'}{o.html
					.replace(/<[^>]*>/g, ' ')
					.replace(/&nbsp;/g, ' ')}{:else}▤{/if}
		</div>{/each}
</div>
