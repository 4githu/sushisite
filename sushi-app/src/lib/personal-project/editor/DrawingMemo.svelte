<script lang="ts">
	import { untrack } from 'svelte';
	import { erase, type Stroke, type InkPoint } from '../pdf/model';
	let {
		initial = [],
		onsave,
		oncancel
	}: {
		initial?: Stroke[];
		onsave: (file: File, strokes: Stroke[]) => Promise<void>;
		oncancel: () => void;
	} = $props();
	let strokes = $state<Stroke[]>(structuredClone(untrack(() => $state.snapshot(initial)))),
		color = $state('#25262b'),
		tool = $state('pen'),
		width = $state(3),
		busy = $state(false),
		error = $state('');
	let undo = $state<Stroke[][]>([]),
		active: number | null = null,
		stroke: Stroke | null = null;
	const point = (e: PointerEvent): InkPoint => {
		const r = (e.currentTarget as SVGElement).getBoundingClientRect();
		return {
			x: ((e.clientX - r.left) * 720) / r.width,
			y: ((e.clientY - r.top) * 420) / r.height,
			pressure: e.pressure || 0.5
		};
	};
	function down(e: PointerEvent) {
		if (active !== null || e.pointerType === 'touch') return;
		e.preventDefault();
		active = e.pointerId;
		(e.currentTarget as SVGElement).setPointerCapture(e.pointerId);
		undo = [...undo.slice(-29), structuredClone($state.snapshot(strokes))];
		const p = point(e);
		if (tool === 'erase' || e.button === 5) {
			strokes = erase(strokes, p, 12);
			stroke = null;
		} else {
			stroke = {
				id: crypto.randomUUID(),
				kind: tool === 'highlight' ? 'highlight' : 'pen',
				color,
				width,
				points: [p, { ...p, x: p.x + 0.01 }]
			};
			strokes = [...strokes, stroke];
		}
	}
	function move(e: PointerEvent) {
		if (active !== e.pointerId) return;
		const p = point(e);
		if (!stroke) strokes = erase(strokes, p, 12);
		else {
			stroke = { ...stroke, points: [...stroke.points, p] };
			strokes = strokes.map((s) => (s.id === stroke!.id ? stroke! : s));
		}
	}
	function end(e: PointerEvent) {
		if (active === e.pointerId) {
			active = null;
			stroke = null;
		}
	}
	async function save() {
		busy = true;
		error = '';
		try {
			const c = document.createElement('canvas');
			c.width = 1440;
			c.height = 840;
			const ctx = c.getContext('2d')!;
			ctx.scale(2, 2);
			ctx.fillStyle = '#fff';
			ctx.fillRect(0, 0, 720, 420);
			for (const s of strokes) {
				ctx.beginPath();
				ctx.strokeStyle = s.color;
				ctx.lineWidth = s.width;
				ctx.lineCap = 'round';
				ctx.lineJoin = 'round';
				ctx.globalAlpha = s.kind === 'highlight' ? 0.3 : 1;
				s.points.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
				ctx.stroke();
			}
			const blob = await new Promise<Blob>((resolve, reject) =>
				c.toBlob((b) => (b ? resolve(b) : reject(Error('이미지 생성 실패'))), 'image/png')
			);
			await onsave(
				new File([blob], '그림 메모.png', { type: 'image/png' }),
				$state.snapshot(strokes)
			);
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
</script>

<div class="drawing-backdrop">
	<div class="drawing-dialog" role="dialog" aria-modal="true" aria-label="그림 메모" tabindex="-1">
		<header>
			<h2>그림 메모</h2>
			<button disabled={busy} onclick={oncancel}>닫기</button>
		</header>
		<div class="drawing-tools">
			<select aria-label="그림 메모 도구" bind:value={tool}
				><option value="pen">펜</option><option value="highlight">형광펜</option><option
					value="erase">획 지우개</option
				></select
			><input type="color" aria-label="그림 메모 색" bind:value={color} /><input
				type="range"
				aria-label="그림 메모 굵기"
				min="1"
				max="12"
				bind:value={width}
			/><button
				disabled={!undo.length || busy}
				onclick={() => {
					strokes = undo.at(-1)!;
					undo = undo.slice(0, -1);
				}}>실행 취소</button
			>
		</div>
		<svg
			viewBox="0 0 720 420"
			role="img"
			aria-label="그림 메모 필기 영역"
			onpointerdown={down}
			onpointermove={move}
			onpointerup={end}
			onpointercancel={end}
			onlostpointercapture={end}
			oncontextmenu={(e) => e.preventDefault()}
			>{#each strokes as s}<path
					d={s.points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ')}
					fill="none"
					stroke={s.color}
					stroke-width={s.width}
					stroke-linecap="round"
					stroke-linejoin="round"
					opacity={s.kind === 'highlight' ? 0.3 : 1}
				/>{/each}</svg
		>
		<footer>
			<small
				>펜 또는 마우스로 그리세요. 첨부 후 다시 선택해 이동·크기 변경·수정할 수 있습니다.</small
			><button disabled={busy || !strokes.length} onclick={save}
				>{busy ? '첨부 중…' : '그림 첨부'}</button
			>
		</footer>
		{#if error}<p role="alert">{error}</p>{/if}
	</div>
</div>

<style>
	.drawing-backdrop {
		position: fixed;
		inset: 0;
		background: #0006;
		z-index: 1100;
		display: grid;
		place-items: center;
		padding: 16px;
	}
	.drawing-dialog {
		background: white;
		color: #25262b;
		border-radius: 12px;
		padding: 18px;
		width: min(780px, 100%);
		max-height: 90dvh;
		overflow: auto;
		box-shadow: 0 12px 50px #0003;
	}
	header,
	footer,
	.drawing-tools {
		display: flex;
		align-items: center;
		gap: 12px;
		justify-content: space-between;
		flex-wrap: wrap;
	}
	h2 {
		font-size: 18px;
		margin: 0;
	}
	svg {
		width: 100%;
		display: block;
		background: #fff;
		border: 1px solid #ccc;
		border-radius: 4px;
		margin: 12px 0;
		touch-action: none;
		user-select: none;
	}
	button,
	select {
		padding: 6px 10px;
		border: 1px solid #ccc;
		border-radius: 5px;
		background: white;
		color: inherit;
	}
	.drawing-tools {
		justify-content: flex-start;
		margin-top: 12px;
	}
	input[type='color'] {
		width: 32px;
		height: 30px;
	}
	small {
		max-width: 75%;
		font-size: 12px;
	}
</style>
