<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { Editor, Node, mergeAttributes } from '@tiptap/core';
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
	import { Plugin, PluginKey } from '@tiptap/pm/state';
	import { Decoration, DecorationSet } from '@tiptap/pm/view';
	import { createDocument, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';
	import { toRich, fromRich } from './document';
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
	let expanded = $state(!untrack(() => compact));
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
	function toggleQuestion() {
		if (!editor || readonly) return;
		const from = editor.state.selection.$from;
		for (let d = from.depth; d > 0; d--) {
			const id = from.node(d).attrs.id;
			if (id) {
				onquestionchange?.(id, !questionChecks[id]);
				return;
			}
		}
	}
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
					if (!onquestionchange && !Object.keys(questionChecks).length)
						return DecorationSet.create(state.doc, dec);
					state.doc.descendants((node, pos) => {
						const id = node.attrs.id;
						if (node.isTextblock && id) {
							dec.push(
								Decoration.widget(
									pos + 1,
									() => {
										const b = document.createElement('button');
										b.className = 'question-check';
										b.contentEditable = 'false';
										b.type = 'button';
										b.disabled = readonly;
										b.textContent = questionChecks[id] ? '☑' : '☐';
										b.setAttribute('aria-label', checkLabel);
										b.setAttribute('aria-pressed', String(!!questionChecks[id]));
										b.onmousedown = (e) => e.preventDefault();
										b.onclick = () => onquestionchange?.(id, !questionChecks[id]);
										return b;
									},
									{ key: `${id}:${!!questionChecks[id]}`, side: -1 }
								)
							);
						}
					});
					return DecorationSet.create(state.doc, dec);
				}
			}
		});
		editor = new Editor({
			element: surface,
			extensions: [
				StarterKit,
				Markdown,
				TableKit.configure({ table: { resizable: true } }),
				TaskList,
				TaskItem.configure({ nested: true }),
				Details.configure({ persist: true }),
				DetailsContent,
				DetailsSummary,
				Image,
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
					if ((event.ctrlKey || event.metaKey) && event.altKey && event.code === 'KeyQ') {
						event.preventDefault();
						toggleQuestion();
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
				if (asset.mimeType.startsWith('image/'))
					editor?.chain().focus().setImage({ src: asset.url, alt: asset.name }).run();
				else
					editor
						?.chain()
						.focus()
						.insertContent({ type: 'attachment', attrs: { href: asset.url, name: asset.name } })
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
	{#if !readonly}<div class="tools" role="toolbar" aria-label="문서 편집 도구">
			<button type="button" onclick={() => (expanded = !expanded)} aria-expanded={expanded}
				>서식 {expanded ? '접기' : '열기'}</button
			>
			<button type="button" onclick={() => editor?.chain().focus().toggleTaskList().run()}
				>☑ 체크리스트</button
			>
			<button
				type="button"
				onclick={() => editor?.chain().focus().undo().run()}
				aria-label="실행 취소">↶</button
			><button
				type="button"
				onclick={() => editor?.chain().focus().redo().run()}
				aria-label="다시 실행">↷</button
			>
			{#if expanded}<button type="button" onclick={() => editor?.chain().focus().toggleBold().run()}
					><b>굵게</b></button
				><button type="button" onclick={() => editor?.chain().focus().toggleItalic().run()}
					><i>기울임</i></button
				><button
					type="button"
					onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}>제목</button
				><button type="button" onclick={() => editor?.chain().focus().toggleBulletList().run()}
					>목록</button
				><button type="button" onclick={() => editor?.chain().focus().toggleOrderedList().run()}
					>번호</button
				><button type="button" onclick={() => editor?.chain().focus().toggleBlockquote().run()}
					>인용</button
				><button type="button" onclick={() => editor?.chain().focus().setDetails().run()}
					>토글</button
				>
				<label
					>글자색 <input
						type="color"
						value="#25262b"
						oninput={(e) => editor?.chain().focus().setColor(e.currentTarget.value).run()}
					/></label
				><label
					>형광펜 <input
						type="color"
						value="#fff3bf"
						oninput={(e) =>
							editor?.chain().focus().setHighlight({ color: e.currentTarget.value }).run()}
					/></label
				>
				<button
					type="button"
					onclick={() => {
						const href = prompt('링크 주소');
						if (href && /^https?:\/\//i.test(href)) editor?.chain().focus().setLink({ href }).run();
					}}>링크</button
				>
				<button type="button" onclick={() => input.click()}>사진·파일</button><button
					type="button"
					onclick={() =>
						editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
					>표</button
				>
				<button type="button" onclick={() => editor?.chain().focus().addRowAfter().run()}
					>행 추가</button
				><button type="button" onclick={() => editor?.chain().focus().addColumnAfter().run()}
					>열 추가</button
				><button type="button" onclick={() => editor?.chain().focus().deleteRow().run()}
					>행 삭제</button
				><button type="button" onclick={() => editor?.chain().focus().deleteColumn().run()}
					>열 삭제</button
				><button type="button" onclick={() => editor?.chain().focus().deleteTable().run()}
					>표 삭제</button
				>{/if}
		</div>{/if}
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

<style>
	.personal-editor {
		border: 1px solid var(--border, #ccd0d8);
		border-radius: 10px;
		background: var(--surface, #fff);
		color: var(--text, #25262b);
		overflow: hidden;
	}
	.tools {
		display: flex;
		flex-wrap: wrap;
		gap: 5px;
		padding: 8px;
		border-bottom: 1px solid var(--border, #ddd);
		align-items: center;
	}
	.tools button {
		font-size: 14px;
		min-height: 32px;
		padding: 4px 9px;
		border: 1px solid var(--border, #ddd);
		border-radius: 5px;
		background: transparent;
		color: inherit;
		cursor: pointer;
	}
	.tools label {
		display: flex;
		gap: 4px;
		align-items: center;
		font-size: 14px;
	}
	.tools input {
		width: 26px;
		height: 26px;
		padding: 0;
		border: 0;
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
		border-left: 2px solid #adb2be;
		padding: 8px;
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
		content: '▸';
	}
	.personal-editor :global([data-type='details'].is-open > button:before) {
		content: '▾';
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
