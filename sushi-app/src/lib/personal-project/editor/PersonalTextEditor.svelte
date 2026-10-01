<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { Editor, Node, Extension, mergeAttributes } from '@tiptap/core';
	import StarterKit from '@tiptap/starter-kit';
	import { Markdown } from '@tiptap/markdown';
	import { TableKit } from '@tiptap/extension-table';
	import TaskList from '@tiptap/extension-task-list';
	import TaskItem from '@tiptap/extension-task-item';
	import { Details, DetailsContent, DetailsSummary } from '@tiptap/extension-details';
	import Image from '@tiptap/extension-image';
	import Highlight from '@tiptap/extension-highlight';
	import { TextStyleKit } from '@tiptap/extension-text-style';
	import Placeholder from '@tiptap/extension-placeholder';
	import UniqueID from '@tiptap/extension-unique-id';
	import { Plugin, PluginKey, NodeSelection } from '@tiptap/pm/state';
	import { Decoration, DecorationSet } from '@tiptap/pm/view';
	import { createDocument, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import { toRich, fromRich } from './document';
	import EditorToolbar from './EditorToolbar.svelte';
	import DrawingMemo from './DrawingMemo.svelte';
	import type { Stroke } from '../pdf/model';
	import { uploadResource } from '../resources/api';
	let {
		initialValue = null,
		readonly = false,
		placeholder = '내용을 입력하세요…',
		onchange,
		questionChecks = {},
		onquestionchange,
		checkLabel = '물어봤음',
		compact = false,
		allowFolding = false,
		foldedBlocks = {},
		onfoldchange,
		boardId
	}: {
		initialValue?: EditorDocument | null;
		readonly?: boolean;
		placeholder?: string;
		onchange?: (d: EditorDocument) => void;
		questionChecks?: Record<string, boolean>;
		onquestionchange?: (id: string, checked: boolean) => void;
		checkLabel?: string;
		compact?: boolean;
		allowFolding?: boolean;
		foldedBlocks?: Record<string, boolean>;
		onfoldchange?: (id: string, closed: boolean) => void;
		boardId?: number;
	} = $props();
	let surface: HTMLDivElement;
	let editor = $state.raw<Editor>();

	let inTable = $state(false);

	let imageSelected = $state(false),
		imageAttrs = $state<Record<string, any>>({});
	let drawingOpen = $state(false),
		drawingInitial = $state<Stroke[]>([]),
		drawingPosition: number | null = null;
	let drawingGeneration = 0;
	const ObjectImage = Image.extend({
		draggable: true,
		addAttributes() {
			return {
				...this.parent?.(),
				widthPct: {
					default: 100,
					parseHTML: (el) => Number(el.dataset.widthPct) || 100,
					renderHTML: (attrs) => ({
						'data-width-pct': attrs.widthPct,
						style:
							'width:' +
							Math.max(15, Math.min(100, Number(attrs.widthPct) || 100)) +
							'%;height:auto;'
					})
				},
				objectAlign: {
					default: 'left',
					parseHTML: (el) => el.dataset.objectAlign || 'left',
					renderHTML: (attrs) => ({
						'data-object-align': attrs.objectAlign,
						style:
							attrs.objectAlign === 'right'
								? 'margin-left:auto;margin-right:0;'
								: attrs.objectAlign === 'center'
									? 'margin-left:auto;margin-right:auto;'
									: 'margin-left:0;margin-right:auto;'
					})
				},
				drawing: { default: null, renderHTML: () => ({}) }
			};
		}
	});
	function syncSelection(e: Editor) {
		inTable = e.isActive('table');
		imageSelected =
			e.state.selection instanceof NodeSelection && e.state.selection.node.type.name === 'image';
		imageAttrs = imageSelected ? e.getAttributes('image') : {};
	}
	function moveImage(direction: number) {
		if (!editor || !(editor.state.selection instanceof NodeSelection)) return;
		const sel = editor.state.selection;
		if (sel.node.type.name !== 'image') return;
		const index = sel.$from.index(),
			parent = sel.$from.parent,
			next = index + direction;
		if (next < 0 || next >= parent.childCount) return;
		const target =
			direction < 0
				? sel.from - parent.child(next).nodeSize
				: sel.from + parent.child(next).nodeSize;
		const tr = editor.state.tr.delete(sel.from, sel.to).insert(target, sel.node);
		tr.setSelection(NodeSelection.create(tr.doc, target));
		editor.view.dispatch(tr.scrollIntoView());
		editor.commands.focus();
	}
	function openDrawing(edit = false) {
		drawingGeneration = generation;
		drawingPosition = edit && editor ? editor.state.selection.from : null;
		drawingInitial =
			edit && Array.isArray(imageAttrs.drawing)
				? structuredClone($state.snapshot(imageAttrs.drawing))
				: [];
		drawingOpen = true;
	}
	export function openDrawingMemo() {
		openDrawing();
	}
	async function saveDrawing(file: File, strokes: Stroke[]) {
		const scope = drawingGeneration;
		if (scope !== generation || !editor)
			throw Error('문서가 바뀌었습니다. 현재 문서에 다시 첨부해주세요.');
		const asset = await uploadResource(file, boardId);
		if (scope !== generation || !editor)
			throw Error('문서가 바뀌었습니다. 현재 문서에 다시 첨부해주세요.');
		const attrs = { src: asset.url, alt: '그림 메모', drawing: strokes };
		if (
			drawingPosition !== null &&
			editor.state.doc.nodeAt(drawingPosition)?.type.name === 'image'
		) {
			const node = editor.state.doc.nodeAt(drawingPosition)!;
			editor.view.dispatch(
				editor.state.tr.setNodeMarkup(drawingPosition, undefined, { ...node.attrs, ...attrs })
			);
		} else
			editor
				.chain()
				.focus()
				.insertContentAt(editor.state.selection.to, [
					{ type: 'image', attrs },
					{ type: 'paragraph' }
				])
				.run();
		drawingOpen = false;
	}

	const BlockLayout = Extension.create({
		name: 'blockLayout',
		addGlobalAttributes() {
			return [
				{
					types: ['paragraph', 'heading', 'codeBlock', 'details'],
					attributes: {
						indent: {
							default: 0,
							parseHTML: (el) => Math.min(8, Math.max(0, Number(el.dataset.indent) || 0)),
							renderHTML: (attrs) => ({
								'data-indent': attrs.indent,
								style: `margin-left:${attrs.indent * 24}px`
							})
						},
						questionMarked: {
							default: false,
							parseHTML: (el) => el.dataset.questionMarked === 'true',
							renderHTML: (attrs) =>
								attrs.questionMarked ? { 'data-question-marked': 'true' } : {}
						}
					}
				}
			];
		}
	});
	function indentBlock(out = false) {
		if (!editor) return false;
		if (editor.isActive('table'))
			return out ? editor.commands.goToPreviousCell() : editor.commands.goToNextCell();
		const list = editor.isActive('taskItem') ? 'taskItem' : 'listItem';
		if (editor.isActive(list))
			return out ? editor.commands.liftListItem(list) : editor.commands.sinkListItem(list);
		if (editor.isActive('codeBlock')) {
			if (!out) return editor.commands.insertContent('  ');
			const { from } = editor.state.selection;
			if (editor.state.doc.textBetween(Math.max(0, from - 2), from) === '  ')
				return editor.commands.deleteRange({ from: from - 2, to: from });
			return true;
		}
		const type = editor.isActive('detailsSummary')
			? 'details'
			: editor.isActive('heading')
				? 'heading'
				: 'paragraph';
		return editor.commands.updateAttributes(type, {
			indent: Math.min(8, Math.max(0, (editor.getAttributes(type).indent || 0) + (out ? -1 : 1)))
		});
	}
	function link() {
		if (!editor) return;
		const href = prompt(
			'선택한 글자에 연결할 https:// 주소 (비우면 링크 제거)',
			editor.getAttributes('link').href || ''
		);
		if (href === null) return;
		if (!href.trim()) {
			editor.chain().focus().extendMarkRange('link').unsetLink().run();
			return;
		}
		if (!/^https?:\/\//i.test(href.trim())) {
			error = 'http:// 또는 https:// 주소를 입력해주세요.';
			return;
		}
		if (editor.state.selection.empty && !editor.isActive('link'))
			editor
				.chain()
				.focus()
				.insertContent({
					type: 'text',
					text: href.trim(),
					marks: [{ type: 'link', attrs: { href: href.trim() } }]
				})
				.run();
		else editor.chain().focus().extendMarkRange('link').setLink({ href: href.trim() }).run();
	}

	let error = $state('');
	let uploadProgress = $state<number | null>(null);
	let failedFile = $state<File | null>(null);
	let input: HTMLInputElement;
	let base = untrack(() => normalizeDocument(initialValue)),
		lastInitial = untrack(() => initialValue);
	let generation = 0;
	const checksKey = new PluginKey('questionChecks');
	const Attachment = Node.create({
		name: 'attachment',
		group: 'block',
		atom: true,
		addAttributes() {
			return { href: { default: '' }, name: { default: '첨부파일' } };
		},
		parseHTML() {
			return [{ tag: 'a[data-attachment]' }];
		},
		renderHTML({ HTMLAttributes }) {
			return [
				'a',
				mergeAttributes(HTMLAttributes, {
					href: /^(https?:\/\/|\/api\/personal\/resources\/)/i.test(HTMLAttributes.href || '')
						? HTMLAttributes.href
						: '#',
					'data-attachment': '',
					target: '_blank',
					rel: 'noopener'
				}),
				HTMLAttributes.name
			];
		}
	});

	function refreshChecks() {
		if (editor && !editor.isDestroyed)
			editor.view.dispatch(editor.state.tr.setMeta(checksKey, true));
	}
	onMount(() => {
		const checkPlugin = new Plugin({
			key: checksKey,
			props: {
				decorations(state) {
					const dec: Decoration[] = [];
					if (allowFolding) {
						const headings: { level: number; closed: boolean }[] = [];
						state.doc.forEach((node, pos) => {
							const id = node.attrs.id;
							const heading = node.type.name === 'heading';
							if (heading) {
								while (headings.length && headings.at(-1)!.level >= node.attrs.level)
									headings.pop();
							}
							if (headings.some((h) => h.closed))
								dec.push(Decoration.node(pos, pos + node.nodeSize, { style: 'display:none' }));
							if (heading && id) {
								const closed = !!foldedBlocks[id];
								dec.push(
									Decoration.widget(
										pos + 1,
										() => {
											const b = document.createElement('button');
											b.type = 'button';
											b.contentEditable = 'false';
											b.className = 'note-fold';
											b.textContent = closed ? '▸' : '▾';
											b.setAttribute('aria-expanded', String(!closed));
											b.setAttribute(
												'aria-label',
												node.textContent + ' ' + (closed ? '펼치기' : '접기')
											);
											b.onmousedown = (e) => e.preventDefault();
											b.onclick = () => {
												foldedBlocks = { ...foldedBlocks, [id]: !closed };
												onfoldchange?.(id, !closed);
												refreshChecks();
											};
											return b;
										},
										{ key: `fold:${id}:${closed}`, side: -1 }
									)
								);
								headings.push({ level: node.attrs.level, closed });
							}
						});
					}

					return DecorationSet.create(state.doc, dec);
				}
			}
		});
		editor = new Editor({
			element: surface,
			extensions: [
				StarterKit,
				BlockLayout,
				Markdown,
				TableKit.configure({ table: { resizable: true } }),
				TaskList,
				TaskItem.configure({ nested: true }),
				Details.configure({ persist: true }),
				DetailsContent,
				DetailsSummary,
				ObjectImage,
				Highlight.configure({ multicolor: true }),
				TextStyleKit,
				Placeholder.configure({ placeholder }),
				UniqueID.configure({
					types: [
						'paragraph',
						'heading',
						'codeBlock',
						'table',
						'tableCell',
						'detailsSummary',
						'image'
					]
				}),
				Attachment
			],
			content: toRich(base),
			editable: !readonly,
			editorProps: {
				attributes: {
					class: 'personal-editor-surface',
					role: 'textbox',
					'aria-label': placeholder,
					'aria-multiline': 'true'
				},
				handleKeyDown: (_view, event) => {
					if (readonly) return false;
					if (
						(event.ctrlKey || event.metaKey) &&
						event.shiftKey &&
						!event.altKey &&
						event.code === 'KeyB'
					) {
						event.preventDefault();
						editor?.chain().focus().toggleBlockquote().run();
						return true;
					}
					if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey) {
						event.preventDefault();
						indentBlock(event.shiftKey);
						return true;
					}

					if (
						(event.ctrlKey || event.metaKey) &&
						event.altKey &&
						['Digit1', 'Digit2', 'Digit3', 'KeyH'].includes(event.code)
					) {
						event.preventDefault();
						editor
							?.chain()
							.focus()
							.toggleHighlight({
								color:
									(
										{ Digit1: '#ffd8a8', Digit2: '#fff3bf', Digit3: '#ffc078' } as Record<
											string,
											string
										>
									)[event.code] || '#fff3bf'
							})
							.run();
						return true;
					}
					return false;
				},
				handlePaste: (_view, event) => {
					const files = Array.from(event.clipboardData?.files || []);
					if (!files.length) {
						const plain = event.clipboardData?.getData('text/plain') || '';
						if (
							!event.clipboardData?.getData('text/html') &&
							/^(?:#{1,6} |[-*] |\d+\. |>|\|)/m.test(plain)
						) {
							event.preventDefault();
							editor?.commands.insertContent(plain, { contentType: 'markdown' });
							return true;
						}
						return false;
					}
					event.preventDefault();
					void attach(files);
					return true;
				},
				handleDrop: (_view, event) => {
					const files = Array.from(event.dataTransfer?.files || []);
					if (!files.length) return false;
					event.preventDefault();
					void attach(files);
					return true;
				}
			},
			onSelectionUpdate: ({ editor: e }) => {
				syncSelection(e);
			},
			onTransaction: ({ editor: e }) => {
				syncSelection(e);
			},
			onUpdate: ({ editor: e }) => {
				base = fromRich(e.getJSON(), base);
				onchange?.(base);
			}
		});
		editor.registerPlugin(checkPlugin);
		return () => {
			generation++;
			editor?.destroy();
		};
	});
	$effect(() => {
		if (editor && initialValue !== lastInitial) {
			lastInitial = initialValue;
			generation++;
			base = normalizeDocument(initialValue);
			editor.commands.setContent(toRich(base), { emitUpdate: false });
			refreshChecks();
		}
	});
	$effect(() => {
		questionChecks;
		foldedBlocks;
		allowFolding;
		refreshChecks();
	});
	$effect(() => {
		editor?.setEditable(!readonly);
	});
	export function getJSON() {
		return editor ? fromRich(editor.getJSON(), base) : base;
	}
	export function setJSON(value: unknown) {
		base = normalizeDocument(value);
		editor?.commands.setContent(toRich(base));
	}
	export function clear() {
		setJSON(createDocument());
	}
	export function focus() {
		editor?.commands.focus();
	}
	async function attach(files: File[]) {
		const scope = generation;
		for (const file of files) {
			try {
				error = '';
				uploadProgress = 0;
				const asset = await uploadResource(file, boardId, (p) => (uploadProgress = p));
				if (scope !== generation) return;
				if (editor)
					editor
						.chain()
						.focus()
						.insertContentAt(editor.state.selection.to, [
							asset.mimeType.startsWith('image/')
								? { type: 'image', attrs: { src: asset.url, alt: asset.name } }
								: { type: 'attachment', attrs: { href: asset.url, name: asset.name } },
							{ type: 'paragraph' }
						])
						.run();
				failedFile = null;
			} catch (e) {
				failedFile = file;
				error = e instanceof Error ? e.message : '업로드 실패';
			} finally {
				uploadProgress = null;
			}
		}
	}
</script>

<div class="personal-editor" class:compact>
	{#if !readonly}<EditorToolbar
			{editor}
			{inTable}
			{imageSelected}
			imageWidth={imageAttrs.widthPct || 100}
			isDrawing={Array.isArray(imageAttrs.drawing)}
			indent={indentBlock}
			{link}
			attach={() => input.click()}
			draw={() => openDrawing()}
			editDrawing={() => openDrawing(true)}
			{moveImage}
			sizeImage={(widthPct) =>
				editor?.chain().focus().updateAttributes('image', { widthPct }).run()}
			alignImage={(objectAlign) =>
				editor?.chain().focus().updateAttributes('image', { objectAlign }).run()}
		/>{/if}
	<input
		hidden
		type="file"
		multiple
		bind:this={input}
		onchange={(e) => {
			void attach(Array.from(e.currentTarget.files || []));
			e.currentTarget.value = '';
		}}
	/>
	{#if uploadProgress !== null}<p role="status">파일 업로드 {uploadProgress}%</p>{/if}{#if error}<p
			role="alert"
		>
			{error}
			{#if failedFile}<button type="button" onclick={() => failedFile && attach([failedFile])}
					>다시 업로드</button
				>{/if}
		</p>{/if}
	<div bind:this={surface}></div>
</div>

{#if drawingOpen}<DrawingMemo
		initial={drawingInitial}
		onsave={saveDrawing}
		oncancel={() => (drawingOpen = false)}
	/>{/if}

<style>
	.personal-editor :global(img.ProseMirror-selectednode) {
		outline: 2px solid #6686a1;
		outline-offset: 3px;
	}

	.personal-editor {
		border: 1px solid var(--border, #ccd0d8);
		border-radius: 10px;
		background: var(--surface, #fff);
		color: var(--text, #25262b);
		overflow: visible;
	}
	.personal-editor :global(.tiptap) {
		min-height: 160px;
		padding: 16px;
		outline: none;
		font-size: 16px;
		line-height: 1.65;
		overflow-wrap: anywhere;
	}
	.compact :global(.tiptap) {
		min-height: 90px;
	}
	.personal-editor :global(.tiptap p) {
		margin: 4px 0;
	}
	.personal-editor :global(.tiptap table) {
		border-collapse: collapse;
		width: 100%;
		table-layout: fixed;
	}
	.personal-editor :global(.tiptap td),
	.personal-editor :global(.tiptap th) {
		border: 1px solid #b5bac5;
		padding: 8px;
		vertical-align: top;
		position: relative;
		min-width: 50px;
	}
	.personal-editor :global(.selectedCell:after) {
		content: '';
		position: absolute;
		inset: 0;
		background: #7b61ff22;
		pointer-events: none;
	}
	.personal-editor :global(.column-resize-handle) {
		position: absolute;
		right: -2px;
		top: 0;
		bottom: 0;
		width: 4px;
		background: #8566cc;
	}
	.personal-editor :global(.tiptap img) {
		display: block;
		cursor: grab;
		max-width: 100%;
		height: auto;
	}
	.personal-editor :global(ul[data-type='taskList']) {
		list-style: none;
		padding-left: 4px;
	}
	.personal-editor :global(li[data-checked]) {
		display: flex;
		gap: 8px;
	}
	.personal-editor :global(li[data-checked] > div) {
		flex: 1;
	}
	.personal-editor :global(.question-check) {
		border: 0;
		background: transparent;
		color: inherit;
		cursor: pointer;
		padding: 0 7px 0 0;
	}
	.personal-editor :global([data-type='details']) {
		display: flex;
		gap: 8px;
		padding: 2px 0;
	}
	.personal-editor :global([data-type='details'] > div) {
		flex: 1;
	}
	.personal-editor :global([data-type='details'] > button) {
		width: 20px;
		border: 0;
		background: transparent;
	}
	.personal-editor :global([data-type='details'] > button:before) {
		content: '';
		display: inline-block;
		width: 0;
		height: 0;
		border-top: 5px solid transparent;
		border-bottom: 5px solid transparent;
		border-left: 7px solid currentColor;
		transition: transform 0.12s;
	}
	.personal-editor :global([data-type='details'].is-open > button:before) {
		transform: rotate(90deg);
	}
	.personal-editor :global(blockquote) {
		border-left: 3px solid #989aa9;
		padding-left: 12px;
	}
	.personal-editor :global(pre) {
		background: #20222a;
		color: #f1f1f7;
		padding: 12px;
		overflow: auto;
	}
	.personal-editor :global(.tiptap a) {
		text-decoration: underline;
	}
	.personal-editor :global(.tiptap .is-empty:first-child:before) {
		content: attr(data-placeholder);
		float: left;
		height: 0;
		color: #92959e;
		pointer-events: none;
	}
	.personal-editor :global(li[data-checked] > label) {
		flex: 0 0 auto;
		display: flex;
		align-items: center;
		margin: 4px 0;
		align-self: flex-start;
		min-height: 26px;
	}
	.personal-editor :global(li[data-checked] > div) {
		min-width: 0;
	}
	.personal-editor :global(.tiptap ul) {
		list-style: disc;
		padding-left: 1.4em;
	}
	.personal-editor :global(.tiptap ol) {
		list-style: decimal;
		padding-left: 1.4em;
	}
	.personal-editor :global(.tiptap ul:has(> li[data-checked])) {
		list-style: none;
		padding-left: 0;
	}
	.personal-editor :global(.note-fold) {
		border: 0;
		background: transparent;
		padding: 0 6px 0 0;
		color: inherit;
	}
</style>
