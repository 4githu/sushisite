<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { request, PersonalApiError } from '../shared/api';
	import { privateCacheUser } from '../shared/auth';
	import {
		erase,
		exportPdf,
		type PdfNotebook,
		type PdfPage,
		type InkPoint,
		type Stroke
	} from './model';
	let { resourceId, url, name }: { resourceId: string; url: string; name: string } = $props();
	let notebook = $state<PdfNotebook>({ version: 1, pages: [] }),
		selected = $state(0),
		zoom = $state(1),
		tool = $state<'pen' | 'highlight' | 'erase' | 'text' | 'pan'>('pen'),
		color = $state('#25262b'),
		width = $state(3),
		penOnly = $state(true),
		toolbar = $state(true),
		loading = $state(true),
		saving = $state(false),
		error = $state(''),
		notice = $state(''),
		dirty = $state(false),
		conflict = $state(false),
		revision = 0;
	let loadingTasks: import('pdfjs-dist').PDFDocumentLoadingTask[] = [];
	let blank: import('pdfjs-dist').PDFDocumentProxy;
	let pdf: import('pdfjs-dist').PDFDocumentProxy,
		original: Uint8Array,
		canvas: HTMLCanvasElement,
		viewport = $state.raw<import('pdfjs-dist').PageViewport>();
	let viewWidth = $state(600),
		viewHeight = $state(800);
	let undo = $state<string[]>([]),
		redo = $state<string[]>([]);
	let active = $state<number | null>(null),
		activeStroke: Stroke | null = null,
		renderVersion = 0,
		disposed = false;
	let renderTask: import('pdfjs-dist').RenderTask | undefined;
	const current = $derived(notebook.pages[selected]);
	const recoveryKey = () => `ondo-private:${privateCacheUser()}:pdf:${resourceId}`;
	const docKey = () => `pdf:${resourceId}`;
	function checkpoint() {
		undo = [...undo.slice(-39), JSON.stringify($state.snapshot(notebook))];
		redo = [];
	}
	function change() {
		dirty = true;
		try {
			if (privateCacheUser())
				localStorage.setItem(
					recoveryKey(),
					JSON.stringify({ data: $state.snapshot(notebook), revision })
				);
		} catch {
			notice = '기기 복구 공간이 부족합니다. 저장 버튼으로 서버에 저장해주세요.';
		}
	}
	async function save() {
		if (saving || !dirty || conflict) return;
		saving = true;
		error = '';
		const snapshot = JSON.stringify($state.snapshot(notebook));
		try {
			const result = await request<{ revision: number }>(`/documents/${docKey()}`, {
				method: 'PUT',
				body: { revision, data: JSON.parse(snapshot) }
			});
			revision = result.revision;
			if (snapshot === JSON.stringify($state.snapshot(notebook))) {
				dirty = false;
				localStorage.removeItem(recoveryKey());
			}
			notice = '내 필기를 저장했습니다.';
		} catch (e) {
			if (e instanceof PersonalApiError && e.status === 409) conflict = true;
			error = String(e);
		} finally {
			saving = false;
		}
	}
	beforeNavigate(({ cancel }) => {
		if (dirty && !confirm('저장 대기 중인 PDF 필기가 있습니다. 이동할까요?')) cancel();
	});
	onMount(() => {
		void (async () => {
			try {
				const pdfjs = await import('pdfjs-dist');
				pdfjs.GlobalWorkerOptions.workerSrc = new URL(
					'pdfjs-dist/build/pdf.worker.min.mjs',
					import.meta.url
				).href;
				const [response, saved] = await Promise.all([
					fetch(url, { credentials: 'include' }),
					request<{ data: PdfNotebook | null; revision: number }>(`/documents/${docKey()}`)
				]);
				if (!response.ok) throw Error('PDF 원본을 불러오지 못했습니다.');
				original = new Uint8Array(await response.arrayBuffer());
				if (disposed) return;
				const sourceTask = pdfjs.getDocument({ data: original.slice() });
				loadingTasks.push(sourceTask);
				pdf = await sourceTask.promise;
				const blankDoc = await (await import('pdf-lib')).PDFDocument.create();
				blankDoc.addPage([595, 842]);
				if (disposed) return;
				const blankTask = pdfjs.getDocument({
					data: await blankDoc.save()
				});
				loadingTasks.push(blankTask);
				blank = await blankTask.promise;
				revision = saved.revision;
				if (saved.data) notebook = saved.data;
				else {
					const pages: PdfPage[] = [];
					for (let i = 0; i < pdf.numPages; i++) {
						const p = await pdf.getPage(i + 1);
						const [x0, y0, x1, y1] = p.view;
						pages.push({
							id: crypto.randomUUID(),
							source: i,
							rotation: p.rotate,
							width: x1 - x0,
							height: y1 - y0,
							strokes: [],
							notes: []
						});
					}
					notebook = { version: 1, pages };
				}
				const local = privateCacheUser() && localStorage.getItem(recoveryKey());
				if (local) {
					const recovery = JSON.parse(local);
					notebook = recovery.data;
					dirty = true;
					if (recovery.revision !== revision) {
						conflict = true;
						error =
							'서버의 PDF 필기가 변경되었습니다. 복구한 필기를 내보낸 뒤 최신 자료를 확인해주세요.';
					}
				}
				loading = false;
				await render();
			} catch (e) {
				error = String(e);
				loading = false;
			}
		})();
	});
	onDestroy(() => {
		disposed = true;
		renderTask?.cancel();
		for (const task of loadingTasks) void task.destroy();
	});
	$effect(() => {
		selected;
		zoom;
		current?.rotation;
		if (!loading && current) void untrack(render);
	});
	$effect(() => {
		notebook;
		dirty;
		if (dirty && !saving && !error && active === null) {
			const timer = setTimeout(() => void save(), 700);
			return () => clearTimeout(timer);
		}
	});
	async function render() {
		if (!canvas || !current || disposed) return;
		const version = ++renderVersion;
		renderTask?.cancel();
		try {
			const source =
				current.source === null ? await blank.getPage(1) : await pdf.getPage(current.source + 1);
			if (version !== renderVersion) return;
			const scale = zoom;
			viewport = source.getViewport({ scale, rotation: current.rotation });
			viewWidth = viewport.width;
			viewHeight = viewport.height;
			const ratio = devicePixelRatio || 1;
			canvas.width = viewWidth * ratio;
			canvas.height = viewHeight * ratio;
			const ctx = canvas.getContext('2d')!;
			ctx.fillStyle = 'white';
			ctx.fillRect(0, 0, canvas.width, canvas.height);
			if (source) {
				renderTask = source.render({
					canvas,
					canvasContext: ctx,
					viewport,
					transform: [ratio, 0, 0, ratio, 0, 0]
				});
				await renderTask.promise;
			}
		} catch (e) {
			if ((e as Error).name !== 'RenderingCancelledException') error = String(e);
		}
	}
	function point(e: PointerEvent): InkPoint {
		const r = (e.currentTarget as SVGElement).getBoundingClientRect();
		const [x, y] = viewport!.convertToPdfPoint(
			((e.clientX - r.left) * viewWidth) / r.width,
			((e.clientY - r.top) * viewHeight) / r.height
		);
		return { x, y, pressure: e.pressure || 0.5 };
	}
	function projected(p: { x: number; y: number }) {
		return viewport?.convertToViewportPoint(p.x, p.y) || [0, 0];
	}
	function path(s: Stroke) {
		return s.points
			.map((p, i) => {
				const [x, y] = projected(p);
				return `${i ? 'L' : 'M'}${x},${y}`;
			})
			.join(' ');
	}
	function start(e: PointerEvent) {
		if (
			!viewport ||
			!current ||
			active !== null ||
			tool === 'pan' ||
			(penOnly && e.pointerType === 'touch')
		)
			return;
		e.preventDefault();
		const p = point(e);
		checkpoint();
		if (tool === 'text') {
			const hit = current.notes.find((n) => Math.hypot(n.x - p.x, n.y - p.y) < 24 / zoom);
			const text = prompt('PDF 메모 (비우면 삭제)', hit?.text || '');
			if (hit && text !== null) {
				if (text) hit.text = text;
				else current.notes = current.notes.filter((n) => n.id !== hit.id);
				change();
				return;
			}
			if (text) {
				current.notes.push({ id: crypto.randomUUID(), x: p.x, y: p.y, text, color, size: 14 });
				change();
			}
			return;
		}
		active = e.pointerId;
		(e.currentTarget as SVGElement).setPointerCapture(e.pointerId);
		if (tool === 'erase' || e.button === 5 || (e.buttons & 32) !== 0) {
			current.strokes = erase(current.strokes, p, 12 / zoom);
			activeStroke = null;
		} else {
			activeStroke = {
				id: crypto.randomUUID(),
				kind: tool === 'highlight' ? 'highlight' : 'pen',
				color,
				width: tool === 'highlight' ? width * 5 : width,
				points: [p]
			};
			current.strokes.push(activeStroke);
		}
		change();
	}
	function move(e: PointerEvent) {
		if (active !== e.pointerId || !current) return;
		e.preventDefault();
		for (const event of e.getCoalescedEvents?.().length ? e.getCoalescedEvents() : [e]) {
			const p = point({
				...event,
				currentTarget: e.currentTarget,
				clientX: event.clientX,
				clientY: event.clientY,
				pressure: event.pressure
			} as PointerEvent);
			if (tool === 'erase' || (e.buttons & 32) !== 0 || !activeStroke)
				current.strokes = erase(current.strokes, p, 12 / zoom);
			else {
				const stroke = current.strokes.find((s) => s.id === activeStroke!.id);
				stroke?.points.push(p);
			}
		}
		notebook = { ...notebook };
	}
	function finish(e: PointerEvent) {
		if (active !== e.pointerId) return;
		active = null;
		activeStroke = null;
		change();
	}
	function pageAction(action: 'add' | 'remove' | 'left' | 'right' | 'rotate') {
		if (!current) return;
		checkpoint();
		if (action === 'add') {
			notebook.pages.splice(selected + 1, 0, {
				id: crypto.randomUUID(),
				source: null,
				rotation: 0,
				width: 595,
				height: 842,
				strokes: [],
				notes: []
			});
			selected++;
		}
		if (action === 'remove' && notebook.pages.length > 1) {
			notebook.pages.splice(selected, 1);
			selected = Math.min(selected, notebook.pages.length - 1);
		}
		if (action === 'rotate') current.rotation = (current.rotation + 90) % 360;
		if (action === 'left' && selected > 0) {
			[notebook.pages[selected - 1], notebook.pages[selected]] = [
				notebook.pages[selected],
				notebook.pages[selected - 1]
			];
			selected--;
		}
		if (action === 'right' && selected < notebook.pages.length - 1) {
			[notebook.pages[selected + 1], notebook.pages[selected]] = [
				notebook.pages[selected],
				notebook.pages[selected + 1]
			];
			selected++;
		}
		notebook = { ...notebook };
		change();
		void render();
	}
	function history(back: boolean) {
		const stack = back ? undo : redo;
		if (!stack.length) return;
		const value = stack.at(-1)!;
		if (back) {
			redo = [...redo, JSON.stringify($state.snapshot(notebook))];
			undo = undo.slice(0, -1);
		} else {
			undo = [...undo, JSON.stringify($state.snapshot(notebook))];
			redo = redo.slice(0, -1);
		}
		notebook = JSON.parse(value);
		selected = Math.min(selected, notebook.pages.length - 1);
		change();
		void render();
	}
	async function preserveConflict() {
		try {
			await request(`/documents/pdf-conflict:${resourceId}:${crypto.randomUUID()}`, {
				method: 'PUT',
				body: { revision: 0, data: $state.snapshot(notebook) }
			});
			localStorage.removeItem(recoveryKey());
			dirty = false;
			location.reload();
		} catch (e) {
			error = String(e);
		}
	}
	async function download() {
		try {
			const bytes = await exportPdf(original, $state.snapshot(notebook));
			const link = document.createElement('a');
			link.href = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }));
			link.download = name.replace(/\.pdf$/i, '') + '-필기.pdf';
			link.click();
			setTimeout(() => URL.revokeObjectURL(link.href), 1000);
		} catch (e) {
			error = String(e);
		}
	}
</script>

<svelte:window
	onbeforeunload={(e) => {
		if (dirty) e.preventDefault();
	}}
/>
<section class="pdf-editor">
	<header>
		<h2>{name}</h2>
		<span role="status"
			>{loading ? 'PDF 불러오는 중…' : saving ? '저장 중…' : dirty ? '저장 대기' : '저장됨'}</span
		><button onclick={() => (toolbar = !toolbar)} aria-expanded={toolbar}>도구</button><button
			disabled={loading || saving || !dirty || conflict}
			onclick={save}>저장</button
		><button disabled={loading} onclick={download}>필기 포함 PDF 내보내기</button>
	</header>
	{#if error}<p role="alert">{error}</p>
		{#if conflict}<button onclick={preserveConflict}>복구본 별도 보존 후 최신 필기 불러오기</button
			>{/if}{/if}{#if notice}<p role="status">{notice}</p>{/if}
	{#if toolbar}<div class="toolbar">
			<select aria-label="PDF 도구" bind:value={tool}
				><option value="pen">펜</option><option value="highlight">형광펜</option><option
					value="erase">지우개</option
				><option value="text">텍스트 주석</option><option value="pan">이동</option></select
			><label>색<input type="color" bind:value={color} /></label><label
				>굵기<input type="range" min="1" max="10" bind:value={width} /></label
			><label><input type="checkbox" bind:checked={penOnly} />펜으로만 필기</label><button
				disabled={!undo.length}
				onclick={() => history(true)}>실행 취소</button
			><button disabled={!redo.length} onclick={() => history(false)}>다시 실행</button><label
				>확대<select bind:value={zoom}
					>{#each [0.5, 0.75, 1, 1.25, 1.5, 2] as z}<option value={z}>{z * 100}%</option
						>{/each}</select
				></label
			>
		</div>{/if}
	{#if current}<div class="pages">
			<button disabled={selected === 0} onclick={() => selected--}>이전 페이지</button><select
				aria-label="PDF 페이지"
				bind:value={selected}
				>{#each notebook.pages as p, i}<option value={i}
						>{i + 1}쪽{p.source === null ? ' · 빈 페이지' : ''}</option
					>{/each}</select
			><button disabled={selected === notebook.pages.length - 1} onclick={() => selected++}
				>다음 페이지</button
			><button onclick={() => pageAction('add')}>빈 페이지 추가</button><button
				disabled={notebook.pages.length === 1}
				onclick={() => pageAction('remove')}>페이지 삭제</button
			><button onclick={() => pageAction('rotate')}>회전</button><button
				disabled={selected === 0}
				onclick={() => pageAction('left')}>앞으로 옮기기</button
			><button disabled={selected === notebook.pages.length - 1} onclick={() => pageAction('right')}
				>뒤로 옮기기</button
			>
		</div>{/if}
	<div class="viewport">
		<div class="paper" style:width={`${viewWidth}px`} style:height={`${viewHeight}px`}>
			<canvas bind:this={canvas}></canvas>{#if current && !loading}<svg
					viewBox={`0 0 ${viewWidth} ${viewHeight}`}
					role="img"
					aria-label="PDF 필기 영역"
					onpointerdown={start}
					onpointermove={move}
					onpointerup={finish}
					onpointercancel={finish}
					onlostpointercapture={finish}
					oncontextmenu={(e) => e.preventDefault()}
					style:touch-action={penOnly || tool === 'pan' ? 'pan-x pan-y pinch-zoom' : 'none'}
					>{#each current.strokes as s}<path
							d={path(s)}
							fill="none"
							stroke={s.color}
							stroke-width={s.width * zoom}
							stroke-linecap="round"
							stroke-linejoin="round"
							opacity={s.kind === 'highlight' ? 0.25 : 1}
						/>{/each}{#each current.notes as n}{@const xy = projected(n)}<text
							x={xy[0]}
							y={xy[1]}
							fill={n.color}
							font-size={n.size * zoom}>{n.text}</text
						>{/each}</svg
				>{/if}
		</div>
	</div>
</section>

<style>
	.pdf-editor {
		min-width: 0;
	}
	header {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	header h2 {
		font-size: 18px;
		flex: 1;
		overflow-wrap: anywhere;
	}
	.toolbar,
	.pages {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		padding: 12px 0;
		align-items: center;
	}
	.toolbar label {
		display: flex;
		gap: 5px;
		align-items: center;
		font-size: 14px;
	}
	.toolbar input[type='range'] {
		width: 80px;
	}
	.toolbar input[type='color'] {
		width: 28px;
		padding: 0;
	}
	.viewport {
		height: 70vh;
		overflow: auto;
		background: #30333a;
		padding: 20px;
		overscroll-behavior: contain;
	}
	.paper {
		position: relative;
		margin: auto;
		background: white;
		box-shadow: 0 3px 16px #0006;
	}
	.paper canvas,
	.paper svg {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
	}
	.paper svg {
		user-select: none;
	}
	button {
		font-size: 14px;
		min-height: 36px;
	}
	p[role='alert'] {
		color: #b32946;
	}
</style>
