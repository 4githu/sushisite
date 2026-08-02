<script lang="ts">
	import TextEditorCard from '$lib/personal-project/editor/PersonalTextEditor.svelte';
	import type { EditorDocument } from '$lib/textediter/types';

	let {
		initialValue,
		readonly = false,
		placeholder = '내용을 입력하세요…',
		onchange,
		questionChecks = {},
		onquestionchange
	}: {
		initialValue: EditorDocument;
		readonly?: boolean;
		placeholder?: string;
		onchange?: (value: EditorDocument) => void;
		questionChecks?: Record<string, boolean>;
		onquestionchange?: (blockId: string, checked: boolean) => void;
	} = $props();

	let editor: TextEditorCard;

	export function getJSON() {
		return editor.getJSON();
	}

	export function focus() {
		editor.focus();
	}
</script>

<div role="group" aria-label="아우라 리포트 에디터">
	<TextEditorCard
		bind:this={editor}
		{initialValue}
		{readonly}
		{placeholder}
		{onchange}
		{questionChecks}
		{onquestionchange}
	/>
</div>
