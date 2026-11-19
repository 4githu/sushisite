<script lang="ts">
	import { onMount } from 'svelte';
	import CourseTags from './CourseTags.svelte';
	import { request } from '../shared/api';
	import type { Course } from './catalog';
	import type { CourseProgress } from './progress';
	let { onchange }: { onchange: (p: CourseProgress) => void } = $props();
	let data = $state<{
			semesters: {
				term: string;
				label: string;
				finished: boolean;
				state?: 'completed' | 'current' | 'future';
				courses: Course[];
			}[];
			excluded: string[];
		} | null>(null),
		error = $state(''),
		busy = $state(false);
	async function load() {
		try {
			data = await request('/student/course-history');
		} catch (e) {
			error = String(e);
		}
	}
	onMount(() => {
		void load();
	});
	async function exclude(code: string, excluded: boolean) {
		busy = true;
		try {
			onchange(
				await request(`/student/transcript/exclusions/${encodeURIComponent(code)}`, {
					method: 'PUT',
					body: { excluded }
				})
			);
			await load();
		} catch (e) {
			error = String(e);
		} finally {
			busy = false;
		}
	}
	async function refreshTags() {
		await load();
		onchange(await request('/student/course-progress'));
	}
</script>

<details class="transcript" aria-labelledby="transcript-title">
	<summary class="transcript-heading">
		<div>
			<h2 id="transcript-title">계산 근거</h2>
		</div>
		<span class="semester-count">{data?.semesters.length || 0}개 학기</span>
	</summary>
	<div class="transcript-content">
		{#if error}<p role="alert">{error}</p>{/if}
		{#each data?.semesters || [] as semester}
			<section class="semester-card">
				<header>
					<div>
						<h3>{semester.label}</h3>
						<span>{semester.courses.length}과목</span>
					</div>
					<span class:past={semester.finished} class="semester-status">
						{semester.finished
							? '종료 학기 · 이수 반영'
							: semester.state === 'current'
								? '현재 학기 · 예상치'
								: '미래 학기 · 예상치'}
					</span>
				</header>
				<div class="course-list">
					{#each semester.courses as c}
						<article class="course-card">
							<div class="course-main">
								<div class="course-title">
									<strong>{c.name}</strong><span>{c.credits}학점</span>
									{#if !c.personalTags?.length}{#each c.classification.filter((value) => value !== '학사') as classification}<span class="classification-chip">{classification}</span>{/each}{/if}
									<CourseTags code={c.sbjt_cd} initial={c.personalTags} onchange={refreshTags} />
								</div>
								<small>{c.sbjt_cd}{c.department ? ` · ${c.department}` : ''}</small>
							</div>
							{#if semester.finished}
								<button
									class="exclude-button"
									disabled={busy}
									onclick={() => exclude(c.sbjt_cd, !data?.excluded.includes(c.sbjt_cd))}
									>{data?.excluded.includes(c.sbjt_cd)
										? '이수 계산에 포함'
										: '미이수로 제외'}</button
								>
							{/if}
						</article>
					{/each}
				</div>
			</section>
		{:else}
			<a class="empty-link" href="/personal-project/calendar/student/timetable">시간표 만들기</a>
		{/each}
	</div>
</details>

<style>
	.transcript {
		margin: 16px 0;
		padding: 18px;
		border: 1px solid #8883;
		border-radius: 14px;
		background: var(--surface, #fff);
	}
	.transcript-heading {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		list-style: none;
		cursor: pointer;
	}
	.transcript-heading::-webkit-details-marker {
		display: none;
	}
	.transcript-heading::after {
		content: '▾';
		color: #71717a;
		transition: transform 120ms ease;
	}
	.transcript[open] > .transcript-heading::after {
		transform: rotate(180deg);
	}
	.transcript-content {
		padding-top: 8px;
	}
	.transcript-heading h2,
	.semester-card h3 {
		margin: 0;
	}
	.semester-count,
	.semester-status {
		border-radius: 999px;
		padding: 5px 10px;
		background: #8882;
		font-size: 12px;
		white-space: nowrap;
	}
	p {
		font-size: 13px;
		line-height: 1.6;
		color: #666;
	}
	.semester-card {
		margin-top: 14px;
		padding: 14px;
		border: 1px solid #8883;
		border-radius: 12px;
		background: color-mix(in srgb, var(--surface, #fff) 94%, #888 6%);
	}
	.semester-card > header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 10px;
		margin-bottom: 12px;
	}
	.semester-card > header > div {
		display: flex;
		align-items: baseline;
		gap: 8px;
	}
	.semester-card > header > div > span,
	.course-main small {
		color: #71717a;
		font-size: 12px;
	}
	.semester-status.past {
		background: #16845a18;
		color: #16734f;
	}
	.course-list {
		display: flex;
		align-items: flex-start;
		flex-wrap: wrap;
		gap: 8px;
	}
	.course-card {
		display: flex;
		flex: 0 1 auto;
		flex-wrap: wrap;
		align-items: center;
		gap: 5px 8px;
		max-width: 100%;
		padding: 7px 10px;
		border: 1px solid #8883;
		border-radius: 9px;
		background: var(--surface, #fff);
	}
	.course-main {
		min-width: 120px;
		max-width: 100%;
	}
	.course-title {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-start;
		align-items: baseline;
		gap: 8px;
	}
	.classification-chip {
		border: 1px solid #d9dee5;
		border-radius: 999px;
		padding: 2px 8px;
		background: #f6f8fa;
		font-size: 11px;
		white-space: nowrap;
	}
	.course-title strong {
		font-size: 13px;
		line-height: 1.35;
	}
	.course-title span {
		font-size: 12px;
		white-space: nowrap;
		color: #52525b;
	}
	:global(.course-tags) {
		flex-basis: auto;
	}
	.exclude-button {
		white-space: nowrap;
		font-size: 12px;
	}
	.empty-link {
		display: inline-flex;
		align-items: center;
		min-height: 36px;
		padding: 0 12px;
		border: 1px solid #d6d8dd;
		border-radius: 8px;
		color: inherit;
		font-size: 13px;
		font-weight: 650;
		text-decoration: none;
	}
	@media (max-width: 560px) {
		.transcript {
			padding: 12px;
		}
		.semester-card > header {
			flex-direction: column;
		}
		.course-card {
			width: 100%;
		}
	}
</style>
