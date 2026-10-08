<script lang="ts">
	import { onMount } from 'svelte';
	import CourseTags from './CourseTags.svelte';
	import { request } from '../shared/api';
	import type { Course } from './catalog';
	import type { CourseProgress } from './progress';
	let { onchange }: { onchange: (p: CourseProgress) => void } = $props();
	let data = $state<{
			semesters: { term: string; label: string; finished: boolean; courses: Course[] }[];
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
</script>

<details class="transcript">
	<summary>계산 근거 · 역대 시간표와 미이수 조정</summary>
	<p>
		종료일이 지난 학기의 수강 기록을 합산합니다. 낙제·수강 취소 등 실제 학점을 얻지 못한 과목은
		여기서 제외하세요. 진행 중·미래 학기와 탐색 초안은 합산하지 않습니다.
	</p>
	{#if error}<p role="alert">{error}</p>{/if}
	{#each data?.semesters || [] as semester}<details>
			<summary
				>{semester.label} · {semester.finished ? '지난 학기' : '진행 중·예정'} · {semester.courses
					.length}과목</summary
			>{#each semester.courses as c}<div>
					<span>{c.name} · {c.sbjt_cd} · {c.credits}학점</span>{#if semester.finished}<button
							disabled={busy}
							onclick={() => exclude(c.sbjt_cd, !data?.excluded.includes(c.sbjt_cd))}
							>{data?.excluded.includes(c.sbjt_cd) ? '계산에 다시 포함' : '미이수로 제외'}</button
						>{/if}
				</div><CourseTags code={c.sbjt_cd} initial={c.personalTags} onchange={async()=>{await load();onchange(await request('/student/course-progress'));}} />{/each}
		</details>{:else}<p>
			아직 저장한 내 시간표가 없습니다. 학기별 시간표를 만들면 이수 현황에 자동으로 연결됩니다.
		</p>{/each}
</details>

<style>
	.transcript {
		margin: 16px 0;
		border-block: 1px solid #8884;
		padding: 12px 0;
	}
	summary {
		cursor: pointer;
		font-weight: 600;
	}
	p {
		font-size: 13px;
		line-height: 1.6;
		color: #666;
	}
	div {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 8px 0;
		font-size: 13px;
	}
	button {
		white-space: nowrap;
	}
</style>
