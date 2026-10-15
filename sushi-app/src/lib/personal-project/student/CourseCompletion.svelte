<script lang="ts">
	import { courseState, type CourseProgress } from './progress';
	let {
		code,
		progress,
		onchange,
		busy = false
	}: {
		code: string;
		progress: CourseProgress;
		onchange?: (code: string) => void;
		busy?: boolean;
	} = $props();
	const state = $derived(courseState(progress, code));
</script>

{#if onchange}<button
		type="button"
		class={state}
		aria-label={`${code} 이수 완료`}
		aria-pressed={state === 'completed'}
		disabled={busy}
		onclick={() => onchange?.(code)}
		>{state === 'completed'
			? '✓ 이수 완료'
			: state === 'planned'
				? '◷ 수강 예정 · 완료 체크'
				: '이수 완료로 표시'}</button
	>{/if}

<style>
	button {
		font-size: 11px !important;
		padding: 5px 8px !important;
		border: 1px solid #cdd2dc;
		border-radius: 20px;
		background: #fff;
		color: #505967;
		white-space: normal;
	}
	.planned {
		background: #fff1cc;
		color: #735900;
		border-color: #dbc16b;
	}
	.completed {
		background: #dcf2e8;
		color: #146648;
		border-color: #6fac95;
	}
</style>
