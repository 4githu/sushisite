<script lang="ts">
	import { copyInk, pasteInk, inPolygon, partialErase } from './ink';
	import { onMount, onDestroy, untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { request, PersonalApiError } from '../shared/api';
	import { privateCacheUser } from '../shared/auth';
	import { verifiedPrivateOwner, samePrivateOwner } from '../shared/private-owner';
	let notebookOwner = '';
	import type { CalendarEvent } from '../shared/types';
	import { dailyEventLayout } from './daily-events';
	import {
		erase,
		exportPdf,
		type PdfNotebook,
		type PdfPage,
		type InkPoint,
		type Stroke
	} from './model';
	let {
		resourceId,
		url,
		name,
		daily = false,
		compactDaily = false,
		onempty,
		oneventdrag,
		events = [],
		date = '',
		onevent,
		onSaveSource
	}: {
		resourceId: string;
		url: string;
		name: string;
		daily?: boolean;
		compactDaily?: boolean;
		onempty?: (minute: number) => void;
		oneventdrag?: (event: CalendarEvent, drag: DragEvent) => void;
		events?: CalendarEvent[];
		date?: string;
		onevent?: (e: CalendarEvent) => void;
		onSaveSource?: (file: File) => Promise<void>;
	} = $props();
	let noteDialog: HTMLDialogElement;
	let inkNote = $state<{ id: string | null; x: number; y: number; text: string } | null>(null);
	function saveInkNote(event: SubmitEvent) {
		event.preventDefault();
		if (!current || !inkNote) return;
		checkpoint();
		if (inkNote.id) current.notes = current.notes.filter((n) => n.id !== inkNote!.id);
		if (inkNote.text.trim())
			current.notes.push({
				id: inkNote.id || crypto.randomUUID(),
				x: inkNote.x,
				y: inkNote.y,
				text: inkNote.text,
				color,
				size: 14
			});
		change();
		inkNote = null;
		noteDialog.close();
	}
	function emptyClick(event: MouseEvent) {
		if (
			!compactDaily ||
			tool !== 'pan' ||
			(event.target instanceof Element && event.target.closest('button'))
		)
			return;
		const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
		const y = ((event.clientY - rect.top) / rect.height) * 760;
		const minute = Math.min(1545, 480 + Math.round(((y - 22) / 40) * 4) * 15);
		if (minute >= 480 && minute < 1560) onempty?.(minute);
	}
	const eventBoxes = $derived(daily && date ? dailyEventLayout(events, date) : []);
	const allDayEvents = $derived(
		events.filter(
			(e) =>
				e.isAllDay &&
				e.startTime.slice(0, 10) <= date &&
				(e.endTime ? e.endTime.slice(0, 10) > date : e.startTime.slice(0, 10) === date)
		)
	);
	let notebook = $state<PdfNotebook>({ version: 1, pages: [] }),
		selected = $state(0),
		zoom = $state(1),
		tool = $state<'pen' | 'highlight' | 'erase' | 'text' | 'pan' | 'lasso'>('pen'),
		color = $state('#25262b'),
		width = $state(3),
		penOnly = $state(true),
		toolbar = $state(true),
		loading = $state(true),
		saving = $state(false),
		savingSource = $state(false),
		error = $state(''),
		notice = $state(''),
		dirty = $state(false),
		conflict = $state(false),
		revision = 0;
	let loadingTasks: import('pdfjs-dist').PDFDocumentLoadingTask[] = [];
	let eraseMode = $state<'stroke' | 'partial'>('stroke'),
		selectedInk = $state<string[]>([]),
		lasso = $state<InkPoint[]>([]);
	let movingSelection: InkPoint | null = null,
		selectionBefore: Stroke[] = [];
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
	const recoveryKey = () =>
		`ondo-private:${compactDaily ? notebookOwner : privateCacheUser()}:pdf:${resourceId}`;
	const docKey = () => `pdf:${resourceId}`;
	function checkpoint() {
		undo = [...undo.slice(-39), JSON.stringify($state.snapshot(notebook))];
		redo = [];
	}
	function change() {
		dirty = true;
		try {
			if (compactDaily ? notebookOwner : privateCacheUser())
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
			if (compactDaily && !(await samePrivateOwner(notebookOwner)))
				throw new Error('계정이 바뀌었어요. 필기 내용을 다시 확인해주세요.');
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
		if (compactDaily) {
			tool = 'pan';
			toolbar = false;
		}
		void (async () => {
			try {
				if (compactDaily) notebookOwner = await verifiedPrivateOwner();
				const pdfjs = await import('pdfjs-dist');
				pdfjs.GlobalWorkerOptions.workerSrc = new URL(
					'pdfjs-dist/build/pdf.worker.min.mjs',
					import.meta.url
				).href;
				const [response, saved] = await Promise.all([
					daily ? Promise.resolve(null) : fetch(url, { credentials: 'include' }),
					request<{ data: PdfNotebook | null; revision: number }>(`/documents/${docKey()}`)
				]);
				if (daily) {
					const { PDFDocument, StandardFonts, rgb } = await import('pdf-lib');
					const doc = await PDFDocument.create(),
						p = doc.addPage([420, 760]),
						font = await doc.embedFont(StandardFonts.Helvetica);
					for (let i = 0; i <= 18; i++) {
						const y = 738 - i * 40;
						p.drawLine({
							start: { x: 42, y },
							end: { x: 410, y },
							thickness: 0.4,
							color: rgb(0.82, 0.83, 0.85)
						});
						if (i < 18)
							p.drawText(`${String((8 + i) % 24).padStart(2, '0')}:00`, {
								x: 5,
								y: y - 12,
								size: compactDaily ? 14 : 9,
								font,
								color: rgb(0.4, 0.4, 0.45)
							});
					}
					original = await doc.save();
				} else {
					if (!response?.ok) throw Error('PDF 원본을 불러오지 못했습니다.');
					original = new Uint8Array(await response.arrayBuffer());
				}
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
				const local =
					(compactDaily ? notebookOwner : privateCacheUser()) &&
					localStorage.getItem(recoveryKey());
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
	function eraseAt(p: InkPoint) {
		if (current)
			current.strokes =
				eraseMode === 'stroke'
					? erase(current.strokes, p, 12 / zoom)
					: partialErase(current.strokes, p, 12 / zoom);
	}
	function copySelection() {
		if (current)
			copyInk(
				structuredClone($state.snapshot(current.strokes.filter((s) => selectedInk.includes(s.id))))
			);
	}
	function pasteSelection() {
		if (!current) return;
		checkpoint();
		const pasted = pasteInk(18, -18);
		current.strokes.push(...pasted);
		selectedInk = pasted.map((s) => s.id);
		change();
	}
	function deleteSelection() {
		if (!current) return;
		checkpoint();
		current.strokes = current.strokes.filter((s) => !selectedInk.includes(s.id));
		selectedInk = [];
		change();
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
		(e.currentTarget as SVGElement)
			.closest<HTMLElement>('[role=application]')
			?.focus({ preventScroll: true });
		const p = point(e);
		checkpoint();
		if (tool === 'text') {
			const hit = current.notes.find((n) => Math.hypot(n.x - p.x, n.y - p.y) < 24 / zoom);
			if (compactDaily) {
				inkNote = {
					id: hit?.id || null,
					x: hit?.x ?? p.x,
					y: hit?.y ?? p.y,
					text: hit?.text || (!inkNote?.id ? inkNote?.text : '') || ''
				};
				noteDialog.showModal();
				return;
			}
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
		if (tool === 'lasso') {
			const hit = current.strokes
				.filter((s) => selectedInk.includes(s.id))
				.some((s) => s.points.some((q) => Math.hypot(q.x - p.x, q.y - p.y) < 20 / zoom));
			if (hit) {
				movingSelection = p;
				selectionBefore = structuredClone($state.snapshot(current.strokes));
			} else {
				selectedInk = [];
				lasso = [p];
				movingSelection = null;
			}
			return;
		}
		if (
			tool === 'erase' ||
			e.button === 5 ||
			(e.buttons & 32) !== 0 ||
			(e.pointerType === 'pen' && (e.buttons & 2) !== 0)
		) {
			eraseAt(p);
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
			if (tool === 'lasso') {
				if (movingSelection) {
					const dx = p.x - movingSelection.x,
						dy = p.y - movingSelection.y;
					current.strokes = selectionBefore.map((s) =>
						selectedInk.includes(s.id)
							? { ...s, points: s.points.map((q) => ({ ...q, x: q.x + dx, y: q.y + dy })) }
							: s
					);
				} else lasso = [...lasso, p];
				continue;
			}
			if (
				tool === 'erase' ||
				(e.buttons & 32) !== 0 ||
				(e.pointerType === 'pen' && (e.buttons & 2) !== 0) ||
				!activeStroke
			)
				eraseAt(p);
			else {
				const stroke = current.strokes.find((s) => s.id === activeStroke!.id);
				stroke?.points.push(p);
			}
		}
		notebook = { ...notebook };
	}
	function finish(e: PointerEvent) {
		if (active !== e.pointerId) return;
		if (tool === 'lasso' && !movingSelection && current)
			selectedInk = current.strokes
				.filter((s) => s.points.some((p) => inPolygon(p, lasso)))
				.map((s) => s.id);
		lasso = [];
		movingSelection = null;
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
			let background = original;
			if (daily && (eventBoxes.length || allDayEvents.length)) {
				const { PDFDocument, rgb } = await import('pdf-lib');
				const doc = await PDFDocument.load(original);
				doc.registerFontkit((await import('@pdf-lib/fontkit')).default);
				const response = await fetch('/fonts/NanumGothic-Regular.ttf');
				if (!response.ok) throw Error('일정 출력 글꼴을 불러오지 못했습니다.');
				const font = await doc.embedFont(await response.arrayBuffer(), { subset: true }),
					p = doc.getPage(0);
				for (const box of eventBoxes) {
					p.drawRectangle({
						x: box.x,
						y: 760 - box.y - box.height,
						width: box.width,
						height: box.height,
						color: rgb(0.84, 0.9, 0.95),
						opacity: 0.6
					});
					let title = box.event.title;
					while (title.length && font.widthOfTextAtSize(title, 8) > box.width - 8)
						title = title.slice(0, -1);
					p.drawText(title, {
						x: box.x + 4,
						y: 760 - box.y - 10,
						size: 8,
						font,
						color: rgb(0.2, 0.3, 0.4)
					});
				}
				if (allDayEvents.length)
					p.drawText(('종일 · ' + allDayEvents.map((e) => e.title).join(' · ')).slice(0, 45), {
						x: 44,
						y: 746,
						size: 8,
						font
					});
				background = await doc.save();
			}
			const bytes = await exportPdf(background, $state.snapshot(notebook));
			const link = document.createElement('a');
			link.href = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }));
			link.download = name.replace(/\.pdf$/i, '') + '-필기.pdf';
			link.click();
			setTimeout(() => URL.revokeObjectURL(link.href), 1000);
		} catch (e) {
			error = String(e);
		}
	}
	async function saveSource() {
		if (!onSaveSource || loading || saving || savingSource || conflict) return;
		savingSource = true;
		error = '';
		try {
			if (dirty) await save();
			if (dirty) throw Error('필기를 저장하지 못했습니다.');
			const bytes = await exportPdf(original, $state.snapshot(notebook));
			await onSaveSource(
				new File([new Blob([bytes as BlobPart])], name, { type: 'application/pdf' })
			);
			notice = '수정본을 저장했습니다.';
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		} finally {
			savingSource = false;
		}
	}
</script>

<svelte:window
	onbeforeunload={(e) => {
		if (dirty) e.preventDefault();
	}}
/>
<section class="pdf-editor" class:daily-paper={daily} class:daily-compact={compactDaily}>
	<header>
		<h2>{name}</h2>
		<span role="status"
			>{loading
				? daily
					? '필기 불러오는 중…'
					: 'PDF 불러오는 중…'
				: saving
					? '저장 중…'
					: dirty
						? '저장 대기'
						: '저장됨'}</span
		><button onclick={() => (toolbar = !toolbar)} aria-expanded={toolbar}>도구</button
		>{#if onSaveSource}<button
				disabled={loading || saving || savingSource || conflict}
				onclick={saveSource}>{savingSource ? '저장 중…' : '수정본 저장'}</button
			>{:else}<button disabled={loading || saving || !dirty || conflict} onclick={save}>저장</button
			>{#if !compactDaily}<button disabled={loading} onclick={download}
					>{daily ? 'PDF로 저장' : '필기 포함 PDF 내보내기'}</button
				>{/if}{/if}
	</header>
	{#if error}<p role="alert">{error}</p>
		{#if conflict}<button onclick={preserveConflict}>복구본 별도 보존 후 최신 필기 불러오기</button
			>{/if}{/if}{#if notice}<p role="status">{notice}</p>{/if}
	{#if compactDaily}<nav class="daily-ink-tools" aria-label="시간표 도구">
			{#each [{ id: 'pan', label: '일정' }, { id: 'pen', label: '펜' }, { id: 'highlight', label: '형광펜' }, { id: 'erase', label: '지우개' }, { id: 'text', label: '메모' }] as item}<button
					type="button"
					aria-pressed={tool === item.id}
					disabled={loading}
					onclick={() => (tool = item.id as typeof tool)}>{item.label}</button
				>{/each}
		</nav>{/if}
	{#if toolbar}<div class="toolbar">
			<select aria-label="PDF 도구" bind:value={tool}
				><option value="pen">펜</option><option value="highlight">형광펜</option><option
					value="erase">지우개</option
				><option value="lasso">올가미 선택·이동</option><option value="text">텍스트 주석</option
				><option value="pan">이동</option></select
			>{#if tool === 'erase'}<select aria-label="지우개 방식" bind:value={eraseMode}
					><option value="stroke">획 지우개</option><option value="partial">부분 지우개</option
					></select
				>{/if}{#if tool === 'lasso'}<button
					onclick={() => (selectedInk = current?.strokes.map((s) => s.id) || [])}>전체 선택</button
				><button disabled={!selectedInk.length} onclick={copySelection}>선택 복사</button><button
					onclick={pasteSelection}>붙여넣기</button
				><button disabled={!selectedInk.length} onclick={deleteSelection}>선택 삭제</button>{/if}
			<div class="ink-presets" aria-label="펜 색상">
				{#each ['#25262b', '#d94d45', '#266dcc', '#31936b', '#ffc83d', '#c084fc'] as preset}<button
						aria-label={`펜 색 ${preset}`}
						style={`background:${preset};width:24px;height:24px;border-radius:50%;border:2px solid ${color === preset ? 'currentColor' : 'transparent'}`}
						onclick={() => (color = preset)}
					></button>{/each}
			</div>
			<label>색<input type="color" bind:value={color} /></label><label
				>굵기<input type="range" min="1" max="10" bind:value={width} /></label
			><label><input type="checkbox" bind:checked={penOnly} />펜으로만 필기</label><small
				>필기 영역 이동은 ‘이동’ 도구를 선택하세요.</small
			><button disabled={!undo.length} onclick={() => history(true)}>실행 취소</button><button
				disabled={!redo.length}
				onclick={() => history(false)}>다시 실행</button
			>{#if !daily}<label
					>확대<select bind:value={zoom}
						>{#each [0.5, 0.75, 1, 1.25, 1.5, 2] as z}<option value={z}>{z * 100}%</option
							>{/each}</select
					></label
				>{/if}
		</div>{/if}
	{#if current && !daily}<div class="pages">
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
	<!-- Custom drawing application supports focus and selection clipboard shortcuts. -->
	<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
	<div
		class="viewport"
		onkeydown={(e) => {
			if ((e.ctrlKey || e.metaKey) && e.key === 'c' && selectedInk.length) {
				e.preventDefault();
				copySelection();
			}
			if ((e.ctrlKey || e.metaKey) && e.key === 'v' && tool === 'lasso') {
				e.preventDefault();
				pasteSelection();
			}
		}}
		role="application"
		tabindex="0"
		aria-label="필기 작업 공간"
	>
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
		<div
			class="paper"
			role="group"
			aria-label={daily?'하루 필기 종이':'문서 페이지'}
			tabindex={compactDaily?0:undefined}
			onkeydown={(e) => {
				if (compactDaily && tool === 'pan' && e.key === 'Enter' && e.target === e.currentTarget) {
					e.preventDefault();
					onempty?.(540);
				}
			}}
			onclick={emptyClick}
			style:width={`${viewWidth}px`}
			style:height={`${viewHeight}px`}
		>
			{#if daily}<div class="event-underlay" class:interactive={tool === 'pan'}>
					{#if allDayEvents.length}<div class="all-day-ink">
							종일 · {allDayEvents.map((e) => e.title).join(' · ')}
						</div>{/if}
					{#each eventBoxes as box}<button
							type="button"
							tabindex={tool === 'pan' ? 0 : -1}
							aria-label={`${box.event.title} 일정 열기`}
							onclick={() => onevent?.(box.event)}
							draggable={compactDaily && box.event.type === 'netaq-plan'}
							ondragstart={(event) => oneventdrag?.(box.event, event)}
							class:planned={box.event.type === 'netaq-plan'}
							class:google-event={box.event.type === 'google'}
							class:completed={box.event.status === 'done'}
							style={`left:${(box.x / 420) * 100}%;top:${(box.y / 760) * 100}%;width:${(box.width / 420) * 100}%;height:${(box.height / 760) * 100}%`}
							><strong>{box.event.title}</strong><small
								>{new Date(box.event.startTime).toLocaleTimeString('ko-KR', {
									hour: '2-digit',
									minute: '2-digit',
									hour12: false
								})}{box.event.endTime
									? '–' +
										new Date(box.event.endTime).toLocaleTimeString('ko-KR', {
											hour: '2-digit',
											minute: '2-digit',
											hour12: false
										})
									: ''}</small
							></button
						>{/each}
				</div>{/if}
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
					style:touch-action={tool === 'pan' ? 'pan-x pan-y pinch-zoom' : 'none'}
					style:pointer-events={daily && tool === 'pan' ? 'none' : 'auto'}
					>{#if lasso.length}<path
							d={path({ id: 'lasso', kind: 'pen', width: 1, color: '#666', points: lasso })}
							fill="#8882"
							stroke="#666"
							stroke-dasharray="4 3"
						/>{/if}{#each current.strokes as s}<path
							d={path(s)}
							fill="none"
							stroke={selectedInk.includes(s.id) ? '#d24928' : s.color}
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

<dialog class="daily-note-dialog" bind:this={noteDialog} aria-label="시간표 메모">
	<form onsubmit={saveInkNote}>
		<h2>메모</h2>
		<textarea
			aria-label="시간표에 쓸 메모"
			value={inkNote?.text || ''}
			oninput={(e) => {
				if (inkNote) inkNote.text = e.currentTarget.value;
			}}
			maxlength="2000"
			placeholder="시간표 위에 적어두세요"
		></textarea>
		<footer>
			<button type="button" onclick={() => noteDialog.close()}>닫기</button><button>적용</button>
		</footer>
	</form>
</dialog>

<style>
	.event-underlay {
		position: absolute;
		inset: 0;
		z-index: 1;
		pointer-events: none;
	}
	.pdf-editor .event-underlay button {
		position: absolute;
		min-height: 0;
		overflow: hidden;
		padding: 2px 5px;
		text-align: left;
		border: 0;
		border-left: 2px solid #688eae;
		border-radius: 3px;
		background: #d7e7f280;
		color: #354d60;
		font-size: 10px;
		line-height: 1.2;
	}
	.event-underlay strong,
	.event-underlay small {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.event-underlay.interactive {
		pointer-events: auto;
	}
	.all-day-ink {
		position: absolute;
		top: 0;
		left: 44px;
		right: 8px;
		font-size: 10px;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.paper svg {
		z-index: 2;
	}
	.pdf-editor button,
	.pdf-editor select {
		font: inherit;
		font-size: 12px;
		color: inherit;
		background: white;
		border: 1px solid #d6d8de;
		border-radius: 6px;
		padding: 6px 8px;
		min-height: 30px;
	}
	.pdf-editor button:disabled {
		opacity: 0.45;
	}
	.ink-presets {
		display: flex;
		gap: 3px;
	}
	.ink-presets button {
		padding: 0 !important;
		min-height: 22px !important;
		min-width: 22px !important;
		flex: 0 0 22px !important;
	}
	.daily-paper header {
		gap: 6px;
	}
	.daily-paper header h2 {
		min-width: 68px;
	}
	.daily-paper .toolbar {
		gap: 6px;
	}
	.daily-paper .toolbar label {
		font-size: 12px;
	}

	.daily-paper .viewport {
		height: auto;
		overflow: visible;
		background: transparent;
		padding: 0;
	}
	.daily-paper .paper {
		max-width: 100%;
		box-shadow: none;
		height: auto !important;
		aspect-ratio: 420/760;
		width: 100% !important;
	}
	.daily-paper header h2 {
		font-size: 16px;
	}
	.daily-paper .toolbar {
		padding: 8px 0;
	}
	.daily-paper .paper canvas,
	.daily-paper .paper svg {
		width: 100%;
		height: 100%;
	}
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

	.daily-compact header {
		justify-content: flex-end;
		min-height: 28px;
		gap: 8px;
	}
	.daily-compact header h2 {
		display: none;
	}
	.daily-compact header span {
		margin-right: auto;
		font-size: 11px;
		color: #696b73;
	}
	.daily-compact header button {
		font-size: 11px;
		min-height: 28px;
		padding: 4px 8px;
	}
	.daily-ink-tools {
		display: flex;
		gap: 4px;
		margin: 8px 0 12px;
	}
	.daily-ink-tools button {
		flex: 1;
		min-height: 36px;
		font-size: 13px;
		padding: 6px 2px;
		background: white;
		border: 1px solid #e2e3e7;
	}
	.daily-ink-tools button[aria-pressed='true'] {
		color: #c4412c;
		background: #faeee9;
		border-color: #e5bcaf;
	}
	.daily-compact .viewport {
		overflow: auto;
		max-height: calc(100dvh - 220px);
		overscroll-behavior: contain;
	}
	.daily-compact .event-underlay button {
		background: #eaf3ee;
		color: #27634b;
		border-left-color: #27634b;
		padding: 3px 5px;
		font-size: 13px;
	}
	.daily-compact .event-underlay small {
		font-size: 11px;
		line-height: 1.3;
	}
	.daily-compact .event-underlay .google-event {
		background: #edf2fa;
		color: #365b91;
		border-left-color: #365b91;
	}
	.daily-compact .event-underlay .completed {
		opacity: 0.6;
	}
	.daily-compact .event-underlay .completed strong {
		text-decoration: line-through;
	}
	.daily-compact .event-underlay .planned {
		background: #faf3e3;
		color: #815d20;
		border-left-color: #815d20;
	}
	.daily-note-dialog {
		position: fixed;
		inset: 0;
		margin: auto;
		width: min(420px, calc(100vw - 32px));
		border: 1px solid #e2e3e7;
		border-radius: 12px;
		padding: 20px;
		box-sizing: border-box;
		color: #242529;
		background: white;
	}
	.daily-note-dialog::backdrop {
		background: #14151959;
	}
	.daily-note-dialog form {
		display: grid;
		gap: 16px;
	}
	.daily-note-dialog h2 {
		font-size: 20px;
		margin: 0;
	}
	.daily-note-dialog textarea {
		width: 100%;
		box-sizing: border-box;
		min-height: 100px;
		border: 1px solid #e2e3e7;
		border-radius: 8px;
		padding: 12px;
		font: inherit;
		font-size: 16px;
	}
	.daily-note-dialog footer {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
	.daily-note-dialog button {
		min-height: 40px;
		border: 1px solid #e2e3e7;
		border-radius: 8px;
		background: white;
		padding: 8px 16px;
		font: inherit;
	}
	.daily-note-dialog button:last-child {
		background: #c4412c;
		color: white;
		border: 0;
	}
</style>
