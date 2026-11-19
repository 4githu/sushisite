<script lang="ts">
	import CourseTags from './CourseTags.svelte';
	import type { Course } from './catalog';
	let {
		course,
		classification,
		major,
		excluded = false,
		disabled = false,
		onexclude,
		onchange
	}: {
		course: Course;
		classification: string;
		major: string;
		excluded?: boolean;
		disabled?: boolean;
		onexclude: (excluded: boolean) => void;
		onchange?: () => void;
	} = $props();
</script>

<li class:excluded>
	<div class="course-label">
		<strong>{course.name}</strong>
		{#if classification}<span class="classification-chip">{classification}</span>{/if}
		<small>{course.sbjt_cd}</small>
	</div>
	<strong class="credits">{course.credits}학점</strong>
	<CourseTags code={course.sbjt_cd} initial={course.personalTags} {onchange} preferredMajor={major} />
	<button class="exclude" {disabled} onclick={() => onexclude(!excluded)}>
		{excluded ? '이 전공에 다시 반영' : '이 전공에서 제외'}
	</button>
</li>

<style>
	li {
		display: grid;
		grid-template-columns: minmax(180px, 1fr) auto;
		align-items: center;
		gap: 6px 10px;
		padding: 7px 0;
		border-bottom: 1px solid #8882;
	}
	li.excluded {
		opacity: 0.75;
	}
	.course-label {
		display: flex;
		align-items: baseline;
		flex-wrap: wrap;
		gap: 6px 8px;
		min-width: 0;
	}
	.course-label strong {
		font-size: 13px;
	}
	.course-label small {
		font-size: 11px;
		color: #727986;
	}
	.classification-chip {
		border: 1px solid #d9dee5;
		border-radius: 999px;
		padding: 2px 8px;
		background: #f6f8fa;
		font-size: 11px;
		white-space: nowrap;
	}
	.credits {
		font-size: 12px;
		white-space: nowrap;
	}
	:global(.course-tags) {
		grid-column: 1;
	}
	.exclude {
		grid-column: 2;
		grid-row: 2;
		font-size: 11px;
		white-space: nowrap;
	}
	@media (max-width: 600px) {
		li {
			grid-template-columns: minmax(0, 1fr) auto;
		}
	}
</style>
