<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '../shared/api';
	import type { CourseProgress } from './progress';
	import type { Course } from './catalog';
	let { rule, track, progress }: { rule: any; track: any; progress: CourseProgress } = $props();
	let courses = $state<Course[]>([]),
		error = $state(''),
		ready = $state(false),
		equiv = $state<{ canon?: Record<string, string> }>({}),
		areas = $state<{ codes?: Record<string, string>; exceptions?: Record<string, string> }>({}),
		general = $state<any>(null);
	let loadVersion=0;
	async function load() {
		const version=++loadVersion;
		try {
			const data = await request<{
				courses: Course[];
				equivalencies: { canon?: Record<string, string> };
				areas: { codes?: Record<string, string>; exceptions?: Record<string, string> };
			}>('/student/completed-details');
			if(version!==loadVersion)return;
			courses = data.courses;
			equiv = data.equivalencies;
			areas = data.areas;
			ready = true;
		} catch (e) {
			error = String(e);
		}
	}
	$effect(() => {
		progress.completed.join(',');
		void load();
	});
	function canonical(c: string) {
		return equiv.canon?.[c] || c;
	}
	function completed(code: string) {
		return progress.completed.some((c) => canonical(c) === canonical(code));
	}
	function collect(value: any): { code: string; credits?: number; name?: string }[] {
		if (Array.isArray(value)) return value.flatMap(collect);
		if (value && typeof value === 'object') {
			if (value.code) return [value];
			return Object.values(value).flatMap(collect);
		}
		return [];
	}
	$effect(() => {
		const key = rule.general_key;
		general = null;
		let active=true;
		if (track.general && typeof key === 'string')
			void request(`/student/general/${key}`)
				.then((v) => {if(active)general = v;})
				.catch((e) => {if(active)error = String(e);});
		return()=>{active=false;};
	});
	function area(c: Course) {
		const chosen=c.personalTags?.filter(t=>t.kind==='general').map(t=>t.area)||[];
        const aliases:Record<string,string[]>={'수학':['math','mathematics'],'과학':['science'],'외국어':['foreign_language','language'],'글쓰기':['writing'],'베리타스':['veritas'],'지성의 열쇠':['keys','keys_to_intellectual_life']};
        const available=(general?.buckets || []).flatMap((b:any)=>b.areas||[]);
        return [...chosen.map(name=>available.find((a:string)=>a===name||aliases[name]?.includes(a))||name), areas.exceptions?.[c.sbjt_cd] || areas.codes?.[c.sbjt_cd.split('.')[0]] || ''];
	}
	const all = $derived(collect(track.required?.all || []));
	const pool = $derived(collect(track.required?.pool || []));
	function matches(c: Course, m: any) {
		return (
			!!m &&
			(!m.departments?.length || m.departments.some((d: string) => c.department.includes(d))) &&
			(!m.classifications?.length ||
				m.classifications.some((d: string) => c.classification.includes(d)))
		);
	}
	const counted = $derived(
		courses.filter(
			(c) =>
				c.personalTags?.some(t=>t.kind==='major_required' && t.major===rule.major) ||
				matches(c, rule.major_required_match) ||
				c.personalTags?.some(t=>t.kind==='major_select' && t.major===rule.major) ||
				matches(c, rule.major_select_match) ||
				collect(track.required).some((r) => canonical(r.code) === canonical(c.sbjt_cd))
		)
	);
	const creditSum = $derived(counted.reduce((sum, c) => sum + c.credits, 0));
	const requiredCredits = $derived(
		courses
			.filter(
				(c) =>
					c.personalTags?.some(t=>t.kind==='major_required' && t.major===rule.major) ||
				matches(c, rule.major_required_match) ||
					all.some((r) => canonical(r.code) === canonical(c.sbjt_cd))
			)
			.reduce((sum, c) => sum + c.credits, 0)
	);
	const poolDone = $derived(pool.filter((c) => completed(c.code)));
	const poolCredits = $derived(
		poolDone.reduce(
			(sum, c) =>
				sum +
				(c.credits ||
					courses.find((r) => canonical(r.sbjt_cd) === canonical(c.code))?.credits ||
					0),
			0
		)
	);
</script>

{#if error}<p role="alert">{error}</p>{:else if ready}<section
		class="progresses"
		aria-label="선택한 규정의 이수 현황"
	>
		<p>
			남은 전공 학점 <strong>{Math.max(0, (track.major_min_credits || 0) - creditSum)}학점</strong>
		</p>
		<label
			>시간표 기준 전공 학점 <strong>{creditSum} / {track.major_min_credits || 0}</strong><progress
				max={track.major_min_credits || 1}
				value={creditSum}
			></progress></label
		>{#if track.required_credits}<label
				>전공필수 학점 <strong>{requiredCredits} / {track.required_credits}</strong><progress
					max={track.required_credits}
					value={requiredCredits}
				></progress></label
			>{/if}{#if all.length}<label
				>필수과목 <strong>{all.filter((c) => completed(c.code)).length} / {all.length}과목</strong
				><progress max={all.length} value={all.filter((c) => completed(c.code)).length}
				></progress></label
			>{/if}{#if pool.length}<p>
				선택 과목 {poolDone.length} / {track.required?.min_courses || 0}과목 · {poolCredits} / {track
					.required?.min_credits || 0}학점
			</p>{/if}{#if general}<h3>교양 · {general.total_min}학점</h3>
			{#each general.buckets || [] as bucket}{@const done = courses.filter((c) =>
					area(c).some(a=>bucket.areas?.includes(a))
				)}{@const credits = done.reduce((sum, c) => sum + c.credits, 0)}<label
					>{bucket.name}<strong>{credits} / {bucket.min}학점</strong><progress
						max={bucket.min || 1}
						value={credits}
					></progress></label
				>{#if bucket.pick_min_areas}<p>
						서로 다른 영역 {new Set(done.map(area)).size} / {bucket.pick_min_areas}개
					</p>{/if}{/each}{#each general.notes || [] as note}<p>{note}</p>{/each}{/if}<small
			>종료된 학기의 시간표에서 미이수로 제외하지 않은 과목을 계산합니다. 성적·승인·중복 인정과
			자료에 없는 조건은 별도 확인이 필요합니다.</small
		>
	</section>{/if}

<style>
	.progresses {
		display: grid;
		gap: 14px;
		padding: 20px 0;
	}
	.progresses label {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		font-size: 15px;
		gap: 8px;
	}
	.progresses progress {
		width: 100%;
		height: 8px;
		accent-color: #529979;
	}
	.progresses small {
		opacity: 0.7;
	}
</style>
