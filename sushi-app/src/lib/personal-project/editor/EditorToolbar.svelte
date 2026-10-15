<script lang="ts">
	import type { Editor } from '@tiptap/core';
	import PersonalColorPicker from './PersonalColorPicker.svelte';
	let {
		editor,
		inTable = false,
		imageSelected = false,
		imageWidth = 100,
		isDrawing = false,
		indent,
		link,
		attach,
		draw,
		editDrawing,
		moveImage,
		sizeImage,
		alignImage,
		alignText,
		exportJSON,
		importJSON
	}: {
		editor?: Editor;
		inTable?: boolean;
		imageSelected?: boolean;
		imageWidth?: number;
		isDrawing?: boolean;
		indent: (out?: boolean) => unknown;
		link: () => void;
		attach: () => void;
		draw: () => void;
		editDrawing: () => void;
		moveImage: (direction: number) => void;
		sizeImage: (width: number) => void;
		alignImage: (align: string) => void;
		alignText: (align: string) => void;
		exportJSON: () => void;
		importJSON: () => void;
	} = $props();
	let textOpen = $state(false),
		colorOpen = $state(false),
		shortcuts = $state(false),
		palette = $state<'text' | 'highlight' | null>(null);
	const focus = () => editor?.chain().focus();
</script>

<div class="editor-toolbar" role="toolbar" aria-label="문서 편집 도구">
	<button
		type="button"
		class="square"
		aria-label="텍스트 서식"
		title="텍스트 서식"
		aria-expanded={textOpen}
		onclick={() => (textOpen = !textOpen)}>T</button
	>
	<div class="color-anchor">
		<button
			type="button"
			class="square"
			aria-label="색상 도구"
			title="색상 도구"
			aria-expanded={colorOpen}
			onclick={() => {
				colorOpen = !colorOpen;
				if (!colorOpen) palette = null;
			}}>C</button
		>
		{#if colorOpen}<div class="color-panel">
				<div class="color-tabs">
					<button type="button" onclick={() => (palette = 'text')}>글자색</button><button
						type="button"
						onclick={() => (palette = 'highlight')}>형광펜</button
					><button
						type="button"
						aria-label="색상 창 닫기"
						onclick={() => {
							colorOpen = false;
							palette = null;
						}}>×</button
					>
				</div>
				<PersonalColorPicker
					kind={palette || 'highlight'}
					onclose={() => {
						colorOpen = false;
						palette = null;
					}}
					onselect={(color) => {
						if (palette === 'text') {
							if (color) focus()?.setColor(color).run();
							else focus()?.unsetColor().run();
						} else {
							if (color) focus()?.setHighlight({ color }).run();
							else focus()?.unsetHighlight().run();
						}
						colorOpen = false;
						palette = null;
					}}
				/>
			</div>{/if}
	</div>
	<button
		type="button"
		aria-label="체크리스트"
		title="체크리스트"
		onclick={() => focus()?.toggleTaskList().run()}>☑</button
	>
	<button
		type="button"
		aria-label="토글 목록"
		title="토글 목록"
		onclick={() => focus()?.setDetails().run()}>▸</button
	>
	<button
		type="button"
		aria-label="코드 블록"
		title="코드 블록"
		onclick={() => focus()?.toggleCodeBlock().run()}>&lt;/&gt;</button
	>
	<button type="button" title="선택한 글자에 링크 연결·수정" onclick={link}>링크</button>
	<button type="button" onclick={attach}>사진·파일</button><button type="button" onclick={draw}
		>그림 메모</button
	>
	<button
		type="button"
		onclick={() => focus()?.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}>표</button
	>
	<button
		type="button"
		aria-label="실행 취소"
		title="실행 취소"
		onclick={() => focus()?.undo().run()}>↶</button
	><button
		type="button"
		aria-label="다시 실행"
		title="다시 실행"
		onclick={() => focus()?.redo().run()}>↷</button
	>
	<button type="button" onclick={importJSON}>JSON 가져오기</button>
	<button type="button" onclick={exportJSON}>JSON 내보내기</button>
	<div class="help-anchor">
		<button
			type="button"
			aria-label="단축키 보기"
			title="단축키 보기"
			aria-expanded={shortcuts}
			onclick={() => (shortcuts = !shortcuts)}>?</button
		>{#if shortcuts}<div class="shortcut-panel">
				<strong>단축키</strong>
				<p>
					Ctrl/Cmd+Alt+H · 최근 색상 형광펜<br />Ctrl/Cmd+B · 굵게<br />Ctrl/Cmd+I · 기울임<br />Ctrl/Cmd+Shift+B · 인용 전환<br />Tab /
					Shift+Tab · 들여쓰기 / 내어쓰기<br />Ctrl/Cmd+Z · 실행 취소<br />Ctrl/Cmd+Shift+Z · 다시
					실행
				</p>
				<button type="button" onclick={() => (shortcuts = false)}>닫기</button>
			</div>{/if}
	</div>
	{#if textOpen}<div class="text-tools" role="group" aria-label="텍스트 서식 도구">
			<button type="button" onclick={() => focus()?.toggleCodeBlock().run()}>코드</button>
			<button type="button" onclick={() => alignText('left')}>왼쪽 정렬</button>
			<button type="button" onclick={() => alignText('center')}>가운데 정렬</button>
			<button type="button" onclick={() => alignText('right')}>오른쪽 정렬</button>
			<button
				type="button"
				aria-label="굵게"
				title="굵게"
				onclick={() => focus()?.toggleBold().run()}><b>B</b></button
			><button
				type="button"
				aria-label="기울임"
				title="기울임"
				onclick={() => focus()?.toggleItalic().run()}><i>I</i></button
			><button
				type="button"
				aria-label="제목"
				title="제목"
				onclick={() => focus()?.toggleHeading({ level: 2 }).run()}>H</button
			><button
				type="button"
				aria-label="목록"
				title="목록"
				onclick={() => focus()?.toggleBulletList().run()}>• ≡</button
			><button
				type="button"
				aria-label="번호"
				title="번호"
				onclick={() => focus()?.toggleOrderedList().run()}>1. ≡</button
			><button
				type="button"
				aria-label="인용"
				title="인용 · Ctrl/Cmd+Shift+B"
				onclick={() => focus()?.toggleBlockquote().run()}>❝</button
			><button
				type="button"
				aria-label="들여쓰기"
				title="들여쓰기"
				onclick={() => {
					editor?.commands.focus();
					indent();
				}}>⇥</button
			><button
				type="button"
				aria-label="내어쓰기"
				title="내어쓰기"
				onclick={() => {
					editor?.commands.focus();
					indent(true);
				}}>⇤</button
			>
		</div>{/if}
	{#if inTable}<div class="context-tools">
			<button type="button" onclick={() => focus()?.addRowAfter().run()}>행 추가</button><button
				type="button"
				onclick={() => focus()?.addColumnAfter().run()}>열 추가</button
			><button type="button" onclick={() => focus()?.deleteRow().run()}>행 삭제</button><button
				type="button"
				onclick={() => focus()?.deleteColumn().run()}>열 삭제</button
			><button type="button" onclick={() => focus()?.deleteTable().run()}>표 삭제</button>
		</div>{/if}
	{#if imageSelected}<div class="context-tools" role="group" aria-label="이미지 객체 도구">
			<small>끌어서 이동</small><button
				type="button"
				aria-label="객체 위로"
				onclick={() => moveImage(-1)}>↑</button
			><button type="button" aria-label="객체 아래로" onclick={() => moveImage(1)}>↓</button><label
				>크기<input
					type="range"
					min="15"
					max="100"
					value={imageWidth}
					oninput={(e) => sizeImage(Number(e.currentTarget.value))}
				/></label
			><button type="button" onclick={() => alignImage('left')}>왼쪽</button><button
				type="button"
				onclick={() => alignImage('center')}>가운데</button
			><button type="button" onclick={() => alignImage('right')}>오른쪽</button
			>{#if isDrawing}<button type="button" onclick={editDrawing}>그림 수정</button>{/if}
		</div>{/if}
</div>

<style>
	.editor-toolbar {
		display: flex;
		gap: 4px;
		flex-wrap: wrap;
		align-items: center;
		padding: 7px;
		border-bottom: 1px solid #8884;
		position: sticky;
		top: var(--editor-toolbar-top, 0px);
		z-index: 20;
		background: var(--surface, #fff);
		border-radius: 10px 10px 0 0;
	}
	button {
		border: 1px solid #8884;
		background: transparent;
		border-radius: 4px;
		min-height: 30px;
		padding: 3px 7px;
		color: inherit;
		font-size: 13px;
		cursor: pointer;
	}
	.square {
		width: 32px;
		font-weight: 700;
	}
	.color-anchor,
	.help-anchor {
		position: static;
	}
	.color-panel,
	.shortcut-panel {
		position: absolute;
		top: 100%;
		left: 8px;
		max-width: calc(100% - 16px);
		width: 260px;
		z-index: 50;
		background: var(--surface, #fff);
		color: var(--text, #25262b);
		border: 1px solid #8885;
		border-radius: 8px;
		box-shadow: 0 8px 28px #0003;
		padding: 10px;
	}
	.color-tabs {
		display: flex;
		gap: 6px;
	}
	.color-tabs button:last-child {
		margin-left: auto;
	}
	.text-tools,
	.context-tools {
		display: flex;
		gap: 5px;
		align-items: center;
		flex-wrap: wrap;
		flex-basis: 100%;
	}
	.context-tools label {
		display: flex;
		align-items: center;
		font-size: 12px;
		gap: 4px;
	}
	.context-tools input {
		width: 90px;
	}
	.shortcut-panel {
		font-size: 12px;
		line-height: 1.8;
	}
	.color-panel :global(.swatches) {
		display: flex;
		gap: 8px;
		margin: 7px 0;
	}
	.color-panel :global(.swatch) {
		width: 26px;
		height: 26px;
		min-height: 26px;
		padding: 0;
		border-radius: 50%;
		background: var(--swatch);
	}
	.color-panel :global(p) {
		font-size: 12px;
		margin: 8px 0 3px;
	}
	.color-panel :global(label) {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 12px;
	}
	.color-panel :global(input[type='color']) {
		width: 32px;
		height: 26px;
		padding: 0;
		border: 0;
	}
	.color-panel :global(.popover-actions) {
		display: flex;
		gap: 8px;
		margin-top: 8px;
	}
	.color-panel :global(button) {
		border: 1px solid #8884;
		border-radius: 4px;
		padding: 4px 7px;
		background: transparent;
		color: inherit;
	}
	.color-panel :global(.swatch) {
		background: var(--swatch);
	}
</style>
