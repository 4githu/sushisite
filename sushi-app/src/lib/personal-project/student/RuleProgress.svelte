<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '../shared/api';
	import type { CourseProgress } from './progress';
	import type { Course } from './catalog';
	import CourseEvidenceRow from './CourseEvidenceRow.svelte';
	let {
		ruleId,
		rule,
		track,
		progress,
		revision = 0,
		basis = 'current'
	}: {
		ruleId: string;
		rule: any;
		track: any;
		progress: CourseProgress;
		revision?: number;
		basis?: 'current' | 'future';
	} = $props();
	let courses = $state<Course[]>([]),
		currentTermCourses = $state<Course[]>([]),
		futureTermCourses = $state<Course[]>([]),
		error = $state(''),
		ready = $state(false),
		equiv = $state<{ canon?: Record<string, string> }>({}),
		areas = $state<{ codes?: Record<string, string>; exceptions?: Record<string, string> }>({}),
		general = $state<any>(null),
		excludedCodes = $state<string[]>([]),
		exclusionError = $state(''),
		exclusionBusy = $state(false);
	let loadVersion = 0;
	async function load() {
		const version = ++loadVersion;
		try {
			const data = await request<{
				courses: Course[];
				plannedCurrent?: Course[];
				plannedFuture?: Course[];
				equivalencies: { canon?: Record<string, string> };
				areas: { codes?: Record<string, string>; exceptions?: Record<string, string> };
				excludedForRule?: string[];
			}>(`/student/completed-details?rule_id=${encodeURIComponent(ruleId)}`);
			if (version !== loadVersion) return;
			courses = data.courses;
			currentTermCourses = data.plannedCurrent || [];
			futureTermCourses = data.plannedFuture || [];
			equiv = data.equivalencies;
			areas = data.areas;
			excludedCodes = data.excludedForRule || [];
			ready = true;
		} catch (e) {
			error = String(e);
		}
	}
	$effect(() => {
		progress.completed.join(',');
		revision;
		void load();
	});
	function canonical(c: string) {
		return equiv.canon?.[c] || c;
	}
	function excluded(c: Course) {
		return excludedCodes.includes(canonical(c.sbjt_cd));
	}
	async function setExcluded(c: Course, value: boolean) {
		exclusionBusy = true;
		exclusionError = '';
		try {
			await request(
				`/student/rules/${encodeURIComponent(ruleId)}/course-exclusions/${encodeURIComponent(c.sbjt_cd)}`,
				{ method: 'PUT', body: { excluded: value } }
			);
			const code = canonical(c.sbjt_cd);
			excludedCodes = value
				? [...new Set([...excludedCodes, code])]
				: excludedCodes.filter((item) => item !== code);
		} catch (e) {
			exclusionError = e instanceof Error ? e.message : '과목 분류 저장 실패';
		} finally {
			exclusionBusy = false;
		}
	}
	function inCalculation(code: string) {
		return includedCourses.some((c) => canonical(c.sbjt_cd) === canonical(code));
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
		let active = true;
		if (track.general && typeof key === 'string')
			void request(`/student/general/${key}`)
				.then((v) => {
					if (active) general = v;
				})
				.catch((e) => {
					if (active) error = String(e);
				});
		return () => {
			active = false;
		};
	});
	function area(c: Course) {
		const specific = c.personalTags?.filter((tag) => tag.major === rule.major) || [];
		const scoped = specific.length
			? specific
			: c.personalTags?.filter((tag) => tag.major === '*') || [];
		const chosen = scoped.filter((tag) => tag.kind === 'general').map((tag) => tag.area);
		const aliases: Record<string, string[]> = {
			수학: ['math', 'mathematics', 'stat'],
			과학: ['science', 'physics', 'chem', 'bio', 'earth'],
			외국어: ['foreign', 'foreign_language', 'language'],
			글쓰기: ['writing'],
			베리타스: ['veritas'],
			'지성의 열쇠': [
				'keys',
				'keys_to_intellectual_life',
				'culture',
				'history',
				'human',
				'scisense'
			]
		};
		const available = (general?.buckets || []).flatMap((b: any) => b.areas || []);
		const chosenAreas = chosen.flatMap((name) => {
			const matches = available.filter((a: string) => a === name || aliases[name]?.includes(a));
			return matches.length ? matches : [name];
		});
		if (chosen.length) return chosenAreas;
		if (scoped.some((tag) => tag.kind.startsWith('major'))) return [];
		// These catalog codes were mapped to the math area by prefix alone. They are not a
		// department-wide general-education equivalency; count them only after an explicit tag.
		if (['033.014', '033.015', 'F31.201', 'F31.202'].includes(c.sbjt_cd.toUpperCase())) return [];
		if (!c.classification?.includes('교양')) return [];
		return [areas.exceptions?.[c.sbjt_cd] || areas.codes?.[c.sbjt_cd.split('.')[0]] || ''];
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
	function belongsToMajor(c: Course) {
		return (
			c.personalTags?.some((t) => t.kind === 'major_required' && t.major === rule.major) ||
			matches(c, rule.major_required_match) ||
			c.personalTags?.some((t) => t.kind === 'major_select' && t.major === rule.major) ||
			matches(c, rule.major_select_match) ||
			collect(track.required).some((r) => canonical(r.code) === canonical(c.sbjt_cd))
		);
	}
	function majorClassification(c: Course) {
		const tag = c.personalTags?.find((t) => t.major === rule.major && t.kind.startsWith('major'));
		return tag?.kind === 'major_required' ? '전공필수' : tag ? '전공선택' : '';
	}
	function courseClassification(c: Course) {
		const majorClass = majorClassification(c);
		if (majorClass) return majorClass;
		const areas = area(c).filter(Boolean);
		if (areas.length) {
			const labels: Record<string, string> = {
				math: '수학', mathematics: '수학', stat: '통계', science: '과학', physics: '물리',
				chem: '화학', bio: '생명과학', earth: '지구과학', foreign: '외국어',
				foreign_language: '외국어', writing: '글쓰기', veritas: '베리타스',
				culture: '문화', history: '역사', human: '인문', scisense: '과학과기술'
			};
			return `교양 · ${areas.map((name) => labels[name] || name).join(' · ')}`;
		}
		if (matches(c, rule.major_required_match) || all.some((r) => canonical(r.code) === canonical(c.sbjt_cd)))
			return '전공필수';
		if (matches(c, rule.major_select_match)) return '전공선택';
		return c.classification?.filter((value) => value !== '학사').join(' · ') || '분류 없음';
	}
	function uniqueCourses(groups: Course[][]) {
		const unique = new Map<string, Course>();
		for (const course of groups.flat()) {
			const code = canonical(course.sbjt_cd);
			if (!unique.has(code)) unique.set(code, course);
		}
		return [...unique.values()];
	}
	const completedSubjects = $derived(uniqueCourses([courses]));
	const currentTermSubjects = $derived(
		uniqueCourses([currentTermCourses]).filter(
			(c) => !completedSubjects.some((done) => canonical(done.sbjt_cd) === canonical(c.sbjt_cd))
		)
	);
	const futureTermSubjects = $derived(
		uniqueCourses([futureTermCourses]).filter(
			(c) =>
				!completedSubjects.some((done) => canonical(done.sbjt_cd) === canonical(c.sbjt_cd)) &&
				!currentTermSubjects.some((current) => canonical(current.sbjt_cd) === canonical(c.sbjt_cd))
		)
	);
	const includedCourses = $derived(
		uniqueCourses(
			basis === 'future'
				? [completedSubjects, currentTermSubjects, futureTermSubjects]
				: [completedSubjects, currentTermSubjects]
			).filter((course) => !excluded(course))
	);
	const excludedSubjects = $derived(
		uniqueCourses([completedSubjects, currentTermSubjects, futureTermSubjects]).filter(excluded)
	);
	const counted = $derived(includedCourses.filter(belongsToMajor));
	const creditSum = $derived(counted.reduce((sum, c) => sum + c.credits, 0));
	const completedMajorCredits = $derived(
		courses.filter((c) => !excluded(c) && belongsToMajor(c)).reduce((sum, c) => sum + c.credits, 0)
	);
	const currentMajorSubjects = $derived(currentTermSubjects.filter((c) => !excluded(c) && belongsToMajor(c)));
	const futureMajorSubjects = $derived(futureTermSubjects.filter((c) => !excluded(c) && belongsToMajor(c)));
	const currentMajorCredits = $derived(currentMajorSubjects.reduce((sum, c) => sum + c.credits, 0));
	const futureMajorCredits = $derived(futureMajorSubjects.reduce((sum, c) => sum + c.credits, 0));
	const requiredCredits = $derived(
		includedCourses
			.filter(
				(c) =>
					c.personalTags?.some((t) => t.kind === 'major_required' && t.major === rule.major) ||
					matches(c, rule.major_required_match) ||
					all.some((r) => canonical(r.code) === canonical(c.sbjt_cd))
			)
			.reduce((sum, c) => sum + c.credits, 0)
	);
	const poolDone = $derived(pool.filter((c) => inCalculation(c.code)));
	const poolCredits = $derived(
		poolDone.reduce(
			(sum, c) =>
				sum +
				(c.credits ||
					includedCourses.find((r) => canonical(r.sbjt_cd) === canonical(c.code))?.credits ||
					0),
			0
		)
	);
</script>

{#if error}
	<p role="alert">{error}</p>
{:else if ready}
	<section class="progresses" aria-label="선택한 규정의 이수 현황">
		{#if exclusionError}<p role="alert">{exclusionError}</p>{/if}
		<p>
			선택 범위 기준 남은 전공 학점 <strong
				>{Math.max(0, (track.major_min_credits || 0) - creditSum)}학점</strong
			>
		</p>
		<details class="course-evidence">
			<summary
				>계산 근거 · 지난 학기 {completedMajorCredits}학점 · 현재 학기 예상 {currentMajorCredits}학점
				· 미래 예상 {futureMajorCredits}학점</summary
			>
			<div class="basis-groups">
				<div>
					<h4>지난 학기 이수 · {completedMajorCredits}학점</h4>
					<ul>
						{#each courses.filter((c) => !excluded(c) && belongsToMajor(c)) as c}<CourseEvidenceRow
							course={c}
							classification={courseClassification(c)}
							major={rule.major}
							disabled={exclusionBusy}
							onexclude={(value) => setExcluded(c, value)}
							onchange={() => void load()}
						/>{/each}
					</ul>
				</div>
				<div>
					<h4>현재 학기 예상 · {currentMajorCredits}학점</h4>
					<ul>
						{#each currentMajorSubjects as c}<CourseEvidenceRow
							course={c}
							classification={courseClassification(c)}
							major={rule.major}
							disabled={exclusionBusy}
							onexclude={(value) => setExcluded(c, value)}
							onchange={() => void load()}
						/>{/each}
					</ul>
				</div>
				<div>
					<h4>미래 학기 예상 · {futureMajorCredits}학점</h4>
					<ul>
						{#each futureMajorSubjects as c}<CourseEvidenceRow
							course={c}
							classification={courseClassification(c)}
							major={rule.major}
							disabled={exclusionBusy}
							onexclude={(value) => setExcluded(c, value)}
							onchange={() => void load()}
						/>{/each}
					</ul>
				</div>
			</div>
			{#if excludedSubjects.length}<details class="excluded-courses">
					<summary>이 전공에서 제외한 과목 · {excludedSubjects.length}개</summary>
					<ul>
						{#each excludedSubjects as c}<CourseEvidenceRow
								course={c}
								classification={courseClassification(c)}
								major={rule.major}
								excluded
								onexclude={(value) => setExcluded(c, value)}
								onchange={() => void load()}
							/>{/each}
					</ul>
				</details>{/if}
		</details>
		<label
			>범위 내 전공 학점 <strong>{creditSum} / {track.major_min_credits || 0}</strong><progress
				max={track.major_min_credits || 1}
				value={creditSum}
			></progress></label
		>
		{#if track.required_credits}<label
				>전공필수 학점 <strong>{requiredCredits} / {track.required_credits}</strong><progress
					max={track.required_credits}
					value={requiredCredits}
				></progress></label
			>{/if}
		{#if all.length}<label
				>필수과목 <strong
					>{all.filter((c) => inCalculation(c.code)).length} / {all.length}과목</strong
				><progress max={all.length} value={all.filter((c) => inCalculation(c.code)).length}
				></progress></label
			>{/if}
		{#if pool.length}<p>
				선택 과목 {poolDone.length} / {track.required?.min_courses || 0}과목 · {poolCredits} / {track
					.required?.min_credits || 0}학점
			</p>{/if}
		{#if general}
			<h3>교양 · {general.total_min}학점</h3>
			{#each general.buckets || [] as bucket}
				{@const subjects = includedCourses.filter((c) =>
					area(c).some((a) => bucket.areas?.includes(a))
				)}
				{@const credits = subjects.reduce((sum, c) => sum + c.credits, 0)}
				<label
					>{bucket.name}<strong>{credits} / {bucket.min}학점</strong><progress
						max={bucket.min || 1}
						value={credits}
					></progress></label
				>
				{#if subjects.length}<details class="course-evidence">
						<summary>반영 과목 {subjects.length}개</summary>
						<ul>
							{#each subjects as c}<CourseEvidenceRow
								course={c}
								classification={courseClassification(c)}
								major={rule.major}
								disabled={exclusionBusy}
								onexclude={(value) => setExcluded(c, value)}
								onchange={() => void load()}
							/>{/each}
						</ul>
					</details>{/if}
				{#if bucket.pick_min_areas}<p>
						서로 다른 영역 {new Set(subjects.flatMap(area)).size} / {bucket.pick_min_areas}개
					</p>{/if}
			{/each}
			{#each general.notes || [] as note}<p>{note}</p>{/each}
		{/if}
		{#if excludedSubjects.length}<p class="excluded-note">제외한 과목은 위 계산 근거에서 다시 반영할 수 있습니다.</p>{/if}
		<small
			>종료 학기는 이수, 현재·미래 학기는 예상으로 계산합니다.</small
		>
	</section>
{/if}

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
	.course-evidence {
		font-size: 13px;
	}
	.course-evidence summary {
		cursor: pointer;
		font-weight: 600;
	}
	.course-evidence ul {
		list-style: none;
		padding: 0;
		margin: 8px 0;
	}
	.course-evidence ul { margin: 8px 0; }
	.excluded-courses { margin-top: 10px; }
	.excluded-note { font-size: 12px; }
	.basis-groups {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 12px;
	}
	.basis-groups > div {
		min-width: 0;
	}
	.basis-groups h4 {
		margin: 10px 0;
		font-size: 13px;
	}
</style>
