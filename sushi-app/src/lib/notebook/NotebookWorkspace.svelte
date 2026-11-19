<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
	import type { NotebookPage, NotebookItem, InkPoint } from './types';

	import { onMount, untrack, tick } from 'svelte';
	import { uploadResource } from '../personal-project/resources/api';
	import PersonalColorPicker from '../personal-project/editor/PersonalColorPicker.svelte';
	import PersonalTextEditor from '../personal-project/editor/PersonalTextEditor.svelte';
	import AnchoredPopover from './AnchoredPopover.svelte';
	import { centerline, horizontalPageSwipe } from './ink-render';
	import {
		visiblePageIndices,
		visiblePageRows,
		adjacentPage,
		createPenInput,
		usesAndroidPen
	} from './view-input';
	const penInput = createPenInput(() => androidPen);
	import PassivePage from './PassivePage.svelte';
	import Thumb from './Thumb.svelte';
	import { createDriveAdapter } from './drive-adapter';
	import { getStroke } from 'perfect-freehand';
	import * as pdfjs from 'pdfjs-dist';
	import worker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
	import { icon } from './icons';
	import { bounds, createLassoSelector, segmentDistance } from './geometry';
	import * as localStorageAdapter from './storage';
	import { pdfOptions } from './pdf-config';
	import PaperOptions from './PaperOptions.svelte';
	import {
		type PaperTemplate,
		readPaperDefault,
		savePaperDefault,
		createPaperPage,
		paperColors,
		paperFor
	} from './paper';
	import PenDiagnostics from './PenDiagnostics.svelte';
	import './notebook.css';
	let {
		resourceId = null,
		url = null,
		name = null,
		onclose = undefined,
		documentStorage = undefined,
		remoteStorage = false,
		initialPaper = undefined,
		defaultPaper = undefined,
		onpaperdefaultchange = undefined,
		libraryMode = false,
		onhome = undefined,
		ontitlechange = undefined,
		daily = false,
		background = undefined,
		ondailytap = undefined
	}: {
		resourceId?: string | null;
		url?: string | null;
		name?: string | null;
		onclose?: () => void;
		documentStorage?: { read: (url: string) => Promise<any>; save: (value: any) => Promise<void> };
		remoteStorage?: boolean;
		initialPaper?: PaperTemplate;
		defaultPaper?: PaperTemplate;
		onpaperdefaultchange?: (p: PaperTemplate) => void;
		libraryMode?: boolean;
		onhome?: () => void;
		ontitlechange?: (title: string) => void;
		daily?: boolean;
		background?: Snippet;
		ondailytap?: (x: number, y: number) => void;
	} = $props();
	const drive = untrack(() => (resourceId ? createDriveAdapter(resourceId) : null));
	const storage = untrack(() => documentStorage) || drive || localStorageAdapter;
	const remote = Boolean(drive || untrack(() => remoteStorage));
	let paperDefaults = $state<PaperTemplate>(untrack(() => defaultPaper) || readPaperDefault());
	$effect(() => {
		if (defaultPaper) paperDefaults = { ...defaultPaper };
	});
	let paperMenu = $state(false),
		paperButton = $state<HTMLButtonElement | null>(null),
		penDiagnostics = $state(false);
	let androidPen = $state(false),
		barrelTool = $state('lasso'),
		temporaryTool = $state<string | null>(null);
	pdfjs.GlobalWorkerOptions.workerSrc = worker;
	const tools = [
		['lasso', '선택'],
		['pen', '펜'],
		['highlight', '형광펜'],
		['eraser', '지우개'],
		['text', '텍스트'],
		['memo', '메모'],
		['hand', '이동']
	];
	let editing = $state(!drive),
		focusMode = $state(false),
		toolTip = $state(''),
		toolTipX = $state(0),
		toolTipY = $state(0);
	let toolTipTimer: ReturnType<typeof setTimeout>;
	let navigationButton = $state<HTMLButtonElement | null>(null),
		imageButton = $state<HTMLButtonElement | null>(null),
		presetButton = $state<HTMLButtonElement | null>(null);
	async function goHome() {
		if (onhome) {
			if (await persist()) onhome();
			return;
		}
		if (await persist()) window.location.assign('/personal-project/calendar');
	}
	async function goBack() {
		if (await persist()) onclose?.();
	}
	function readerSize(node: HTMLElement) {
		const sync = () => {
			node.style.setProperty(
				'--reader-height',
				Math.max(
					160,
					(window.visualViewport?.height ?? window.innerHeight) -
						Math.max(
							0,
							node.getBoundingClientRect().top - (window.visualViewport?.offsetTop ?? 0)
						) -
						(drive ? 8 : 0)
				) + 'px'
			);
		};
		sync();
		window.addEventListener('resize', sync);
		window.visualViewport?.addEventListener('resize', sync);
		return {
			destroy() {
				window.removeEventListener('resize', sync);
				window.visualViewport?.removeEventListener('resize', sync);
			}
		};
	}

	function toolName(label: string, e: MouseEvent) {
		const r =
			e.currentTarget instanceof HTMLElement ? e.currentTarget.getBoundingClientRect() : null;
		toolTipX = r ? r.left + r.width / 2 : 0;
		toolTipY = r ? r.bottom + 4 : 0;
		toolTip = label;
		clearTimeout(toolTipTimer);
		toolTipTimer = setTimeout(() => (toolTip = ''), 850);
	}
	let twoPage = $state(false);
	let pageMode = $state('paged'),
		navigationOpen = $state(false);
	async function activatePage(i: number, e?: PointerEvent) {
		if (penId !== null) return;
		pageIndex = i;
		selected = [];
		activeText = null;
		await tick();
		if (e) down(e);
	}
	function pageScroll(index: number) {
		if (pageMode === 'continuous') {
			const slot = viewport?.querySelector('[data-page-slot="' + index + '"]');
			slot?.scrollIntoView({ block: 'start', inline: 'nearest' });
		} else viewport?.scrollTo({ top: 0, left: 0 });
	}
	function changeMode(mode: string) {
		pageMode = mode;
		navigationOpen = false;
		tick().then(() => {
			fit();
			pageScroll(pageIndex);
		});
	}
	function toggleTwoPage() {
		twoPage = !twoPage;
		tick().then(() => {
			fit();
			pageScroll(pageIndex);
		});
	}
	let presets = $state([
			{ color: '#242529', width: 1.4 },
			{ color: '#c4412c', width: 2.3 },
			{ color: '#697f9a', width: 2.8 }
		]),
		presetIndex = $state(0),
		presetOpen = $state(false),
		railWidth = $state(200),
		thumbSize = $state(72);
	function choosePreset(i: number) {
		if (tool === 'pen' && presetIndex === i) presetOpen = !presetOpen;
		else {
			tool = 'pen';
			presetOpen = false;
		}
		presetIndex = i;
		color = presets[i].color;
		size = presets[i].width;
	}
	function updatePreset(c?: string, w?: number | string) {
		const next = { color: c || color, width: Number(w || size) };
		presets[presetIndex] = next;
		color = next.color;
		size = next.width;
		try {
			localStorage.setItem('netaq-pen-presets', JSON.stringify(presets));
		} catch {}
	}
	function resizeRail(e: PointerEvent) {
		e.preventDefault();
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		const start = e.clientX,
			w = railWidth;
		const move = (e: PointerEvent) =>
			(railWidth = Math.max(100, Math.min(360, w + e.clientX - start)));
		const end = () => {
			window.removeEventListener('pointermove', move);
			window.removeEventListener('pointerup', end);
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', end, { once: true });
	}
	const freshPage = (template: PaperTemplate = paperDefaults): NotebookPage =>
		createPaperPage(template);
	let title = $state(untrack(() => name) || '제목 없는 노트'),
		pages = $state<NotebookPage[]>([freshPage(untrack(() => initialPaper || paperDefaults))]),
		pageIndex = $state(0),
		tool = $state(drive || untrack(() => daily) ? 'hand' : 'pen'),
		color = $state('#242529'),
		size = $state(1.4),
		zoom = $state(0.8),
		rail = $state(!drive && !untrack(() => libraryMode || daily)),
		imageMenu = $state(false),
		lassoMode = $state('touch'),
		eraseMode = $state('stroke');
	let dailySettings = $state(false);
	let ready = $state(false),
		status = $state(''),
		saveState = $state('저장 준비 중'),
		quotaFailed = $state(false),
		paperEl = $state<HTMLDivElement>(null!),
		viewport: HTMLElement,
		canvasHost = $state<HTMLDivElement>(null!),
		textToolbarHost = $state<HTMLDivElement>(null!);
	let activeText = $state<string | null>(null),
		selected = $state<string[]>([]),
		lasso = $state<InkPoint[]>([]),
		draft = $state<any>(null),
		pdf = $state.raw<PDFDocumentProxy | null>(null),
		pdfBytes: ArrayBuffer | null = null,
		pdfName = $state(''),
		pdfSourceUrl = '',
		pageBusy = $state(false),
		textVersion = $state(0),
		memoOpen = $state<string | null>(null);
	let pdfInput: HTMLInputElement,
		imageInput: HTMLInputElement,
		cameraInput: HTMLInputElement,
		backupInput: HTMLInputElement,
		dbTimer: ReturnType<typeof setTimeout>,
		zoomTimer: ReturnType<typeof setTimeout>,
		renderToken = 0,
		lastTask: RenderTask | null = null,
		gesture: any = null,
		penId: number | null = null,
		touches = new Map<number, any>(),
		pinch: any = null;
	let history = $state<NotebookPage[][]>([]),
		future = $state<NotebookPage[][]>([]),
		revision = $state(0);
	let liveCanvas: HTMLCanvasElement,
		liveContext: CanvasRenderingContext2D | null,
		livePoints: InkPoint[] = [],
		liveStroke: NotebookItem | null = null;
	const pathCache = new WeakMap();
	function paintLive(a: InkPoint, b: InkPoint) {
		if (!liveContext || !liveStroke) return;
		liveContext.strokeStyle = liveStroke.color;
		liveContext.fillStyle = liveStroke.color;
		liveContext.lineWidth = liveStroke.width;
		liveContext.lineCap = 'round';
		liveContext.lineJoin = 'round';
		liveContext.globalAlpha = 1;
		liveCanvas.style.opacity = liveStroke.highlight ? '0.3' : '1';
		liveContext.beginPath();
		liveContext.moveTo(a.x, a.y);
		liveContext.lineTo(b.x, b.y);
		liveContext.stroke();
	}
	function resetLive() {
		if (liveContext) liveContext.clearRect(0, 0, liveCanvas.width, liveCanvas.height);
	}
	function inkCanvas(node: HTMLCanvasElement, _page?: string | number) {
		liveCanvas = node;
		const sync = () => {
			node.width = Math.ceil(page.w * 2);
			node.height = Math.ceil(page.h * 2);
			liveContext = node.getContext('2d');
			liveContext?.scale(2, 2);
		};
		sync();
		return { update: sync };
	}
	const page = $derived(pages[pageIndex] || pages[0]);
	const selectedIds = $derived(new Set(selected));
	const selectedItems = $derived(page.items.filter((o) => selectedIds.has(o.id))); 
	const selection = $derived(bounds(selectedItems));
	const uid = () => crypto.randomUUID();
	let ignoreTouchClickUntil = 0;
	let noticeTimer: ReturnType<typeof setTimeout>;
	function notice(s: string) {
		status = s;
		clearTimeout(noticeTimer);
		noticeTimer = setTimeout(() => (status = ''), 4500);
	}
	const snapshot = () => pages.map((p) => ({ ...p, items: p.items.slice() }));
	function checkpoint() {
		history = [...history.slice(-29), snapshot()];
		future = [];
	}
	function undo() {
		if (!history.length) return;
		future = [...future, snapshot()];
		pages = history.at(-1)!;
		revision++;
		history = history.slice(0, -1);
		selected = [];
		activeText = null;
	}
	function redo() {
		if (!future.length) return;
		history = [...history, snapshot()];
		pages = future.at(-1)!;
		revision++;
		future = future.slice(0, -1);
		selected = [];
		activeText = null;
	}
	function path(points: InkPoint[], width = 2.5, highlight = false) {
		if (!points?.length) return '';
		const cached = pathCache.get(points);
		if (cached) return cached;
		const shape = getStroke(
			points.map((p: InkPoint) => [p.x, p.y, p.p ?? 0.5]),
			{
				size: width,
				thinning: highlight ? 0 : 0.45,
				smoothing: 0.55,
				streamline: 0.08,
				simulatePressure: false,
				last: true
			}
		);
		const d = shape.length ? 'M' + shape.map((p) => p.join(',')).join('L') + 'Z' : '';
		pathCache.set(points, d);
		return d;
	}
	function position(e: PointerEvent) {
		const r = paperEl.getBoundingClientRect();
		return { x: (e.clientX - r.left) / zoom, y: (e.clientY - r.top) / zoom, p: e.pressure || 0.5 };
	}
	function setTool(t: string) {
		editing = true;
		if (t !== tool) {
			activeText = null;
			memoOpen = null;
			selected = [];
		}
		tool = t;
		imageMenu = false;
	}
	function removeSelected() {
		if (!selected.length) return;
		checkpoint();
		page.items = page.items.filter((o) => !selected.includes(o.id));
		revision++;
		selected = [];
		activeText = null;
		memoOpen = null;
	}
	function duplicate() {
		checkpoint();
		const copies = structuredClone($state.snapshot(selectedItems)).map((o: NotebookItem) =>
			o.kind === 'stroke'
				? {
						...o,
						id: uid(),
						points: o.points.map((p: InkPoint) => ({ ...p, x: p.x + 18, y: p.y + 18 }))
					}
				: { ...o, id: uid(), x: o.x + 18, y: o.y + 18 }
		);
		page.items.push(...copies);
		selected = copies.map((o) => o.id);
		revision++;
	}
	function selectAll() {
		selected = page.items.map((o) => o.id);
		activeText = null;
	}
	function objectClick(e: MouseEvent | KeyboardEvent, o: NotebookItem) {
		e.stopPropagation();
		if (Date.now() < ignoreTouchClickUntil) return;
		if (o.kind === 'image' && ['pen', 'highlight', 'lasso'].includes(tool)) return;
		if (e instanceof PointerEvent && e.pointerType === 'pen' && ['pen', 'highlight'].includes(tool))
			return;
		if (!editing) return;
		if (tool === 'eraser') {
			checkpoint();
			page.items = page.items.filter((i) => i.id !== o.id);
			return;
		}
		if (penId !== null) return;
		selected = [o.id];
		if (o.kind === 'text') {
			tool = 'text';
			activeText = o.id;
		} else if (o.kind === 'memo') {
			tool = 'memo';
			memoOpen = o.id;
			activeText = o.id;
		}
	}
	function addText(p: InkPoint, kind: string) {
		checkpoint();
		const o = {
			id: uid(),
			kind,
			x: Math.max(0, Math.min(page.w - 280, p.x)),
			y: Math.max(0, Math.min(page.h - 90, p.y)),
			w: 280,
			h: 60,
			html: '<p></p>'
		};
		page.items.push(o as NotebookItem);
		revision++;
		selected = [o.id];
		activeText = o.id;
		if (kind === 'memo') memoOpen = o.id;
	}
	function erase(p: InkPoint) {
		page.items = page.items.flatMap((o) => {
			if (o.kind !== 'stroke') return [o];
			const radius = eraseMode === 'stroke' ? Math.max(8, o.width) : 14;
			if (
				!o.points.some(
					(b: InkPoint, i: number) => segmentDistance(p, o.points[Math.max(0, i - 1)], b) < radius
				)
			)
				return [o];
			if (eraseMode === 'stroke') return [];
			let parts: NotebookItem[] = [],
				part: InkPoint[] = [];
			for (let i = 0; i < o.points.length; i++) {
				const a = o.points[Math.max(0, i - 1)],
					b = o.points[i],
					n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / 4));
				for (let j = i ? 1 : 0; j <= n; j++) {
					const q = {
						x: a.x + ((b.x - a.x) * j) / n,
						y: a.y + ((b.y - a.y) * j) / n,
						p: a.p ?? 0.5
					};
					if (Math.hypot(q.x - p.x, q.y - p.y) <= radius) {
						if (part.length > 1) parts.push({ ...o, id: uid(), points: part });
						part = [];
					} else part.push(q);
				}
			}
			if (part.length > 1) parts.push({ ...o, id: uid(), points: part });
			return parts;
		});
	}
	function penContextMenu(e: MouseEvent) {
		e.preventDefault();
	}

	function down(e: PointerEvent) {
		if (!ready) return;
		if (daily && tool === 'hand' && e.pointerType !== 'touch') {
			const r = paperEl.getBoundingClientRect();
			ondailytap?.((e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom);
		}
		if (gesture?.kind === 'transform') return;
		const pen = penInput.update(e);
		if (e.pointerType === 'pen')
			temporaryTool = editing ? (pen.override === 'lasso' ? barrelTool : pen.override) : null;
		if (e.pointerType === 'pen' && !pen.contact) {
			if (pen.override) e.preventDefault();
			return;
		}
		if (
			e.pointerType !== 'touch' &&
			!(editing && ['pen', 'highlight', 'eraser', 'lasso'].includes(tool) && (e.target as HTMLElement)?.closest?.('.image-object')) &&
			!(
				e.pointerType === 'pen' &&
				editing &&
				['pen', 'highlight', 'eraser'].includes(tool) &&
				!(e.target as HTMLElement)?.closest?.(
					'.selection-actions,.resize-handle,.text-width-handle,.memo-popup'
				)
			) &&
			(e.target as HTMLElement)?.closest?.(
				'.note-object,.selection-actions,.resize-handle,.memo-popup'
			)
		)
			return;
		if (e.pointerType === 'touch') {
			e.preventDefault();
			if (penId !== null) return;
			touches.set(e.pointerId, {
				x: e.clientX,
				y: e.clientY,
				startX: e.clientX,
				startY: e.clientY
			});
			paperEl.setPointerCapture(e.pointerId);
			if (touches.size === 2) {
				for (const point of touches.values()) point.pinched = true;
				const [a, b] = [...touches.values()];
				pinch = {
					distance: Math.hypot(a.x - b.x, a.y - b.y),
					zoom,
					cx: (a.x + b.x) / 2,
					cy: (a.y + b.y) / 2,
					left: viewport.scrollLeft,
					top: viewport.scrollTop
				};
			}
			return;
		}
		if (e.button !== 0 && e.pointerType !== 'pen') return;
		if (liveStroke || gesture) return;
		e.preventDefault();
		paperEl.setPointerCapture(e.pointerId);
		const t = !editing ? 'hand' : pen.override === 'lasso' ? barrelTool : (pen.override ?? tool);
		if (e.pointerType === 'pen') {
			penId = e.pointerId;
			touches.clear();
			pinch = null;
		}
		const p = position(e);
		gesture = {
			id: e.pointerId,
			tool: t,
			start: p,
			last: p,
			scroll: { x: viewport.scrollLeft, y: viewport.scrollTop },
			client: { x: e.clientX, y: e.clientY }
		};
		if (t === 'text' || t === 'memo') {
			if (selected.length || activeText) {
				selected = [];
				activeText = null;
				memoOpen = null;
			} else addText(p, t);
			gesture = null;
			return;
		}
		activeText = null;
		memoOpen = null;
		if (t === 'lasso') {
			selected = [];
			lasso = [p];
		}
		if (t === 'pen' || t === 'highlight') {
			checkpoint();
			selected = [];
			livePoints = [p];
			liveStroke = {
				id: uid(),
				kind: 'stroke',
				color,
				width: t === 'highlight' ? 18 : Number(size),
				highlight: t === 'highlight',
				uniform: true
			};
			resetLive();
			paintLive(p, { ...p, x: p.x + 0.01 });
		}
		if (t === 'eraser') {
			checkpoint();
			selected = [];
			erase(p);
		}
	}
	function moveTransform(e: PointerEvent) {
		e.preventDefault();
		const p = position(e);
		const dx = p.x - gesture.start.x,
			dy = p.y - gesture.start.y,
			b = gesture.bounds,
			[cx, cy] = gesture.corner || [100, 100],
			scale = gesture.resize
				? Math.max(
						0.1,
						Math.max((b.w + dx * (cx ? 1 : -1)) / b.w, (b.h + dy * (cy ? 1 : -1)) / b.h)
					)
				: 1,
			ax = b.x + (cx ? 0 : b.w),
			ay = b.y + (cy ? 0 : b.h);
		for (const original of gesture.original) {
			const at = gesture.indices.get(original.id);
			if (at === undefined) continue;
			const o = { ...page.items[at] };
			page.items[at] = o;
			if (o.kind === 'stroke') {
				o.width = original.width * scale;
				o.points = original.points.map((q: InkPoint) => ({
					...q,
					x: gesture.resize ? ax + (q.x - ax) * scale : q.x + dx,
					y: gesture.resize ? ay + (q.y - ay) * scale : q.y + dy
				}));
			} else {
				o.x = gesture.resize ? ax + (original.x - ax) * scale : original.x + dx;
				o.y = gesture.resize ? ay + (original.y - ay) * scale : original.y + dy;
				if (gesture.resize) {
					o.w = original.w * scale;
					o.h = original.h * scale;
					o.textScale = (original.textScale || 1) * scale;
				}
			}
		}
		return;
	}

	function move(e: PointerEvent) {
		if (gesture?.kind === 'transform' && gesture.id === e.pointerId) {
			moveTransform(e);
			return;
		}
		if (e.pointerType === 'pen') {
			const pen = penInput.update(e);
			temporaryTool = editing ? (pen.override === 'lasso' ? barrelTool : pen.override) : null;
			if (pen.override) e.preventDefault();
			if (!gesture && pen.contact) down(e);
			if (gesture?.id === e.pointerId) {
				// Chorded pen buttons change through pointermove, not another pointerdown.
				if (!pen.contact) {
					up(e);
					return;
				}
				const nextTool = !editing
					? 'hand'
					: pen.override === 'lasso'
						? barrelTool
						: (pen.override ?? tool);
				if (
					gesture.tool !== nextTool &&
					['pen', 'highlight', 'lasso', 'eraser', 'hand'].includes(gesture.tool)
				) {
					up(e);
					down(e);
				}
			}
		}

		if (touches.has(e.pointerId)) {
			e.preventDefault();
			const before = touches.get(e.pointerId);
			touches.set(e.pointerId, { ...before, x: e.clientX, y: e.clientY });
			if (pinch && touches.size === 2 && penId === null) {
				const [a, b] = [...touches.values()],
					next = Math.max(
						0.35,
						Math.min(3, (pinch.zoom * Math.hypot(a.x - b.x, a.y - b.y)) / pinch.distance)
					),
					r = viewport.getBoundingClientRect(),
					ratio = next / pinch.zoom;
				zoom = next;
				viewport.scrollLeft = (pinch.left + pinch.cx - r.left) * ratio - ((a.x + b.x) / 2 - r.left);
				viewport.scrollTop = (pinch.top + pinch.cy - r.top) * ratio - ((a.y + b.y) / 2 - r.top);
			} else if (touches.size === 1) {
				viewport.scrollLeft -= e.clientX - before.x;
				viewport.scrollTop -= e.clientY - before.y;
			}
			return;
		}
		if (!gesture || gesture.id !== e.pointerId) return;
		e.preventDefault();
		const p = position(e);

		if (gesture.tool === 'hand') {
			viewport.scrollLeft = gesture.scroll.x - e.clientX + gesture.client.x;
			viewport.scrollTop = gesture.scroll.y - e.clientY + gesture.client.y;
		}
		if (liveStroke) {
			const ev = [...(e.getCoalescedEvents?.() || []), e];
			for (const q of ev.length ? ev : [e]) {
				const p = position(q);
				const prev = livePoints.at(-1)!;
				if (Math.hypot(p.x - prev.x, p.y - prev.y) < 0.08) continue;
				paintLive(prev, p);
				livePoints.push(p);
			}
		}
		if (gesture.tool === 'lasso') lasso.push(p);
		if (gesture.tool === 'eraser') {
			const n = Math.max(1, Math.ceil(Math.hypot(p.x - gesture.last.x, p.y - gesture.last.y) / 6));
			for (let i = 1; i <= n; i++)
				erase({
					x: gesture.last.x + ((p.x - gesture.last.x) * i) / n,
					y: gesture.last.y + ((p.y - gesture.last.y) * i) / n
				});
		}
		gesture.last = p;
	}
	function up(e: PointerEvent) {
		if (e.type === 'pointerup' || e.type === 'pointercancel') {
			const pen = penInput.update(e);
			if (e.pointerType === 'pen')
				temporaryTool =
					e.type === 'pointercancel' ? null : pen.override === 'lasso' ? barrelTool : pen.override;
		}
		const touch = touches.get(e.pointerId);
		if (touch && Math.hypot(e.clientX - touch.startX, e.clientY - touch.startY) > 6)
			ignoreTouchClickUntil = Date.now() + 400;
		if (
			daily &&
			touch &&
			touches.size === 1 &&
			!touch.pinched &&
			tool === 'hand' &&
			e.type === 'pointerup' &&
			Math.hypot(e.clientX - touch.startX, e.clientY - touch.startY) < 6
		) {
			const r = paperEl.getBoundingClientRect();
			ondailytap?.((e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom);
		}
		if (touch && touches.size === 1) {
			const direction = horizontalPageSwipe(
				pageMode,
				{ x: touch.startX, y: touch.startY },
				{ x: e.clientX, y: e.clientY },
				Boolean(pinch) || touch.pinched
			);
			const next = adjacentPage(pageIndex, direction, twoPage);
			if (direction && next >= 0 && next < pages.length) jump(next);
		}
		touches.delete(e.pointerId);
		if (touches.size < 2) pinch = null;
		if (penId === e.pointerId) penId = null;
		if (!gesture || gesture.id !== e.pointerId) return;
		if (liveStroke) {
			if (e.type === 'pointerup') {
				const p = position(e);
				if (
					Number.isFinite(p.x) &&
					Number.isFinite(p.y) &&
					p.x >= 0 &&
					p.y >= 0 &&
					p.x <= page.w &&
					p.y <= page.h &&
					!(e.clientX === 0 && e.clientY === 0)
				)
					livePoints.push(p);
			}
			page.items.push({ ...liveStroke, points: livePoints });
			liveStroke = null;
			livePoints = [];
			revision++;
			/* Clear only if another contact has not started after this commit. */ tick().then(() => {
				if (!liveStroke) resetLive();
			});
		}
		if (gesture.tool === 'lasso' && lasso.length > 2) {
			const matchesLasso = createLassoSelector(lasso, lassoMode);
			selected = page.items
				.filter((o) =>
					matchesLasso(
						o.kind === 'stroke'
							? o.points
							: [
									{ x: o.x, y: o.y },
									{ x: o.x + o.w, y: o.y },
									{ x: o.x + o.w, y: o.y + o.h },
									{ x: o.x, y: o.y + o.h },
									{ x: o.x, y: o.y }
								]
					)
				)
				.map((o) => o.id);
		}
		lasso = [];
		const restoreText = gesture.restoreText;
		gesture = null;
		if (restoreText) activeText = restoreText;
		revision++;
	}
	function moveText(e: PointerEvent, o: NotebookItem) {
		selected = [o.id];
		transform(e);
		if (gesture) gesture.restoreText = o.id;
	}
	function resizeText(e: PointerEvent, o: NotebookItem) {
		e.preventDefault();
		e.stopPropagation();
		checkpoint();
		const start = e.clientX,
			w = o.w;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
		const move = (ev: PointerEvent) => {
			const at = page.items.findIndex((i) => i.id === o.id);
			if (at >= 0)
				page.items[at] = {
					...page.items[at],
					w: Math.max(80, Math.min(page.w - o.x, w + (ev.clientX - start) / zoom))
				};
		};
		const end = () => {
			window.removeEventListener('pointermove', move);
			revision++;
		};
		window.addEventListener('pointermove', move);
		window.addEventListener('pointerup', end, { once: true });
	}
	function transform(e: PointerEvent, resize = false, corner = [100, 100]) {
		if (!selection) return;
		e.preventDefault();
		e.stopPropagation();
		touches.delete(e.pointerId);
		pinch = null;
		checkpoint();
		activeText = null;
		if (e.pointerType === 'pen') penId = e.pointerId;
		paperEl.setPointerCapture(e.pointerId);
		gesture = {
			id: e.pointerId,
			kind: 'transform',
			start: position(e),
			bounds: { ...selection },
			original: structuredClone($state.snapshot(selectedItems)),
			indices: new Map(page.items.map((item, index) => [item.id, index])),
			resize,
			corner
		};
	}
	async function renderPdf() {
		const token = ++renderToken,
			doc = pdf,
			idx = pageIndex;
		if (!canvasHost) return;
		lastTask?.cancel();
		if (!doc || pages[idx].source === null) {
			canvasHost.replaceChildren();
			return;
		}
		pageBusy = true;
		try {
			const p = await doc.getPage((pages[idx].source ?? idx) + 1);
			if (token !== renderToken) return;
			const native = p.getViewport({ scale: 1, rotation: pages[idx].rotation ?? p.rotate });
			if (pages[idx].w !== native.width || pages[idx].h !== native.height) {
				pages[idx].w = native.width;
				pages[idx].h = native.height;
			}
			const v = p.getViewport({
					scale: Math.min(2.5, Math.max(1.3, zoom * devicePixelRatio)),
					rotation: pages[idx].rotation ?? p.rotate
				}),
				c = document.createElement('canvas');
			c.width = Math.ceil(v.width);
			c.height = Math.ceil(v.height);
			const task = p.render({ canvas: c, viewport: v });
			lastTask = task;
			await task.promise;
			if (token === renderToken) canvasHost.replaceChildren(c);
		} catch (e) {
			if ((e as Error).name !== 'RenderingCancelledException')
				notice('PDF 표시 실패 · 다른 페이지를 열어 보세요.');
		} finally {
			if (token === renderToken) pageBusy = false;
		}
	}
	$effect(() => {
		pdf;
		pageIndex;
		canvasHost;
		untrack(renderPdf);
	});
	$effect(() => {
		zoom;
		clearTimeout(zoomTimer);
		zoomTimer = setTimeout(() => untrack(renderPdf), 240);
	});
	function fit() {
		if (viewport) {
			const style = getComputedStyle(viewport);
			const available =
				viewport.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 4;
			const indices = visiblePageIndices('vertical', pageIndex, pages.length, twoPage);
			const width = twoPage ? indices.reduce((sum, i) => sum + pages[i].w, 0) : page.w;
			zoom = Math.min(1.1, Math.max(0.1, (available - (twoPage ? 16 : 0)) / width));
			viewport.scrollTop = 0;
		}
	}
	function paperInk() {
		if (paperFor(page).color === 'black' && color === '#242529') color = '#eeeeee';
		else if (paperFor(page).color !== 'black' && color === '#eeeeee') color = '#242529';
	}
	function jump(n: number) {
		const next = Math.max(0, Math.min(pages.length - 1, n));
		if (next === pageIndex) return;
		pageIndex = next;
		paperInk();
		activeText = null;
		selected = [];
		memoOpen = null;
		tick().then(() => pageScroll(pageIndex));
	}
	async function openPdf(file?: File) {
		if (!file) return;
		try {
			if (pdf || pages.some((p) => p.items.length)) await backup();
			const bytes = await file.arrayBuffer(),
				doc = await pdfjs.getDocument({ ...pdfOptions(), data: bytes.slice(0) }).promise;
			const first = await doc.getPage(1),
				v = first.getViewport({ scale: 1 }),
				dims = Array.from({ length: doc.numPages }, () => ({ w: v.width, h: v.height, items: [] }));
			pdf?.loadingTask.destroy();
			pdf = doc;
			pdfBytes = bytes;
			pdfName = file.name;
			title = file.name.replace(/\.pdf$/i, '');
			pages = dims;
			pageIndex = 0;
			activeText = null;
			selected = [];
			history = [];
			future = [];
			fit();
			notice('PDF를 열었습니다');
		} catch {
			notice('PDF를 열지 못했습니다. 파일 손상 또는 암호를 확인하세요.');
		}
	}
	function newPage(template: PaperTemplate = paperDefaults) {
		checkpoint();
		pages.push(freshPage(template));
		if (template.color === 'black' && color === '#242529') color = '#eeeeee';
		if (template.color !== 'black' && color === '#eeeeee') color = '#242529';
		pageIndex = pages.length - 1;
		selected = [];
		activeText = null;
	}
	async function blankNotebook() {
		if (pdf || pages.some((p) => p.items.length)) await backup();
		pdf?.loadingTask.destroy();
		pdf = null;
		pdfBytes = null;
		pdfName = '';
		pdfSourceUrl = '';
		pages = [freshPage()];
		title = '제목 없는 노트';
		pageIndex = 0;
		history = [];
		future = [];
		selected = [];
		activeText = null;
	}
	async function insertImage(file?: File) {
		if (!file) return;
		imageMenu = false;
		try {
			const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' }),
				ratio = Math.min(1, 2200 / Math.max(bitmap.width, bitmap.height)),
				c = document.createElement('canvas');
			c.width = Math.round(bitmap.width * ratio);
			c.height = Math.round(bitmap.height * ratio);
			c.getContext('2d')!.drawImage(bitmap, 0, 0, c.width, c.height);
			bitmap.close();
			let src = c.toDataURL('image/png');
			if (remote) {
				const blob = await new Promise<Blob>((resolve, reject) =>
					c.toBlob((b) => (b ? resolve(b) : reject(Error('image conversion'))), 'image/png')
				);
				const asset = await uploadResource(new File([blob], file.name, { type: 'image/png' }));
				src = asset.url;
			}
			const w = Math.min(page.w * 0.55, c.width, (page.h * 0.65 * c.width) / c.height),
				h = (w * c.height) / c.width;
			checkpoint();
			const o = {
				id: uid(),
				kind: 'image',
				x: (page.w - w) / 2,
				y: Math.max(24, Math.min(page.h - h - 24, (viewport.scrollTop + 140) / zoom)),
				w,
				h,
				src
			};
			page.items.push(o as NotebookItem);
			revision++;
			selected = [o.id];
			activeText = null;
			tool = 'lasso';
			notice('이미지를 추가했습니다');
		} catch {
			notice('이미지를 읽지 못했습니다. PNG 또는 JPG를 선택해 주세요.');
		}
	}
	function paste(e: ClipboardEvent) {
		if (
			(e.target as HTMLElement)?.closest?.('.tiptap,input,textarea,select,[contenteditable=true]')
		)
			return;
		const f = [...(e.clipboardData?.items || [])]
			.find((i) => i.type.startsWith('image/'))
			?.getAsFile();
		if (f) {
			e.preventDefault();
			insertImage(f);
		}
	}
	function keydown(e: KeyboardEvent) {
		if (document.querySelector('.notebook-popover:popover-open')) return;
		if (
			(e.target as HTMLElement)?.closest?.('.tiptap,input,textarea,select,[contenteditable=true]')
		)
			return;
		const mod = e.ctrlKey || e.metaKey;
		if (!mod && !e.altKey && ['ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown'].includes(e.key)) {
			if (!ready || gesture || penId !== null) return;
			e.preventDefault();
			const next = adjacentPage(
				pageIndex,
				['ArrowLeft', 'PageUp'].includes(e.key) ? -1 : 1,
				twoPage
			);
			if (next >= 0 && next < pages.length) jump(next);
			return;
		}

		if (mod && e.key.toLowerCase() === 'a') {
			e.preventDefault();
			selectAll();
		} else if (mod && e.key.toLowerCase() === 'z') {
			e.preventDefault();
			e.shiftKey ? redo() : undo();
		} else if (e.key === 'Delete' || e.key === 'Backspace') {
			e.preventDefault();
			removeSelected();
		} else if (e.key === 'Escape') {
			selected = [];
			activeText = null;
			memoOpen = null;
			imageMenu = false;
		} else if (!mod) {
			const t = (
				{ p: 'pen', e: 'eraser', l: 'lasso', t: 'text', h: 'hand' } as Record<string, string>
			)[e.key];
			if (t) setTool(t);
		}
	}
	export async function flush() {
		await loadingDocument;
		return persist();
	}
	async function persist() {
		if (!ready) return false;
		if (penId !== null || liveStroke) {
			dbTimer = setTimeout(persist, 250);
			return;
		}
		clearTimeout(dbTimer);
		try {
			await storage.save({
				title,
				pages: $state.snapshot(pages),
				pdf: pdfBytes,
				pdfName,
				pdfUrl: pdfSourceUrl,
				pageIndex
			});
			quotaFailed = false;
			saveState = remote ? '서버에 저장됨' : '이 기기에 저장됨';
			ontitlechange?.(title);
			return true;
		} catch (error) {
			quotaFailed =
				Boolean(error && typeof error === 'object' && 'status' in error && error.status === 413) ||
				(error instanceof Error && error.message.includes('저장 공간'));
			saveState = quotaFailed ? '저장 공간 부족 · 백업 필요' : '저장 실패 · 백업을 내려받으세요';
			if (quotaFailed)
				notice(
					'저장 공간이 부족합니다. 현재 필기는 보존했습니다. 드라이브에서 용량을 확인해 주세요.'
				);
			return false;
		}
	}
	$effect(() => {
		revision;
		title;
		pageIndex;
		pages.length;
		if (ready) {
			saveState = '저장 중';
			clearTimeout(dbTimer);
			dbTimer = setTimeout(persist, 650);
		}
	});
	function download(blob: Blob, name: string) {
		const u = URL.createObjectURL(blob),
			a = document.createElement('a');
		a.href = u;
		a.download = name;
		a.click();
		setTimeout(() => URL.revokeObjectURL(u), 1000);
	}
	async function backup() {
		await persist();
		if (!pdfBytes && pdfSourceUrl) {
			try {
				const response = await fetch(pdfSourceUrl, { credentials: 'include' });
				if (!response.ok) throw Error();
				pdfBytes = await response.arrayBuffer();
			} catch {
				notice('원본 PDF를 내려받지 못해 백업을 중단했습니다');
				return;
			}
		}
		download(
			new Blob(
				[
					JSON.stringify({
						format: 'netaq-notes-v1',
						title,
						pages: $state.snapshot(pages),
						pdf: pdfBytes ? Array.from(new Uint8Array(pdfBytes)) : null,
						pdfName
					})
				],
				{ type: 'application/json' }
			),
			title + '.netaq'
		);
		notice('노트 백업을 내려받았습니다');
	}
	function safeHtml(html: string) {
		const doc = new DOMParser().parseFromString(String(html), 'text/html');
		for (const el of doc.body.querySelectorAll('*')) {
			if (
				[
					'SCRIPT',
					'IFRAME',
					'OBJECT',
					'EMBED',
					'STYLE',
					'LINK',
					'META',
					'SVG',
					'MATH',
					'FORM'
				].includes(el.tagName)
			) {
				el.remove();
				continue;
			}
			for (const a of [...el.attributes])
				if (
					a.name.startsWith('on') ||
					['srcdoc', 'formaction'].includes(a.name) ||
					(['href', 'src'].includes(a.name) &&
						!/^(https?:|data:image\/(png|jpeg|webp|gif);|mailto:)/i.test(a.value))
				)
					el.removeAttribute(a.name);
		}
		return doc.body.innerHTML;
	}
	async function restore(file?: File) {
		if (!file) return;
		try {
			const d = JSON.parse(await file.text());
			if (d.format !== 'netaq-notes-v1' || !Array.isArray(d.pages) || !d.pages.length)
				throw Error();
			for (const p of d.pages) {
				if (!(p.w > 0 && p.h > 0) || !Array.isArray(p.items)) throw Error();
				for (const o of p.items) {
					if (o.html) o.html = safeHtml(o.html);
					if (o.kind === 'image' && !/^data:image\/(png|jpeg|webp|gif);/i.test(o.src))
						throw Error();
				}
			}
			const bytes = d.pdf ? new Uint8Array(d.pdf).buffer : null,
				doc = bytes
					? await pdfjs.getDocument({ ...pdfOptions(), data: bytes.slice(0) }).promise
					: null;
			if (pdf || pages.some((p) => p.items.length)) await backup();
			pdf?.loadingTask.destroy();
			pdf = doc;
			pdfBytes = bytes;
			pdfName = d.pdfName || '';
			pages = d.pages;
			title = d.title || '복원한 노트';
			pageIndex = 0;
			selected = [];
			activeText = null;
			history = [];
			future = [];
			notice('노트를 복원했습니다');
		} catch {
			notice('백업을 읽지 못했습니다. .netaq 파일을 확인하세요.');
		}
	}
	function textChanged(id: string, html: string) {
		const at = page.items.findIndex((i) => i.id === id);
		if (at >= 0) {
			page.items[at] = { ...page.items[at], html };
			revision++;
		}
	}
	let loadingDocument: Promise<void> = Promise.resolve();
	onMount(() => {
		androidPen = usesAndroidPen(navigator);
		barrelTool = androidPen ? 'eraser' : 'lasso';
		try {
			if (!androidPen) barrelTool = localStorage.getItem('netaq-barrel-tool') || barrelTool;
			const saved = JSON.parse(localStorage.getItem('netaq-pen-presets') || 'null');
			if (
				Array.isArray(saved) &&
				saved.length &&
				saved.every(
					(p: { color: string; width: number }) =>
						/^#[0-9a-f]{6}$/i.test(p.color) && p.width > 0 && p.width <= 10
				)
			)
				presets = saved;
		} catch {}
		let alive = true;
		loadingDocument = (async () => {
			try {
				const d = await storage.read(url || '');
				if (d && alive) {
					title = d.title || name || '제목 없는 노트';
					pages = d.pages;
					pdfBytes = d.pdf;
					pdfName = d.pdfName || '';
					pageIndex = d.pageIndex || 0;
					pdfSourceUrl = d.pdfUrl || '';
					if (pdfSourceUrl)
						pdf = await pdfjs.getDocument({
							...pdfOptions(),
							url: pdfSourceUrl,
							withCredentials: true
						}).promise;
					else if (url)
						pdf = await pdfjs.getDocument({ ...pdfOptions(), url, withCredentials: true }).promise;
					else if (pdfBytes)
						pdf = await pdfjs.getDocument({ ...pdfOptions(), data: pdfBytes.slice(0) }).promise;
				}
			} catch {
				saveState = '불러오기 실패 · 새로고침 필요';
				notice('노트 불러오기 실패 · 기존 저장본을 보존했습니다. 새로고침해 주세요.');
				return;
			}
			if (alive) {
				if (name && !title) title = name;
				ready = true;
				paperInk();
				await tick();
				fit();
			}
		})();
		const wheel = (e: WheelEvent) => {
			if (penId !== null || (gesture && gesture.tool !== 'hand')) e.preventDefault();
			else if (e.ctrlKey) {
				e.preventDefault();
				zoom = Math.max(0.35, Math.min(3, zoom * (e.deltaY > 0 ? 0.95 : 1.05)));
			}
		};
		viewport.addEventListener('wheel', wheel, { passive: false });
		return () => {
			alive = false;
			clearTimeout(dbTimer);
			clearTimeout(zoomTimer);
			viewport?.removeEventListener('wheel', wheel);
			pdf?.loadingTask.destroy();
		};
	});
</script>

<svelte:window
	onblur={() => {
		penInput.reset();
		temporaryTool = null;
	}}
	onpaste={paste}
	onkeydown={keydown}
	onpointerup={up}
	onpointercancel={up}
/>
<input
	hidden
	class="hidden"
	type="file"
	accept="application/pdf"
	bind:this={pdfInput}
	onchange={(e) => {
		openPdf(e.currentTarget.files?.[0]);
		e.currentTarget.value = '';
	}}
/>
<input
	hidden
	class="hidden"
	type="file"
	accept="image/*"
	bind:this={imageInput}
	onchange={(e) => {
		insertImage(e.currentTarget.files?.[0]);
		e.currentTarget.value = '';
	}}
/>
<input
	hidden
	class="hidden"
	type="file"
	accept="image/*"
	capture="environment"
	bind:this={cameraInput}
	onchange={(e) => {
		insertImage(e.currentTarget.files?.[0]);
		e.currentTarget.value = '';
	}}
/>
<input
	hidden
	class="hidden"
	type="file"
	accept=".netaq,application/json"
	bind:this={backupInput}
	onchange={(e) => {
		restore(e.currentTarget.files?.[0]);
		e.currentTarget.value = '';
	}}
/>
<div
	class="app netaq-notebook"
	class:daily-notebook={daily}
	use:readerSize
	class:embedded={Boolean(drive)}
	class:margin-workspace={Boolean(drive)}
	class:focus-mode={focusMode}
	class:reading={!editing}
	class:library-workspace={libraryMode}
	data-notebook-version="2"
	data-notebook-build={import.meta.env.VITE_NOTEBOOK_BUILD_ID || 'dev'}
>
	{#if !daily}<header class="app-header">
			<button
				class="home-button"
				aria-label={libraryMode ? '노트 목록' : 'NETAQ 홈으로'}
				onclick={goHome}>{@html icon(libraryMode ? 'pages' : 'home')}</button
			>{#if drive}<button class="back-list" onclick={goBack}>← 목록</button>{:else}<div
					class="brand"
				>
					NETAQ<span>Notes</span>
				</div>{/if}
			<span class="header-divider"></span><input
				class="doc-title"
				aria-label="노트 제목"
				bind:value={title}
				readonly={Boolean(drive)}
				disabled={!ready}
			/><span class="save-state">{saveState}</span>{#if quotaFailed}<a
					class="storage-link"
					href="/personal-project/calendar/drive"
					target="_blank"
					rel="noopener">드라이브 용량 확인 ↗</a
				>{/if}{#if !drive}<button onclick={() => pdfInput.click()}
					>{@html icon('open')}<span>PDF 열기</span></button
				><button class="backup" onclick={backup} title="PDF와 필기를 포함한 노트 백업"
					>{@html icon('download')}<span>백업</span></button
				>
				<details class="file-menu">
					<summary aria-label="파일 메뉴">⋯</summary>
					<div class="file-options">
						<button onclick={() => backupInput.click()}>백업 파일 열기</button><button
							onclick={blankNotebook}>새 노트</button
						>
					</div>
				</details>{/if}
		</header>{/if}
	{#if drive}<div class="viewer-actions">
			<button onclick={() => (focusMode = !focusMode)}
				>{focusMode ? '분할 보기' : '크게 보기'}</button
			><button
				class:active={editing}
				onclick={() => {
					editing = !editing;
					tool = editing ? 'pen' : 'hand';
					activeText = null;
					selected = [];
				}}>{editing ? '보기' : '필기'}</button
			>
		</div>{/if}
	{#if daily}<div class="daily-save-state" role="status">{saveState}</div>{/if}
	<nav class="main-tools" aria-label="필기 도구">
		<button
			class:active={rail}
			onclick={() => (rail = !rail)}
			aria-label="PDF 페이지 보기"
			aria-pressed={rail}>{@html icon('pages')}</button
		><i></i>{#each editing ? tools : [['hand', '이동']] as [key, label] (key)}<button
				class:active={(temporaryTool || tool) === key}
				aria-pressed={tool === key}
				onclick={(e) => {
					setTool(key);
					toolName(label, e);
				}}
				aria-label={label}
				title={label}>{@html icon(key)}</button
			>{/each}
		{#if editing}<div class="image-anchor">
				<button
					bind:this={imageButton}
					aria-label="이미지 추가"
					class:active={imageMenu}
					onclick={() => (imageMenu = !imageMenu)}
					aria-expanded={imageMenu}>{@html icon('image')}</button
				><AnchoredPopover anchor={imageButton} open={imageMenu} onclose={() => (imageMenu = false)}
					><div class="image-menu">
						<button
							onclick={() => {
								imageMenu = false;
								imageInput.click();
							}}>{@html icon('image')}사진·파일 선택</button
						><button
							onclick={() => {
								imageMenu = false;
								cameraInput.click();
							}}>{@html icon('camera')}카메라로 촬영</button
						>
						<div>이미지 붙여넣기 <kbd>Ctrl V</kbd></div>
					</div></AnchoredPopover
				>
			</div>{/if}
		<div class="navigation-anchor">
			<button
				bind:this={navigationButton}
				aria-label="페이지 넘김 방식"
				onclick={() => (navigationOpen = !navigationOpen)}
				>{pageMode === 'continuous' ? '연속 스크롤' : '넘기기'} ▾</button
			><AnchoredPopover
				anchor={navigationButton}
				open={navigationOpen}
				onclose={() => (navigationOpen = false)}
				width={220}
				><div class="navigation-menu">
					{#each [['paged', '넘기기'], ['continuous', '연속 스크롤']] as [key, label] (key)}<button
							class:active={pageMode === key}
							onclick={() => changeMode(key)}>{label}</button
						>{/each}
				</div></AnchoredPopover
			>
		</div>
		<button
			class="two-page-toggle"
			class:active={twoPage}
			aria-label="두 쪽 보기"
			aria-pressed={twoPage}
			title="두 쪽 보기"
			onclick={toggleTwoPage}>{@html icon('spread')}</button
		>
		<i></i><button aria-label="실행 취소" disabled={!history.length} onclick={undo}
			>{@html icon('undo')}</button
		><button aria-label="다시 실행" disabled={!future.length} onclick={redo}
			>{@html icon('redo')}</button
		>
	</nav>
	{#if toolTip}<div
			class="tool-name-toast"
			style:left={toolTipX + 'px'}
			style:top={toolTipY + 'px'}
			role="status"
		>
			{toolTip}
		</div>{/if}
	{#if daily}<button
			class="daily-settings-toggle"
			onclick={() => (dailySettings = !dailySettings)}
			aria-expanded={dailySettings}>도구 설정</button
		>{/if}
	{#if editing && (!daily || dailySettings)}<section
			class="tool-settings"
			aria-label="선택한 도구 설정"
		>
			{#if tool === 'text' || tool === 'memo'}<div
					class="shared-editor"
					bind:this={textToolbarHost}
				></div>
				{#if !activeText}<div class="editor-parking">
						<PersonalTextEditor
							transparent
							compact
							localAttachments={!remote}
							toolbarTarget={textToolbarHost}
						/>
					</div>{/if}{:else if tool === 'lasso'}<div class="segmented">
					<button class:chosen={lassoMode === 'touch'} onclick={() => (lassoMode = 'touch')}
						>일부가 닿으면 선택</button
					><button class:chosen={lassoMode === 'inside'} onclick={() => (lassoMode = 'inside')}
						>전체가 들어와야 선택</button
					>
				</div>
				<span class="setting-divider"></span><button onclick={selectAll}>페이지 전체 선택</button
				>{:else if tool === 'eraser'}<div class="segmented">
					<button class:chosen={eraseMode === 'stroke'} onclick={() => (eraseMode = 'stroke')}
						>획 지우개</button
					><button class:chosen={eraseMode === 'part'} onclick={() => (eraseMode = 'part')}
						>부분 지우개</button
					>
				</div>{:else if tool === 'hand'}<span class="setting-hint"
					>드래그로 이동 · 두 손가락으로 확대·축소</span
				>{:else}<div class="preset-strip">
					{#each presets as preset, i (i)}<div class="preset-anchor">
							<button
								class:active={tool === 'pen' && presetIndex === i}
								aria-label={'펜 프리셋 ' + (i + 1)}
								style:color={preset.color}
								onclick={(e) => {
									presetButton = e.currentTarget;
									choosePreset(i);
								}}>{@html icon('pen')}<span>{(preset.width / 2.83465).toFixed(1)} mm</span></button
							>{#if presetOpen && presetIndex === i}<AnchoredPopover
									anchor={presetButton}
									open={presetOpen}
									onclose={() => (presetOpen = false)}
									width={300}
									><div class="preset-popover">
										<div class="preset-heading">
											펜 설정<button onclick={() => (presetOpen = false)} aria-label="펜 설정 닫기"
												>×</button
											>
										</div>
										<PersonalColorPicker
											kind="text"
											value={preset.color}
											onselect={(c) => updatePreset(c, preset.width)}
											onclose={() => (presetOpen = false)}
										/><label
											>굵기<input
												type="range"
												min=".5"
												max="10"
												step=".1"
												value={preset.width}
												oninput={(e) => updatePreset(preset.color, e.currentTarget.value)}
											/></label
										>
									</div></AnchoredPopover
								>{/if}
						</div>{/each}<button
						aria-label="펜 프리셋 추가"
						onclick={(e) => {
							presetButton = e.currentTarget;
							presets.push({ color, width: Number(size) });
							presetIndex = presets.length - 1;
							presetOpen = true;
						}}>＋</button
					>
				</div>{/if}{#if activeText}<button
					class="delete-text"
					onclick={removeSelected}
					aria-label="텍스트 또는 메모 삭제">{@html icon('trash')}</button
				>{/if}
			{#if !['text', 'memo'].includes(tool)}{#if !androidPen}<label class="barrel-setting"
						>펜 버튼<select
							aria-label="펜 버튼 도구"
							bind:value={barrelTool}
							onchange={() => localStorage.setItem('netaq-barrel-tool', barrelTool)}
							><option value="eraser">지우개</option><option value="lasso">올가미</option></select
						></label
					>{:else}<span class="setting-hint">펜 버튼 · 누르는 동안 지우개</span>{/if}<button
					class="pen-diagnostic-button"
					onclick={() => (penDiagnostics = !penDiagnostics)}>펜 입력 확인</button
				>{/if}
		</section>{/if}
	{#if penDiagnostics}<PenDiagnostics onclose={() => (penDiagnostics = false)} />{/if}
	<div class="workspace">
		{#if rail}<aside
				class="page-rail"
				style:width={railWidth + 'px'}
				style:--thumb-min={thumbSize + 'px'}
			>
				<button class="rail-resizer" aria-label="페이지 목록 폭 조절" onpointerdown={resizeRail}
				></button>
				<div class="rail-title">페이지 <span>{pages.length}</span></div>
				<label class="thumb-size"
					>크기<input
						aria-label="페이지 미리보기 크기"
						type="range"
						min="50"
						max="130"
						bind:value={thumbSize}
					/></label
				>
				<div class="thumb-list">
					{#each pages as p, i (i)}<button
							class="page-thumb"
							class:current={pageIndex === i}
							onclick={() => jump(i)}
							aria-label={i + 1 + ' 페이지'}
							aria-current={pageIndex === i ? 'page' : undefined}
							><div
								class="thumb-paper"
								style:background={paperColors[paperFor(p).color]}
								style:aspect-ratio={p.w + '/' + p.h}
							>
								{#if pdf && p.source !== null}<Thumb
										document={pdf}
										pageNumber={(p.source ?? i) + 1}
									/>{:else if paperFor(p).pattern === 'ruled'}<div
										class="thumb-rules"
									></div>{/if}<svg viewBox={'0 0 ' + p.w + ' ' + p.h} aria-hidden="true"
									>{#each p.items.filter((o) => o.kind === 'stroke') as stroke (stroke.id)}<path
											d={stroke.geometry === 'outline'
												? centerline(stroke.points) + 'Z'
												: stroke.uniform
													? centerline(stroke.points)
													: path(stroke.points, stroke.width, stroke.highlight)}
											stroke={stroke.uniform ? stroke.color : undefined}
											stroke-width={stroke.width}
											stroke-linecap="round"
											stroke-linejoin="round"
											fill={stroke.uniform ? 'none' : stroke.color}
											opacity={stroke.highlight ? 0.3 : 1}
										/>{/each}</svg
								>{#each p.items.filter((o) => o.kind !== 'stroke') as o (o.id)}<span
										class="thumb-mark"
										style:left={(o.x / p.w) * 100 + '%'}
										style:top={(o.y / p.h) * 100 + '%'}
										>{o.kind === 'image' ? '▧' : o.kind === 'memo' ? '▤' : 'T'}</span
									>{/each}
							</div>
							<span>{i + 1}</span></button
						>{/each}
				</div>
				<div class="add-page-actions">
					<button class="add-page" onclick={() => newPage()}>{@html icon('plus')}페이지 추가</button
					><button
						bind:this={paperButton}
						aria-label="페이지 추가 옵션"
						onclick={() => (paperMenu = !paperMenu)}>▾</button
					>
				</div>
				<AnchoredPopover
					anchor={paperButton}
					open={paperMenu}
					onclose={() => (paperMenu = false)}
					width={310}
					><PaperOptions
						initial={paperDefaults}
						onapply={(template, remember) => {
							if (remember) {
								paperDefaults = template;
								savePaperDefault(template);
								onpaperdefaultchange?.(template);
							}
							newPage(template);
							paperMenu = false;
						}}
					/></AnchoredPopover
				>
			</aside>{/if}
		<main
			class="viewport"
			class:spread={twoPage}
			bind:this={viewport}
			aria-label="노트 작업 영역"
			onpointermove={(e) => {
				if (e.pointerType === 'pen' && !(e.target as Element).closest('.paper')) {
					const pen = penInput.update(e);
					temporaryTool = editing ? (pen.override === 'lasso' ? barrelTool : pen.override) : null;
				}
			}}
			onpointerleave={(e) => {
				if (e.pointerType === 'pen' && penId === null) {
					penInput.reset();
					temporaryTool = null;
				}
			}}
			oncontextmenu={penContextMenu}
		>
			{#each visiblePageRows(pageMode, pageIndex, pages.length, twoPage) as row (row[0])}<div
					class="page-row"
				>
					{#each row.map((i) => ({ p: pages[i], i })) as slot (slot.i)}<div
							class="page-slot"
							data-page-slot={slot.i}
						>
							{#if slot.i === pageIndex}<div
									class="paper-stage"
									style:width={page.w * zoom + 'px'}
									style:height={page.h * zoom + 'px'}
								>
									<div
										class="paper"
										style:--paper-background={paperColors[paperFor(page).color]}
										style:--paper-foreground={paperFor(page).color === 'black'
											? '#eeeeee'
											: '#242529'}
										class:hand={tool === 'hand'}
										bind:this={paperEl}
										style:width={page.w + 'px'}
										style:height={page.h + 'px'}
										style:transform={'scale(' + zoom + ')'}
										onpointerdown={down}
										onpointermove={move}
										onpointerup={up}
										onpointercancel={up}
										onlostpointercapture={up}
										role="application"
										aria-label="필기 페이지"
									>
										{#if background}<div class="daily-background">{@render background()}</div>{/if}
										<canvas class="live-ink" use:inkCanvas={page.id || pageIndex}></canvas>
										<div class="pdf-layer" bind:this={canvasHost}></div>
										{#if (!pdf || page.source === null) && paperFor(page).pattern === 'ruled'}<div
												class="ruled-paper"
											></div>{/if}<svg
											class="ink-layer"
											viewBox={'0 0 ' + page.w + ' ' + page.h}
											aria-hidden="true"
											>{#each page.items.filter((o) => o.kind === 'stroke') as stroke (stroke.id)}<path
													d={stroke.geometry === 'outline'
														? centerline(stroke.points) + 'Z'
														: stroke.uniform
															? centerline(stroke.points)
															: path(stroke.points, stroke.width, stroke.highlight)}
													stroke={stroke.uniform ? stroke.color : undefined}
													stroke-width={stroke.width}
													stroke-linecap="round"
													stroke-linejoin="round"
													fill={stroke.uniform ? 'none' : stroke.color}
													opacity={stroke.highlight ? 0.3 : 1}
												/>{/each}{#if draft}<path
													d={path(draft.points, draft.width, draft.highlight)}
													fill={draft.color}
													opacity={draft.highlight ? 0.3 : 1}
												/>{/if}{#if lasso.length > 1}<path
													d={'M' + lasso.map((p) => p.x + ',' + p.y).join('L') + 'Z'}
													fill="#24252908"
													stroke="#696b73"
													stroke-width={1 / zoom}
													stroke-dasharray={5 / zoom}
												/>{/if}</svg
										>
										{#each page.items.filter((o) => o.kind !== 'stroke') as o (o.id)}{#if o.kind === 'image'}<button
													class="note-object image-object"
													style:left={o.x + 'px'}
													style:top={o.y + 'px'}
													style:width={o.w + 'px'}
													style:height={o.h + 'px'}
													onclick={(e) => objectClick(e, o)}
													aria-label="이미지 선택"
													><img src={o.src} alt="추가한 이미지" draggable="false" /></button
												>{:else if o.kind === 'memo'}<button
													class="note-object memo-pin"
													style:left={o.x + 'px'}
													style:top={o.y + 'px'}
													onclick={(e) => objectClick(e, o)}
													aria-label="메모 열기">{@html icon('memo')}</button
												>{#if memoOpen === o.id}<div
														class="memo-popup"
														style:left={Math.min(page.w - 320, o.x + 32) + 'px'}
														style:top={Math.min(page.h - 240, o.y) + 'px'}
													>
														<div class="memo-heading">
															메모<button
																onclick={() => {
																	activeText = null;
																	memoOpen = null;
																}}
																aria-label="메모 닫기">{@html icon('close')}</button
															>
														</div>
														<PersonalTextEditor
															transparent
															compact
															localAttachments={!remote}
															toolbarTarget={textToolbarHost}
															initialHtml={o.html}
															onhtmlchange={(html) => textChanged(o.id, html)}
														/><button class="memo-delete" onclick={removeSelected}
															>{@html icon('trash')}메모 삭제</button
														>
													</div>{/if}{:else}<div
													class="note-object text-object"
													class:editing={activeText === o.id}
													style:left={o.x + 'px'}
													style:top={o.y + 'px'}
													style:width={o.w + 'px'}
													style:min-height={o.h + 'px'}
													style:font-size={'16px'}
													role="button"
													tabindex="0"
													aria-label="텍스트박스 편집"
													onclick={(e) => objectClick(e, o)}
													onkeydown={(e) => {
														if (e.key === 'Enter') objectClick(e, o);
													}}
												>
													<div
														class="text-content"
														style:zoom={o.textScale || 1}
														style:width={100 / (o.textScale || 1) + '%'}
													>
														{#if activeText === o.id}<PersonalTextEditor
																transparent
																compact
																localAttachments={!remote}
																toolbarTarget={textToolbarHost}
																initialHtml={o.html}
																onhtmlchange={(html) => textChanged(o.id, html)}
															/>{:else}<div class="tiptap text-display">
																{@html safeHtml(o.html)}
															</div>{/if}
													</div>
													{#if activeText === o.id}<button
															class="text-move-handle"
															aria-label="텍스트박스 이동"
															onpointerdown={(e) => moveText(e, o)}
															onclick={(e) => e.stopPropagation()}>이동</button
														><button
															class="text-width-handle"
															aria-label="텍스트박스 너비 조절"
															onpointerdown={(e) => resizeText(e, o)}
															onclick={(e) => e.stopPropagation()}
														></button>{/if}
												</div>{/if}{/each}
										{#if selection && !activeText}<div
												class="selection-box"
												style:left={selection.x + 'px'}
												style:top={selection.y + 'px'}
												style:width={selection.w + 'px'}
												style:height={selection.h + 'px'}
												role="button"
												tabindex="0"
												aria-label="선택 영역 이동"
												onpointerdown={(e) => transform(e)}
											>
												<div
													class="selection-actions"
													style:transform={'scale(' + 1 / zoom + ')'}
													style:transform-origin="bottom left"
													style:bottom={selection.y * zoom < 45 ? 'auto' : 'calc(100% + 10px)'}
													style:top={selection.y * zoom < 45 ? 'calc(100% + 10px)' : undefined}
													onpointerdown={(e) => e.stopPropagation()}
													role="toolbar"
													tabindex="-1"
													aria-label="선택 작업"
												>
													<button onclick={duplicate}>복제</button><button onclick={removeSelected}
														>삭제</button
													><button onclick={() => (selected = [])}>해제</button>
												</div>
												{#each [[0, 0], [100, 0], [0, 100], [100, 100]] as [x, y] (x + '-' + y)}<button
														class="resize-handle"
														style:width={24 / zoom + 'px'}
														style:height={24 / zoom + 'px'}
														style:min-height={24 / zoom + 'px'}
														style:left={x + '%'}
														style:top={y + '%'}
														aria-label="선택 영역 크기 조절"
														onpointerdown={(e) => transform(e, true, [x, y])}
													></button>{/each}
											</div>{/if}
									</div>
								</div>{:else}<PassivePage
									{pdf}
									page={slot.p}
									{zoom}
									index={slot.i}
									onactivate={activatePage}
								/>{/if}
						</div>{/each}
				</div>{/each}
		</main>
		<div class="view-controls">
			<button aria-label="축소" onclick={() => (zoom = Math.max(0.35, zoom - 0.1))}>−</button
			><button class="zoom-value" onclick={fit}>{Math.round(zoom * 100)}%</button><button
				aria-label="확대"
				onclick={() => (zoom = Math.min(3, zoom + 0.1))}>＋</button
			><span></span><button
				aria-label="이전 페이지"
				title="이전 페이지 (←)"
				disabled={twoPage ? pageIndex < 2 : pageIndex === 0}
				onclick={() => jump(adjacentPage(pageIndex, -1, twoPage))}>‹</button
			><input
				aria-label="현재 페이지"
				type="number"
				min="1"
				max={pages.length}
				value={pageIndex + 1}
				onchange={(e) => jump(Number(e.currentTarget.value) - 1)}
			/><small>/ {pages.length}</small><button
				aria-label="다음 페이지"
				title="다음 페이지 (→)"
				disabled={twoPage
					? Math.floor(pageIndex / 2) * 2 + 2 >= pages.length
					: pageIndex === pages.length - 1}
				onclick={() => jump(adjacentPage(pageIndex, 1, twoPage))}>›</button
			><span></span><button onclick={fit}>폭 맞춤</button>
		</div>
	</div>
	<footer>
		<span>{pdfName || '줄 노트'}</span><span class="footer-status" role="status" aria-live="polite"
			>{status || (pageBusy ? '페이지 준비 중' : '')}</span
		><span>{remote ? 'NETAQ 계정에 저장' : '이 브라우저에 자동 저장'}</span>
	</footer>
</div>
