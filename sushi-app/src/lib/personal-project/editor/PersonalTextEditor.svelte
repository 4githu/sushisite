<script lang="ts">
	import { onMount, tick, untrack } from 'svelte';
	import ColorPicker from './PersonalColorPicker.svelte';
	import {
		createDocument,
		createId,
		normalizeChunks,
		normalizeDocument
	} from '$lib/textediter/model';
	import { SHORTCUTS, matchesShortcut } from '$lib/textediter/shortcuts';
	import type {
		EditorBlock,
		EditorDocument,
		FontSize,
		MarkName,
		TextBlock,
		TextChunk,
		TextMarks
	} from '$lib/textediter/types';
	import './personal-text-editor.css';

	let {
		initialValue = null,
		readonly = false,
		placeholder = '내용을 입력하세요…',
		onchange,
		questionChecks = {},
		onquestionchange
	}: {
		initialValue?: EditorDocument | null;
		readonly?: boolean;
		placeholder?: string;
		onchange?: (value: EditorDocument) => void;
		questionChecks?: Record<string, boolean>;
		onquestionchange?: (blockId: string, checked: boolean) => void;
	} = $props();

	let documentValue = $state(normalizeDocument(untrack(() => initialValue)));
	let surface: HTMLElement;
	let colorPanel = $state<'text' | 'highlight' | null>(null);
	let tableRows = $state(2);
	let tableColumns = $state(2);
	let selectedTextColor = $state('#111827');
	let selectedHighlightColor = $state('#fef08a');
	let selectedFontFamily = $state('inherit');
	let customFontFamily = $state('');
	let selectionSummary = $state('문단 · 기본 · 기본 크기');
	let pendingMarks = $state<TextMarks>({});
	let lastInitial = untrack(() => initialValue);
	let isRendering = false;
	let isComposing = false;
	let savedRange: Range | null = null;
	let jsonInput: HTMLInputElement;
	let undoStack = $state<EditorDocument[]>([]);
	let redoStack = $state<EditorDocument[]>([]);

	const empty = $derived(
		documentValue.blocks.every((block) =>
			block.type === 'table'
				? block.rows.every((row) =>
						row.every((cell) =>
							cell.blocks.every((child) => child.children.every((chunk) => !chunk.text))
						)
					)
				: block.children.every((chunk) => !chunk.text)
		)
	);
	const canUndo = $derived(undoStack.length > 0);
	const canRedo = $derived(redoStack.length > 0);

	$effect(() => {
		if (initialValue !== lastInitial) {
			lastInitial = initialValue;
			setDocumentInternal(initialValue, false);
		}
	});

	onMount(() => {
		renderDocument();
		emitChange();
	});

	export function getJSON() {
		return normalizeDocument(documentValue);
	}
	export function setJSON(value: unknown) {
		setDocumentInternal(value, true);
	}
	export function clear() {
		setDocumentInternal(createDocument(), true);
	}
	export function focus() {
		surface?.focus();
	}

	function downloadJson() {
		const blob = new Blob([JSON.stringify(getJSON(), null, 2)], { type: 'application/json' });
		const url = URL.createObjectURL(blob);
		const link = globalThis.document.createElement('a');
		link.href = url;
		link.download = `aura-editor-${new Date().toISOString().slice(0, 10)}.json`;
		link.click();
		URL.revokeObjectURL(url);
	}

	async function importJson(file?: File) {
		if (!file) return;
		try {
			const parsed = JSON.parse(await file.text());
			if (!parsed || !Array.isArray(parsed.blocks)) throw new Error('invalid');
			setDocumentInternal(parsed, true);
		} catch {
			globalThis.alert('에디터 JSON 형식이 아닙니다. 내보낸 .json 파일을 선택해주세요.');
		}
	}

	function setDocumentInternal(value: unknown, record = true) {
		if (record) pushUndo();
		documentValue = normalizeDocument(value);
		redoStack = [];
		void tick().then(() => {
			renderDocument();
			emitChange();
		});
	}

	function cloneDocument(value: EditorDocument) {
		return normalizeDocument(JSON.parse(JSON.stringify(value)));
	}

	function pushUndo() {
		undoStack = [...undoStack, cloneDocument(documentValue)].slice(-60);
	}

	function emitChange() {
		onchange?.(cloneDocument(documentValue));
	}

	function exec(command: string, value?: string) {
		restoreNativeSelection();
		surface?.focus();
		document.execCommand(command, false, value);
		syncFromDom(true);
	}

	function rememberSelection() {
		const selection = getSelection();
		if (!selection?.rangeCount || !surface) return;
		const range = selection.getRangeAt(0);
		const container = range.commonAncestorContainer;
		const element = container instanceof Element ? container : container.parentElement;
		if (element && surface.contains(element)) savedRange = range.cloneRange();
		updateSelectionSummary();
	}

	function restoreNativeSelection() {
		if (!savedRange) return;
		const selection = getSelection();
		selection?.removeAllRanges();
		selection?.addRange(savedRange);
	}

	function keepEditorSelection(event: MouseEvent) {
		event.preventDefault();
		rememberSelection();
	}

	function spanStyle(chunk: TextChunk) {
		const decorations = [chunk.underline && 'underline', chunk.strike && 'line-through']
			.filter(Boolean)
			.join(' ');
		return [
			chunk.bold && 'font-weight:700',
			chunk.italic && 'font-style:italic',
			decorations && `text-decoration:${decorations}`,
			chunk.fontSize && `font-size:${chunk.fontSize}px`,
			chunk.textColor && `color:${chunk.textColor}`,
			chunk.highlightColor && `background-color:${chunk.highlightColor}`,
			chunk.fontFamily && `font-family:${chunk.fontFamily}`,
			chunk.code && 'font-family:ui-monospace,monospace'
		]
			.filter(Boolean)
			.join(';');
	}

	function createTextSpan(chunk: TextChunk) {
		const span = globalThis.document.createElement('span');
		span.dataset.chunk = 'true';
		if (chunk.bold) span.dataset.bold = 'true';
		if (chunk.italic) span.dataset.italic = 'true';
		if (chunk.underline) span.dataset.underline = 'true';
		if (chunk.strike) span.dataset.strike = 'true';
		if (chunk.code) span.dataset.code = 'true';
		if (chunk.fontSize) span.dataset.fontSize = String(chunk.fontSize);
		if (chunk.fontFamily) span.dataset.fontFamily = chunk.fontFamily;
		if (chunk.textColor) span.dataset.textColor = chunk.textColor;
		if (chunk.highlightColor) span.dataset.highlightColor = chunk.highlightColor;
		span.style.cssText = spanStyle(chunk);
		span.textContent = chunk.text || '\u200b';
		return span;
	}

	function renderTextBlock(block: TextBlock, showQuestionCheck = true) {
		const element = globalThis.document.createElement('div');
		element.className = 'text-block';
		element.dataset.blockId = block.id;
		element.dataset.type = block.type;
		if (block.level) element.dataset.level = String(block.level);
		if (block.depth) element.style.marginLeft = `${block.depth * 24}px`;
		element.style.setProperty('--block-indent', `${(block.depth ?? 0) * 24}px`);
		for (const chunk of block.children) element.append(createTextSpan(chunk));
		if (showQuestionCheck && (!readonly || questionChecks[block.id])) {
			element.append(createQuestionCheck(block.id, readonly));
		}
		return element;
	}

	function createQuestionCheck(blockId: string, displayOnly = false) {
		const checked = Boolean(questionChecks[blockId]);
		const check = globalThis.document.createElement('button');
		check.type = 'button';
		check.contentEditable = 'false';
		check.disabled = displayOnly;
		check.dataset.editorUi = 'true';
		check.className = `question-check${checked ? ' checked' : ''}`;
		check.title = checked ? '이 부분은 물어봤음' : '이 부분을 물어봤음으로 표시';
		check.setAttribute('aria-label', check.title);
		check.setAttribute('aria-pressed', String(checked));
		check.addEventListener('mousedown', (event) => event.preventDefault());
		check.addEventListener('click', (event) => {
			event.preventDefault();
			event.stopPropagation();
			if (displayOnly) return;
			const nextChecked = !check.classList.contains('checked');
			check.classList.toggle('checked', nextChecked);
			check.setAttribute('aria-pressed', String(nextChecked));
			onquestionchange?.(blockId, nextChecked);
		});
		return check;
	}

	function renderDocument() {
		if (!surface) return;
		isRendering = true;
		/* eslint-disable svelte/no-dom-manipulating */
		surface.replaceChildren();
		for (const block of documentValue.blocks) {
			if (block.type !== 'table') {
				surface.append(renderTextBlock(block));
				continue;
			}
			const wrapper = globalThis.document.createElement('div');
			wrapper.dataset.tableId = block.id;
			wrapper.dataset.depth = String(block.depth ?? 0);
			wrapper.style.setProperty('--block-indent', `${(block.depth ?? 0) * 24}px`);
			if (block.depth) wrapper.style.marginLeft = `${block.depth * 24}px`;
			const table = globalThis.document.createElement('table');
			table.className = 'editor-table';
			const tbody = globalThis.document.createElement('tbody');
			for (const row of block.rows) {
				const tr = globalThis.document.createElement('tr');
				for (const cell of row) {
					const td = globalThis.document.createElement('td');
					td.dataset.cellId = cell.id;
					for (const child of cell.blocks) td.append(renderTextBlock(child, false));
					tr.append(td);
				}
				tbody.append(tr);
			}
			table.append(tbody);
			wrapper.append(table);
			if (
				!readonly ||
				questionChecks[block.id] ||
				block.rows.some((row) =>
					row.some((cell) => cell.blocks.some((child) => questionChecks[child.id]))
				)
			) {
				const tableCheck = createQuestionCheck(block.id, readonly);
				tableCheck.classList.add('table-question-check');
				if (
					block.rows.some((row) =>
						row.some((cell) => cell.blocks.some((child) => questionChecks[child.id]))
					)
				) {
					tableCheck.classList.add('checked');
				}
				wrapper.append(tableCheck);
			}
			if (!readonly) wrapper.append(createTableControls(block));
			surface.append(wrapper);
		}
		/* eslint-enable svelte/no-dom-manipulating */
		isRendering = false;
	}

	function createTableControls(block: Extract<EditorBlock, { type: 'table' }>) {
		const controls = globalThis.document.createElement('div');
		controls.className = 'table-controls';
		const actions: Array<[string, () => void]> = [
			['행 추가', () => addTableRow(block.id)],
			['열 추가', () => addTableColumn(block.id)],
			['마지막 행 삭제', () => deleteTableRow(block.id)],
			['마지막 열 삭제', () => deleteTableColumn(block.id)],
			['표 내어쓰기', () => changeTableDepth(block.id, -1)],
			['표 들여쓰기', () => changeTableDepth(block.id, 1)],
			['표 삭제', () => deleteTable(block.id)]
		];
		for (const [label, action] of actions) {
			const button = globalThis.document.createElement('button');
			button.type = 'button';
			button.textContent = label;
			button.addEventListener('click', action);
			controls.append(button);
		}
		return controls;
	}

	function updateSelectionSummary() {
		const block = activeBlock();
		const selection = getSelection();
		const node = selection?.anchorNode;
		const marks = node ? marksFromNode(node) : {};
		const parts = [
			blockLabel(block),
			marks.fontFamily ? marks.fontFamily.replaceAll('"', '') : '기본',
			marks.fontSize ? `${marks.fontSize}px` : '기본 크기',
			marks.bold && '굵게',
			marks.italic && '기울임',
			marks.underline && '밑줄',
			marks.textColor && `글자 ${marks.textColor}`,
			marks.highlightColor && `형광 ${marks.highlightColor}`
		].filter(Boolean);
		selectionSummary = parts.join(' · ');
	}

	function blockLabel(block?: HTMLElement | null) {
		const type = block?.dataset.type;
		if (type === 'heading') return `제목 ${block?.dataset.level ?? 1}`;
		if (type === 'orderedList') return '번호 목록';
		if (type === 'bulletList') return '글머리 목록';
		if (type === 'blockquote') return '인용문';
		if (type === 'codeBlock') return '코드';
		return '문단';
	}

	function marksFromNode(node: Node): TextMarks {
		const element = node instanceof HTMLElement ? node : node.parentElement;
		const marks: TextMarks = {};
		if (!element) return marks;
		if (element.closest('[data-bold="true"],b,strong')) marks.bold = true;
		if (element.closest('[data-italic="true"],i,em')) marks.italic = true;
		if (element.closest('[data-underline="true"],u')) marks.underline = true;
		if (element.closest('[data-strike="true"],s,strike,del')) marks.strike = true;
		if (element.closest('[data-code="true"],code')) marks.code = true;
		const fontSource = element.closest<HTMLElement>('[data-font-family]');
		const textColorSource = element.closest<HTMLElement>('[data-text-color]');
		const highlightSource = element.closest<HTMLElement>('[data-highlight-color]');
		const sizeSource = element.closest<HTMLElement>('[data-font-size]');
		const size = Number(sizeSource?.dataset.fontSize);
		if ([12, 16, 20, 28].includes(size)) marks.fontSize = size as FontSize;
		if (textColorSource?.dataset.textColor) marks.textColor = textColorSource.dataset.textColor;
		if (highlightSource?.dataset.highlightColor)
			marks.highlightColor = highlightSource.dataset.highlightColor;
		if (fontSource?.dataset.fontFamily) marks.fontFamily = fontSource.dataset.fontFamily;
		const style = getComputedStyle(element);
		const textColor = rgbToHex(style.color);
		const highlightColor = rgbToHex(style.backgroundColor);
		if (textColor) marks.textColor = textColor;
		if (isTransparent(style.backgroundColor)) delete marks.highlightColor;
		else if (highlightColor && highlightColor !== '#ffffff') marks.highlightColor = highlightColor;
		if (Number.parseInt(style.fontWeight, 10) >= 600) marks.bold = true;
		if (style.fontStyle === 'italic') marks.italic = true;
		if (style.textDecorationLine.includes('underline')) marks.underline = true;
		if (style.textDecorationLine.includes('line-through')) marks.strike = true;
		return marks;
	}

	function rgbToHex(value: string) {
		const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([.\d]+))?\)/);
		if (!match || match[4] === '0') return undefined;
		return `#${[match[1], match[2], match[3]]
			.map((part) => Number(part).toString(16).padStart(2, '0'))
			.join('')}`;
	}

	function isTransparent(value: string) {
		return value === 'transparent' || /rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(value);
	}

	function parseTextBlock(element: HTMLElement): TextBlock {
		const chunks: TextChunk[] = [];
		const visit = (node: Node) => {
			if (node instanceof HTMLElement && node.dataset.editorUi) return;
			if (node.nodeType === Node.TEXT_NODE) {
				const text = (node.textContent ?? '').replace(/\u200b/g, '');
				if (text) chunks.push({ type: 'text', text, ...marksFromNode(node) });
				return;
			}
			if (node instanceof HTMLBRElement) {
				chunks.push({ type: 'text', text: '\n', ...pendingMarks });
				return;
			}
			for (const child of Array.from(node.childNodes)) visit(child);
		};
		for (const child of Array.from(element.childNodes)) visit(child);
		const type = (element.dataset.type ?? 'paragraph') as TextBlock['type'];
		const block: TextBlock = {
			id: element.dataset.blockId || createId('block'),
			type,
			children: normalizeChunks(chunks.length ? chunks : [{ type: 'text', text: '' }])
		};
		if (type === 'heading') block.level = Number(element.dataset.level || 1) as 1 | 2 | 3;
		const depth = depthFromElement(element);
		if (depth) block.depth = depth;
		return block;
	}

	function parseSurface(): EditorDocument {
		const blocks: EditorBlock[] = [];
		for (const child of Array.from(surface.children)) {
			const element = child as HTMLElement;
			if (element.dataset.tableId) {
				const rows = Array.from(element.querySelectorAll('tr')).map((row) =>
					Array.from(row.querySelectorAll('td')).map((cell) => ({
						id: cell.dataset.cellId || createId('cell'),
						blocks: Array.from(cell.querySelectorAll<HTMLElement>(':scope > .text-block')).map(
							parseTextBlock
						)
					}))
				);
				const depth = Math.max(0, Math.min(6, Number(element.dataset.depth ?? 0)));
				blocks.push({
					id: element.dataset.tableId,
					type: 'table',
					...(depth ? { depth } : {}),
					rows
				});
			} else if (element.classList.contains('text-block')) blocks.push(parseTextBlock(element));
		}
		return normalizeDocument({ ...documentValue, blocks });
	}

	function syncFromDom(record = false) {
		if (isRendering || !surface) return;
		if (record) pushUndo();
		documentValue = parseSurface();
		redoStack = [];
		emitChange();
	}

	function refreshDocumentFromDom() {
		if (!surface || isRendering) return;
		documentValue = parseSurface();
	}

	function applyMarkdownIfNeeded() {
		const selection = getSelection();
		const block = activeBlock();
		if (!selection || !block) return false;
		const text = block.innerText.replace(/\n$/, '');
		const markdown = text.match(/^(#{1,3}|[-*]|1\.|>) $|^```$/);
		if (!markdown) return false;
		const token = markdown[1] ?? '```';
		block.textContent = '';
		block.dataset.type = token.startsWith('#')
			? 'heading'
			: token === '-' || token === '*'
				? 'bulletList'
				: token === '1.'
					? 'orderedList'
					: token === '>'
						? 'blockquote'
						: 'codeBlock';
		if (token.startsWith('#')) block.dataset.level = String(token.length);
		else delete block.dataset.level;
		placeCursor(block, 0);
		syncFromDom(true);
		return true;
	}

	function activeBlock() {
		const selection = getSelection();
		const node = selection?.anchorNode;
		return (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>(
			'.text-block'
		);
	}

	function placeCursor(root: HTMLElement, offset: number) {
		const range = globalThis.document.createRange();
		const walker = globalThis.document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
		let remaining = offset;
		let textNode: Node | null;
		while ((textNode = walker.nextNode())) {
			const length = textNode.textContent?.length ?? 0;
			if (remaining <= length) {
				range.setStart(textNode, remaining);
				range.collapse(true);
				const selection = getSelection();
				selection?.removeAllRanges();
				selection?.addRange(range);
				return;
			}
			remaining -= length;
		}
		range.selectNodeContents(root);
		range.collapse(false);
		const selection = getSelection();
		selection?.removeAllRanges();
		selection?.addRange(range);
	}

	function toggleMark(mark: MarkName) {
		const command = mark === 'strike' ? 'strikeThrough' : mark;
		pendingMarks = { ...pendingMarks, [mark]: pendingMarks[mark] ? undefined : true };
		exec(command);
	}

	function selectValue(
		mark: 'fontSize' | 'textColor' | 'highlightColor',
		value?: FontSize | string
	) {
		restoreNativeSelection();
		if (mark === 'textColor' && typeof value === 'string') {
			selectedTextColor = value;
			pendingMarks = { ...pendingMarks, textColor: value };
			exec('foreColor', value);
		} else if (mark === 'highlightColor' && typeof value === 'string') {
			selectedHighlightColor = value;
			pendingMarks = { ...pendingMarks, highlightColor: value };
			exec('hiliteColor', value);
		} else if (mark === 'fontSize' && typeof value === 'number') {
			pendingMarks = { ...pendingMarks, fontSize: value };
			applyMarksToSelection({ fontSize: value });
		} else if (mark === 'textColor') {
			pendingMarks = { ...pendingMarks, textColor: undefined };
			exec('removeFormat');
		} else if (mark === 'highlightColor') {
			pendingMarks = { ...pendingMarks, highlightColor: undefined };
			exec('removeFormat');
		}
		colorPanel = null;
	}

	function selectFontFamily(value: string) {
		restoreNativeSelection();
		selectedFontFamily = value;
		if (value === 'inherit') {
			pendingMarks = { ...pendingMarks, fontFamily: undefined };
			exec('removeFormat');
			return;
		}
		pendingMarks = { ...pendingMarks, fontFamily: value };
		applyMarksToSelection({ fontFamily: value });
	}

	function applyCustomFontFamily() {
		const value = customFontFamily.trim();
		if (!value) return;
		selectFontFamily(value);
	}

	function applyMarksToSelection(marks: TextMarks) {
		const selection = getSelection();
		if (!selection?.rangeCount) return;
		const range = selection.getRangeAt(0);
		if (range.collapsed) return;
		pushUndo();
		const span = createTextSpan({ type: 'text', text: '', ...marks });
		const contents = range.extractContents();
		span.replaceChildren(...Array.from(contents.childNodes));
		range.insertNode(span);
		selection.removeAllRanges();
		const next = globalThis.document.createRange();
		next.selectNodeContents(span);
		selection.addRange(next);
		syncFromDom(true);
	}

	function pressed(mark: MarkName): boolean | 'mixed' {
		if (pendingMarks[mark]) return true;
		return false;
	}

	function openColors(kind: 'text' | 'highlight') {
		rememberSelection();
		colorPanel = colorPanel === kind ? null : kind;
	}

	function changeCurrentBlock(type: TextBlock['type'], level?: 1 | 2 | 3) {
		restoreNativeSelection();
		const blocks = selectedTextBlocks();
		if (!blocks.length) return;
		pushUndo();
		for (const block of blocks) {
			block.dataset.type = type;
			if (level) block.dataset.level = String(level);
			else delete block.dataset.level;
		}
		syncFromDom();
		updateSelectionSummary();
	}

	function handleInput() {
		if (isComposing) return;
		if (applyMarkdownIfNeeded()) return;
		syncFromDom(true);
	}

	function handleBeforeInput(event: InputEvent) {
		if (readonly) event.preventDefault();
	}

	function handleCopy(event: ClipboardEvent) {
		const selection = getSelection();
		if (!selection?.rangeCount || selection.isCollapsed) return;
		const blocks = selectedTextBlocks();
		if (!blocks.length) return;
		if (blocks.length === 1) {
			const clone = blocks[0].cloneNode(true) as HTMLElement;
			clone.querySelectorAll('[data-editor-ui]').forEach((item) => item.remove());
			if (selection.toString() !== (clone.textContent ?? '')) return;
		}
		const table = (selection.anchorNode instanceof Element
			? selection.anchorNode
			: selection.anchorNode?.parentElement)?.closest<HTMLElement>('[data-table-id]');
		if (table) {
			event.preventDefault();
			const cloned = table.querySelector('table')?.cloneNode(true) as HTMLTableElement | undefined;
			if (!cloned) return;
			event.clipboardData?.setData('text/html', cloned.outerHTML);
			event.clipboardData?.setData(
				'text/plain',
				Array.from(cloned.rows).map((row) => Array.from(row.cells).map((cell) => cell.innerText).join('\t')).join('\n')
			);
			return;
		}
		event.preventDefault();
		const text = blocks
			.map((block) => {
				const clone = block.cloneNode(true) as HTMLElement;
				clone.querySelectorAll('[data-editor-ui]').forEach((item) => item.remove());
				return `${'\t'.repeat(depthFromElement(block))}${(clone.textContent ?? '')
					.replace(/\u200b/g, '')
					.replace(/\n$/, '')}`;
			})
			.join('\n');
		event.clipboardData?.setData('text/plain', text);
	}

	function pastedLine(value: string) {
		let depth = 0;
		let offset = 0;
		while (offset < value.length && depth < 6) {
			if (value[offset] === '\t') {
				depth += 1;
				offset += 1;
			} else if (value.slice(offset, offset + 4) === '    ') {
				depth += 1;
				offset += 4;
			} else break;
		}
		return { depth, text: value.slice(offset) };
	}

	function handlePaste(event: ClipboardEvent) {
		if (readonly) return;
		event.preventDefault();
		const html = event.clipboardData?.getData('text/html') ?? '';
		const text = (event.clipboardData?.getData('text/plain').slice(0, 100_000) ?? '').replace(
			/\r\n?/g,
			'\n'
		);
		const pastedTable = tableFromClipboard(html, text);
		if (pastedTable) {
			insertTableAfterActive(pastedTable);
			return;
		}
		pushUndo();
		const lines = text.split('\n').map(pastedLine);
		for (const [index, line] of lines.entries()) {
			const block = activeBlock();
			if (block) {
				block.style.marginLeft = line.depth ? `${line.depth * 24}px` : '';
				block.style.setProperty('--block-indent', `${line.depth * 24}px`);
			}
			if (line.text) globalThis.document.execCommand('insertText', false, line.text);
			if (index < lines.length - 1) splitCurrentBlock(false, false);
		}
		syncFromDom();
	}

	function tableFromClipboard(html: string, plain: string): Extract<EditorBlock, { type: 'table' }> | null {
		let matrix: string[][] = [];
		if (html.includes('<table')) {
			const root = globalThis.document.createElement('div');
			root.innerHTML = html;
			matrix = Array.from(root.querySelectorAll('tr')).map((row) =>
				Array.from(row.querySelectorAll('th,td')).map((cell) => cell.textContent?.replace(/\s+/g, ' ').trim() ?? '')
			);
		} else {
			const lines = plain.split('\n').filter((line) => line.trim());
			const markdown = lines.filter((line) => !/^\s*\|?\s*:?-{3,}/.test(line));
			if (markdown.length >= 2 && markdown.every((line) => line.includes('|')))
				matrix = markdown.map((line) => line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim()));
			else if (lines.length >= 2 && lines.every((line) => line.includes('\t')))
				matrix = lines.map((line) => line.split('\t').map((cell) => cell.trim()));
		}
		const width = Math.max(0, ...matrix.map((row) => row.length));
		if (matrix.length < 1 || width < 1) return null;
		return {
			id: createId('table'), type: 'table',
			rows: matrix.map((row) => Array.from({ length: width }, (_, index) => ({
				id: createId('cell'), blocks: [{ id: createId('block'), type: 'paragraph' as const,
					children: [{ type: 'text' as const, text: row[index] ?? '' }] }]
			})))
		};
	}

	function insertTableAfterActive(table: Extract<EditorBlock, { type: 'table' }>) {
		refreshDocumentFromDom();
		pushUndo();
		const anchor = activeBlock()?.closest<HTMLElement>('[data-table-id]')?.dataset.tableId ?? activeBlock()?.dataset.blockId;
		const index = documentValue.blocks.findIndex((block) => block.id === anchor);
		const paragraph: TextBlock = { id: createId('block'), type: 'paragraph', children: [{ type: 'text', text: '' }] };
		documentValue = normalizeDocument({ ...documentValue, blocks: [
			...documentValue.blocks.slice(0, index + 1), table, paragraph, ...documentValue.blocks.slice(index + 1)
		] });
		renderDocument();
		emitChange();
		void tick().then(() => {
			const next = surface.querySelector<HTMLElement>(`[data-block-id="${paragraph.id}"]`);
			if (next) placeCursor(next, 0);
		});
	}

	function recentColor(kind: 'text' | 'highlight') {
		const fallback = kind === 'text' ? selectedTextColor : selectedHighlightColor;
		try {
			const stored = JSON.parse(localStorage.getItem(`textediter-recent-${kind}`) ?? '[]');
			return typeof stored?.[0] === 'string' ? stored[0] : fallback;
		} catch {
			return fallback;
		}
	}

	function selectionHasColor(kind: 'text' | 'highlight', color: string) {
		const selection = getSelection();
		if (!selection?.rangeCount || selection.isCollapsed || !surface) return false;
		const range = selection.getRangeAt(0);
		const nodes: Node[] = [];
		const walker = globalThis.document.createTreeWalker(surface, NodeFilter.SHOW_TEXT);
		let node: Node | null;
		while ((node = walker.nextNode())) {
			if (node.textContent?.replace(/\u200b/g, '') && range.intersectsNode(node)) nodes.push(node);
		}
		const key = kind === 'text' ? 'textColor' : 'highlightColor';
		return nodes.length > 0 && nodes.every((item) => marksFromNode(item)[key] === color);
	}

	function applyRecentColor(kind: 'text' | 'highlight') {
		rememberSelection();
		const color = recentColor(kind);
		const shouldRemove = selectionHasColor(kind, color);
		if (kind === 'highlight') {
			selectedHighlightColor = color;
			exec('hiliteColor', shouldRemove ? 'transparent' : color);
		} else {
			selectedTextColor = color;
			exec('foreColor', shouldRemove ? '#111827' : color);
		}
	}

	function applyHighlightShortcut(color: string) {
		try {
			const key = 'textediter-recent-highlight';
			const stored = JSON.parse(localStorage.getItem(key) ?? '[]');
			localStorage.setItem(
				key,
				JSON.stringify([color, ...stored.filter((item: unknown) => item !== color)].slice(0, 6))
			);
		} catch {
			// 저장소를 막은 브라우저에서도 서식 적용은 계속한다.
		}
		selectedHighlightColor = color;
		const shouldRemove = selectionHasColor('highlight', color);
		exec('hiliteColor', shouldRemove ? 'transparent' : color);
	}

	function toggleQuestionChecks() {
		const table = activeBlock()?.closest<HTMLElement>('[data-table-id]');
		if (table) {
			const check = table.querySelector<HTMLButtonElement>(':scope > .table-question-check');
			if (!check) return;
			const checked = !check.classList.contains('checked');
			check.classList.toggle('checked', checked);
			check.setAttribute('aria-pressed', String(checked));
			onquestionchange?.(table.dataset.tableId ?? '', checked);
			return;
		}
		const blocks = selectedTextBlocks();
		if (!blocks.length) return;
		const shouldCheck = !blocks.every((block) =>
			block.querySelector('.question-check')?.classList.contains('checked')
		);
		for (const block of blocks) {
			const check = block.querySelector<HTMLButtonElement>('.question-check');
			if (!check) continue;
			check.classList.toggle('checked', shouldCheck);
			check.setAttribute('aria-pressed', String(shouldCheck));
			check.title = shouldCheck ? '이 부분은 물어봤음' : '이 부분을 물어봤음으로 표시';
			onquestionchange?.(block.dataset.blockId ?? '', shouldCheck);
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (readonly) return;
		if (
			(event.ctrlKey || event.metaKey) &&
			event.altKey &&
			!event.shiftKey &&
			event.key.toLowerCase() === 'q'
		) {
			event.preventDefault();
			toggleQuestionChecks();
		} else if (
			(event.ctrlKey || event.metaKey) &&
			event.altKey &&
			!event.shiftKey &&
			event.code === 'Digit1'
		) {
			event.preventDefault();
			applyHighlightShortcut('#fed7aa');
		} else if (
			(event.ctrlKey || event.metaKey) &&
			event.altKey &&
			!event.shiftKey &&
			event.code === 'Digit2'
		) {
			event.preventDefault();
			applyHighlightShortcut('#fef08a');
		} else if (
			(event.ctrlKey || event.metaKey) &&
			event.altKey &&
			!event.shiftKey &&
			event.code === 'Digit3'
		) {
			event.preventDefault();
			applyHighlightShortcut('#fdba74');
		} else if (matchesShortcut(event, SHORTCUTS.bold)) {
			event.preventDefault();
			toggleMark('bold');
		} else if (matchesShortcut(event, SHORTCUTS.italic)) {
			event.preventDefault();
			toggleMark('italic');
		} else if (matchesShortcut(event, SHORTCUTS.underline)) {
			event.preventDefault();
			toggleMark('underline');
		} else if (matchesShortcut(event, SHORTCUTS.undo)) {
			event.preventDefault();
			undo();
		} else if (matchesShortcut(event, SHORTCUTS.redo)) {
			event.preventDefault();
			redo();
		} else if (matchesShortcut(event, SHORTCUTS.highlightColor)) {
			event.preventDefault();
			applyRecentColor('highlight');
		} else if (matchesShortcut(event, SHORTCUTS.textColor)) {
			event.preventDefault();
			applyRecentColor('text');
		} else if (
			event.key === 'Enter' &&
			!event.shiftKey &&
			activeBlock()?.dataset.type === 'codeBlock'
		) {
			event.preventDefault();
			exec('insertLineBreak');
		} else if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			splitCurrentBlock();
		} else if (event.key === 'Tab') {
			event.preventDefault();
			const tableId = activeBlock()?.closest<HTMLElement>('[data-table-id]')?.dataset.tableId;
			if (tableId) changeTableDepth(tableId, event.shiftKey ? -1 : 1);
			else indentSelectedBlocks(event.shiftKey ? -1 : 1);
		}
	}

	function selectedTextBlocks() {
		const selection = getSelection();
		if (!selection?.rangeCount || !surface) return [];
		const range = selection.getRangeAt(0);
		const blocks = Array.from(surface.querySelectorAll<HTMLElement>('.text-block')).filter(
			(block) => range.intersectsNode(block)
		);
		const block = activeBlock();
		return blocks.length ? blocks : block ? [block] : [];
	}

	function indentSelectedBlocks(direction: 1 | -1) {
		const blocks = selectedTextBlocks();
		if (!blocks.length) return;
		pushUndo();
		for (const block of blocks) {
			const depth = Math.max(0, Math.min(6, depthFromElement(block) + direction));
			if (depth) block.style.marginLeft = `${depth * 24}px`;
			else block.style.marginLeft = '';
			block.style.setProperty('--block-indent', `${depth * 24}px`);
		}
		syncFromDom();
	}

	function depthFromElement(element: HTMLElement) {
		const margin = Number.parseInt(element.style.marginLeft || '0', 10);
		return Number.isFinite(margin) ? Math.round(margin / 24) : 0;
	}

	function splitCurrentBlock(record = true, sync = true) {
		const block = activeBlock();
		const selection = getSelection();
		if (!block || !selection?.rangeCount) return;
		if (record) pushUndo();
		const range = selection.getRangeAt(0);
		range.deleteContents();
		const afterRange = range.cloneRange();
		const editorUi = block.querySelector<HTMLElement>(':scope > [data-editor-ui]');
		if (editorUi) afterRange.setEndBefore(editorUi);
		else afterRange.setEndAfter(block.lastChild ?? block);
		const tail = afterRange.extractContents();
		const next = globalThis.document.createElement('div');
		next.className = 'text-block';
		next.dataset.blockId = createId('block');
		next.dataset.type = block.dataset.type ?? 'paragraph';
		if (block.dataset.level) next.dataset.level = block.dataset.level;
		next.style.marginLeft = block.style.marginLeft;
		next.style.setProperty('--block-indent', block.style.getPropertyValue('--block-indent'));
		if (!block.textContent?.replace(/\u200b/g, '').trim()) {
			block.dataset.type = 'paragraph';
			delete block.dataset.level;
			block.style.marginLeft = '';
			next.dataset.type = 'paragraph';
			delete next.dataset.level;
		}
		next.append(tail);
		if (!next.textContent) next.append(createTextSpan({ type: 'text', text: '' }));
		if (!readonly) next.append(createQuestionCheck(next.dataset.blockId));
		block.after(next);
		placeCursor(next, 0);
		if (sync) syncFromDom();
	}

	function undo() {
		const previous = undoStack.at(-1);
		if (!previous) return;
		redoStack = [...redoStack, cloneDocument(documentValue)].slice(-60);
		undoStack = undoStack.slice(0, -1);
		documentValue = previous;
		renderDocument();
		emitChange();
	}

	function redo() {
		const next = redoStack.at(-1);
		if (!next) return;
		undoStack = [...undoStack, cloneDocument(documentValue)].slice(-60);
		redoStack = redoStack.slice(0, -1);
		documentValue = next;
		renderDocument();
		emitChange();
	}

	function addTable() {
		const selectedBlock = activeBlock();
		const selectedTable = selectedBlock?.closest<HTMLElement>('[data-table-id]');
		const anchorId = selectedTable?.dataset.tableId ?? selectedBlock?.dataset.blockId;
		refreshDocumentFromDom();
		pushUndo();
		const rows = Math.min(10, Math.max(1, tableRows));
		const columns = Math.min(10, Math.max(1, tableColumns));
		const table: EditorBlock = {
			id: createId('table'),
			type: 'table',
			rows: Array.from({ length: rows }, () =>
				Array.from({ length: columns }, () => ({
					id: createId('cell'),
					blocks: [
						{ id: createId('block'), type: 'paragraph', children: [{ type: 'text', text: '' }] }
					]
				}))
			)
		};
		const paragraph: EditorBlock = {
			id: createId('block'),
			type: 'paragraph',
			children: [{ type: 'text', text: '' }]
		};
		const insertAfter = documentValue.blocks.findIndex((block) => block.id === anchorId);
		const index = insertAfter < 0 ? documentValue.blocks.length : insertAfter + 1;
		documentValue = normalizeDocument({
			...documentValue,
			blocks: [
				...documentValue.blocks.slice(0, index),
				table,
				paragraph,
				...documentValue.blocks.slice(index)
			]
		});
		renderDocument();
		emitChange();
		void tick().then(() => {
			const next = surface.querySelector<HTMLElement>(`[data-block-id="${paragraph.id}"]`);
			if (next) placeCursor(next, 0);
		});
	}

	function updateTable(
		tableId: string,
		change: (table: Extract<EditorBlock, { type: 'table' }>) => void
	) {
		refreshDocumentFromDom();
		pushUndo();
		const next = cloneDocument(documentValue);
		const table = next.blocks.find((block) => block.type === 'table' && block.id === tableId);
		if (table?.type === 'table') change(table);
		documentValue = normalizeDocument(next);
		renderDocument();
		emitChange();
	}

	function addTableRow(tableId: string) {
		updateTable(tableId, (table) => {
			const columns = table.rows[0]?.length ?? 1;
			table.rows.push(
				Array.from({ length: columns }, () => ({
					id: createId('cell'),
					blocks: [
						{ id: createId('block'), type: 'paragraph', children: [{ type: 'text', text: '' }] }
					]
				}))
			);
		});
	}
	function addTableColumn(tableId: string) {
		updateTable(tableId, (table) => {
			for (const row of table.rows)
				row.push({
					id: createId('cell'),
					blocks: [
						{ id: createId('block'), type: 'paragraph', children: [{ type: 'text', text: '' }] }
					]
				});
		});
	}
	function deleteTableRow(tableId: string) {
		updateTable(tableId, (table) => {
			if (table.rows.length > 1) table.rows.pop();
		});
	}
	function deleteTableColumn(tableId: string) {
		updateTable(tableId, (table) => {
			if ((table.rows[0]?.length ?? 0) > 1) for (const row of table.rows) row.pop();
		});
	}
	function changeTableDepth(tableId: string, amount: number) {
		updateTable(tableId, (table) => {
			table.depth = Math.max(0, Math.min(6, (table.depth ?? 0) + amount));
		});
	}
	function deleteTable(tableId: string) {
		refreshDocumentFromDom();
		pushUndo();
		documentValue = normalizeDocument({
			...documentValue,
			blocks: documentValue.blocks.filter((block) => block.id !== tableId)
		});
		renderDocument();
		emitChange();
	}
</script>

<svelte:document onselectionchange={rememberSelection} />

<section class="text-editor-card" aria-label="리치 텍스트 에디터">
	<div class="text-editor-toolbar" role="toolbar" tabindex="0" aria-label="텍스트 서식">
		<div class="toolbar-group">
			<button
				aria-label="실행 취소"
				disabled={readonly || !canUndo}
				onmousedown={keepEditorSelection}
				onclick={undo}>↶</button
			>
			<button
				aria-label="다시 실행"
				disabled={readonly || !canRedo}
				onmousedown={keepEditorSelection}
				onclick={redo}>↷</button
			>
		</div>
		<div class="toolbar-group">
			<button
				aria-label="굵게"
				aria-pressed={pressed('bold')}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => toggleMark('bold')}><b>B</b></button
			>
			<button
				aria-label="기울임"
				aria-pressed={pressed('italic')}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => toggleMark('italic')}><i>I</i></button
			>
			<button
				aria-label="밑줄"
				aria-pressed={pressed('underline')}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => toggleMark('underline')}><u>U</u></button
			>
			<button
				aria-label="취소선"
				aria-pressed={pressed('strike')}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => toggleMark('strike')}><s>S</s></button
			>
		</div>
		<div class="toolbar-group">
			<select
				aria-label="글꼴"
				bind:value={selectedFontFamily}
				disabled={readonly}
				onchange={(event) => selectFontFamily(event.currentTarget.value)}
			>
				<option value="inherit">기본 글꼴</option>
				<option value="Arial, sans-serif">Arial</option>
				<option value="Georgia, serif">Georgia</option>
				<option value="Times New Roman, serif">Times</option>
				<option value="ui-monospace, monospace">Monospace</option>
				<option value="Pretendard, sans-serif">Pretendard</option>
			</select>
			<input
				class="font-family-input"
				aria-label="사용자 지정 글꼴"
				placeholder="글꼴 직접 입력"
				bind:value={customFontFamily}
				disabled={readonly}
				onkeydown={(event) => {
					if (event.key === 'Enter') {
						event.preventDefault();
						applyCustomFontFamily();
					}
				}}
				onchange={applyCustomFontFamily}
			/>
			<select
				aria-label="글자 크기"
				disabled={readonly}
				onchange={(event) => selectValue('fontSize', Number(event.currentTarget.value) as FontSize)}
			>
				<option value="16">기본 (16)</option><option value="12">작게 (12)</option><option value="20"
					>중간 제목 (20)</option
				><option value="28">큰 제목 (28)</option>
			</select>
			<button
				aria-label="글자색 선택"
				aria-pressed={pressed('textColor')}
				aria-expanded={colorPanel === 'text'}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => openColors('text')}>A 색상</button
			>
			{#if colorPanel === 'text'}<ColorPicker
					kind="text"
					value={selectedTextColor}
					onselect={(color) => selectValue('textColor', color)}
					onclose={() => (colorPanel = null)}
				/>{/if}
		</div>
		<div class="toolbar-group">
			<button
				aria-label="형광펜 선택"
				aria-pressed={pressed('highlightColor')}
				aria-expanded={colorPanel === 'highlight'}
				disabled={readonly}
				onmousedown={keepEditorSelection}
				onclick={() => openColors('highlight')}>▰ 형광펜</button
			>
			{#if colorPanel === 'highlight'}<ColorPicker
					kind="highlight"
					value={selectedHighlightColor}
					onselect={(color) => selectValue('highlightColor', color)}
					onclose={() => (colorPanel = null)}
				/>{/if}
		</div>
		<div class="toolbar-group">
			<select
				aria-label="블록 유형"
				disabled={readonly}
				onchange={(event) => {
					const [type, level] = event.currentTarget.value.split(':');
					changeCurrentBlock(
						type as TextBlock['type'],
						level ? (Number(level) as 1 | 2 | 3) : undefined
					);
				}}
			>
				<option value="paragraph">문단</option><option value="heading:1">제목 1</option><option
					value="heading:2">제목 2</option
				><option value="heading:3">제목 3</option><option value="bulletList">글머리 목록</option
				><option value="orderedList">번호 목록</option><option value="blockquote">인용문</option
				><option value="codeBlock">코드 블록</option>
			</select>
		</div>
		<div class="toolbar-group">
			<input
				aria-label="표 행 수"
				title="행"
				type="number"
				min="1"
				max="10"
				bind:value={tableRows}
				disabled={readonly}
			/>
			<input
				aria-label="표 열 수"
				title="열"
				type="number"
				min="1"
				max="10"
				bind:value={tableColumns}
				disabled={readonly}
			/>
			<button aria-label="표 삽입" disabled={readonly} onclick={addTable}>표 삽입</button>
		</div>
		<div class="toolbar-group">
			<button disabled={readonly} title="에디터 JSON 내보내기" onclick={downloadJson}>JSON 내보내기</button>
			<button disabled={readonly} title="에디터 JSON 불러오기" onclick={() => jsonInput?.click()}>JSON 불러오기</button>
			<input class="json-import-input" bind:this={jsonInput} type="file" accept="application/json,.json" onchange={(event) => importJson(event.currentTarget.files?.[0])} />
		</div>
		<div class="selection-summary" aria-live="polite">{selectionSummary}</div>
		<details class="shortcut-guide">
			<summary>단축키</summary>
			<div>
				<strong>기본 편집</strong>
				<span><kbd>Ctrl/Cmd+B</kbd> 굵게</span>
				<span><kbd>Ctrl/Cmd+I</kbd> 기울임</span>
				<span><kbd>Ctrl/Cmd+U</kbd> 밑줄</span>
				<span><kbd>Ctrl/Cmd+Z</kbd> 실행 취소</span>
				<span><kbd>Ctrl/Cmd+Shift+Z</kbd> 다시 실행</span>
				<strong>아우라 표시</strong>
				<span><kbd>Ctrl/Cmd+Alt+Q</kbd> 물어봤음 체크</span>
				<span><kbd>Ctrl/Cmd+Alt+H</kbd> 최근 형광색</span>
				<span><kbd>Ctrl/Cmd+Alt+1/2/3</kbd> 살구/노랑/주황</span>
				<span><kbd>Ctrl/Cmd+Alt+C</kbd> 최근 글자색</span>
				<strong>문단</strong>
				<span><kbd>Tab / Shift+Tab</kbd> 들여쓰기/내어쓰기</span>
				<span><kbd>Enter</kbd> 새 문단 · 코드 블록에서는 줄바꿈</span>
			</div>
		</details>
	</div>

	<div
		class="text-editor-surface"
		bind:this={surface}
		role="textbox"
		tabindex="0"
		aria-multiline="true"
		aria-readonly={readonly}
		aria-label="문서 내용"
		contenteditable={!readonly}
		spellcheck="true"
		data-placeholder={placeholder}
		data-empty={empty}
		onbeforeinput={(event) => handleBeforeInput(event as InputEvent)}
		oninput={handleInput}
		onclick={rememberSelection}
		onkeyup={rememberSelection}
		onkeydown={handleKeydown}
		oncopy={handleCopy}
		onpaste={handlePaste}
		oncompositionstart={() => (isComposing = true)}
		oncompositionend={() => {
			isComposing = false;
			syncFromDom(true);
		}}
	></div>
</section>
