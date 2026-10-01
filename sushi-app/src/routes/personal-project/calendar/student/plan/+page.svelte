<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import Transcript from '$lib/personal-project/student/Transcript.svelte';
	import RuleVersion from '$lib/personal-project/student/RuleVersion.svelte';
	import RuleProgress from '$lib/personal-project/student/RuleProgress.svelte';
	import RuleText from '$lib/personal-project/student/RuleText.svelte';
	import { type CourseProgress } from '$lib/personal-project/student/progress';
	import RuleTree from '$lib/personal-project/student/RuleTree.svelte';
	import '$lib/personal-project/student/student.css';
	type Entry = { id: string; major: string; batch: string };
	type Rule = {
		major: string;
		college: string;
		source: string;
		source_links?: string[];
		major_required_known?: unknown;
		total_credits: number;
		notes: string[];
		raw_notes?: string[];
		needs_verification?: boolean;
		tracks: ({ key: string; name: string; major_min_credits?: number } & Record<string, unknown>)[];
		external_recognition?: unknown;
		dept_required_general?: unknown;
	};
	let progress = $state<CourseProgress>({ planned: [], completed: [] });

	let entries = $state<Entry[]>([]),
		major = $state(''),
		batch = $state(''),
		track = $state('double'),
		rule = $state<Rule | null>(null),
		error = $state(''),
		loading = $state(true),
		updated = $state('');
	type Selection = { rule_id: string; batch: string; track: string };
	let tab = $state<'current' | 'explore' | 'rules'>('current');
	let plan = $state<{ items: Selection[]; revision: number }>({ items: [], revision: 0 });
	let savedRules = $state<Record<string, Rule>>({});
	let saving = $state(false),
		planReady = $state(false);
	async function updatePlan(items: Selection[]) {
		if (!planReady || saving) return;
		saving = true;
		error = '';
		const detail = rule,
			entry = entries.find((e) => e.major === major && e.batch === batch);
		try {
			plan = await request('/student/major-plan', {
				method: 'PUT',
				body: { items, revision: plan.revision }
			});
			if (detail && entry) savedRules[entry.id] = detail;
			tab = 'current';
		} catch (e) {
			error = e instanceof Error ? e.message : '전공 저장 실패';
		} finally {
			saving = false;
		}
	}
	function addMajor() {
		const entry = entries.find((e) => e.major === major && e.batch === batch);
		if (!entry || !current) return;
		if (plan.items.some((i) => i.rule_id === entry.id && i.batch === batch && i.track === track)) {
			error = '이미 추가한 전공입니다.';
			return;
		}
		void updatePlan([...plan.items, { rule_id: entry.id, batch, track }]);
	}
	function inspectMajor(item: Selection) {
		major = entries.find((e) => e.id === item.rule_id)?.major || '';
		batch = item.batch;
		track = item.track;
		tab = 'explore';
		void load();
	}

	let officialRule = $state<Rule | null>(null);
	let version = 0;
	const majors = $derived([...new Set(entries.map((e) => e.major))].sort());
	const batches = $derived(
		[...new Set(entries.filter((e) => e.major === major).map((e) => e.batch))].sort().reverse()
	);
	const current = $derived(rule?.tracks.find((t) => t.key === track));
	function containsCourse(value: unknown, code: string): boolean {
		if (Array.isArray(value)) return value.some((v) => containsCourse(v, code));
		if (value && typeof value === 'object')
			return (
				('code' in value && String(value.code) === code) ||
				Object.values(value).some((v) => containsCourse(v, code))
			);
		return false;
	}
	const extraKnown = $derived(
		Array.isArray(rule?.major_required_known)
			? rule.major_required_known.filter(
					(item) =>
						item &&
						typeof item === 'object' &&
						'code' in item &&
						!containsCourse(current, String(item.code))
				)
			: []
	);

	async function load() {
		const n = ++version;
		loading = true;
		error = '';
		rule = null;
		try {
			const entry = entries.find((e) => e.major === major && e.batch === batch);
			if (!entry) return;
			const data = await request<Rule>(`/student/rules/${encodeURIComponent(entry.id)}`);
			if (n !== version) return;
			rule = officialRule = data;
			if (!data.tracks.some((t) => t.key === track)) track = data.tracks[0]?.key || '';
		} catch (e) {
			if (n === version) error = e instanceof Error ? e.message : '자료 불러오기 실패';
		} finally {
			if (n === version) loading = false;
		}
	}
	onMount(async () => {
		try {
			const data = await request<{ index: Entry[]; sourceUpdatedAt: string }>('/student/rules');
			entries = data.index;
			updated = data.sourceUpdatedAt;
			major = majors.includes('컴퓨터공학부') ? '컴퓨터공학부' : majors[0];
			batch = [...new Set(entries.filter((e) => e.major === major).map((e) => e.batch))]
				.sort()
				.reverse()[0];
			[plan, progress] = await Promise.all([
				request<typeof plan>('/student/major-plan'),
				request<CourseProgress>('/student/course-progress')
			]);
			const details = await Promise.all(
				[...new Set(plan.items.map((i) => i.rule_id))].map(async (id) => {
					const [official, version, choice] = await Promise.all([
						request<Rule>(`/student/rules/${encodeURIComponent(id)}`),
						request<{ data: Rule | null }>(`/student/rules/${encodeURIComponent(id)}/versions`),
						request<{ data: { edition?: string } | null }>(
							`/documents/rule-choice:${encodeURIComponent(id)}`
						)
					]);
					return [
						id,
						choice.data?.edition === 'custom' && version.data ? version.data : official
					] as const;
				})
			);
			savedRules = Object.fromEntries(details);
			planReady = true;
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : '자료 불러오기 실패';
			loading = false;
		}
	});
</script>

<svelte:head><title>수강계획·이수규정 · NETAQ</title></svelte:head>
<div class="student-page">
	<header class="page-heading">
		<div>
			<h1>수강계획과 이수규정</h1>
			<p class="muted">서울대 학과·입학 연도별 주전공, 복수전공, 부전공 규정을 확인하세요.</p>
		</div>
		<a class="button" href="/personal-project/calendar/student/timetable"
			>강의 검색하고 시간표 짜기</a
		>
	</header>
	<nav class="major-tabs" aria-label="수강 계획 보기">
		<button class:chosen={tab === 'current'} onclick={() => (tab = 'current')}>현재 전공</button>
		<button class:chosen={tab === 'explore'} onclick={() => (tab = 'explore')}
			>전공 탐색·이수 현황</button
		><a class="button" href="/personal-project/calendar/student/plan/explore">과거 강의 탐색</a
		><button class:chosen={tab === 'rules'} onclick={() => (tab = 'rules')}
			>수강 규정 편집·업데이트</button
		>
	</nav>
	<Transcript onchange={(p) => (progress = p)} />
	{#if error}<p role="alert" class="error">{error}</p>
		<button onclick={() => location.reload()}>새로고침하고 다시 시도</button>{/if}
	{#if tab === 'current'}
		<section class="panel">
			<div class="major-heading">
				<h2>현재 전공</h2>
				<button
					aria-label="현재 전공 추가"
					disabled={!planReady || saving || plan.items.length >= 8}
					onclick={() => (tab = 'explore')}>+ 전공 추가</button
				>
			</div>
			<p class="muted">
				역대 시간표를 바탕으로 주전공·복수전공·부전공의 남은 이수 요건을 비교하세요. 최대 8개까지
				계정에 저장됩니다.
			</p>
			{#if !planReady}<p>전공 목록을 불러오는 중…</p>{:else if !plan.items.length}<p>
					등록한 전공이 없습니다. + 버튼으로 시작하세요.
				</p>{/if}
			<div class="major-grid">
				{#each plan.items as item, i}
					{@const detail = savedRules[item.rule_id]}
					{@const chosen = detail?.tracks.find((t) => t.key === item.track)}
					<article class="major-card">
						<h3>{detail?.major}</h3>
						<p>{item.batch}학번 · {chosen?.name}</p>
						<dl>
							<dt>전공 최소</dt>
							<dd>{chosen?.major_min_credits ?? '자료 없음'} 학점</dd>
							<dt>졸업 총학점</dt>
							<dd>{detail?.total_credits ?? '자료 없음'} 학점</dd>
						</dl>
						{#if detail?.needs_verification}<p class="muted">
								일부 조건은 학과 확인이 필요합니다.
							</p>{/if}
						{#if detail && chosen}<RuleProgress
								rule={detail}
								track={chosen}
								{progress}
							/>{/if}<button onclick={() => inspectMajor(item)}>이수 현황·규정 편집</button>
						<button
							disabled={saving}
							aria-label={`${detail?.major} ${chosen?.name} 삭제`}
							onclick={() => updatePlan(plan.items.filter((_, n) => n !== i))}>삭제</button
						>
					</article>
				{/each}
			</div>
			<p class="muted">
				각 전공의 기준을 나란히 표시합니다. 중복 인정 학점이나 졸업 충족 여부를 합산 판정하지
				않습니다.
			</p>
		</section>
	{:else}
		<section class="panel">
			<div class="fields">
				<label
					>학과<select
						bind:value={major}
						onchange={() => {
							batch = [...new Set(entries.filter((e) => e.major === major).map((e) => e.batch))]
								.sort()
								.reverse()[0];
							void load();
						}}
						>{#each majors as m}<option>{m}</option>{/each}</select
					></label
				><label
					>입학 연도<select bind:value={batch} onchange={() => load()}
						>{#each batches as b}<option>{b}</option>{/each}</select
					></label
				><label
					>전공 유형<select bind:value={track} disabled={loading}
						>{#each rule?.tracks || [] as t}<option value={t.key}>{t.name}</option>{/each}</select
					></label
				>
			</div>
		</section>

		{#if loading}<p role="status">이수규정을 불러오는 중…</p>{:else if rule}<section
				class="panel rule"
			>
				<p class="eyebrow">{rule.college} / {batch}학번</p>
				<h2>{rule.major} · {current?.name}</h2>
				{#if officialRule}{#key entries.find((e) => e.major === major && e.batch === batch)?.id}<RuleVersion
							ruleId={entries.find((e) => e.major === major && e.batch === batch)!.id}
							official={officialRule}
							{track}
							onselect={(v) => {
								rule = v;
								const entry = entries.find((e) => e.major === major && e.batch === batch);
								if (entry) savedRules = { ...savedRules, [entry.id]: v };
							}}
						/>{/key}{/if}
				{#if current}<RuleProgress {rule} track={current} {progress} />{/if}
				<button disabled={saving || !planReady || plan.items.length >= 8} onclick={addMajor}
					>+ 현재 전공에 추가</button
				>
				{#if rule.needs_verification}<p role="note">
						자료 확인 필요 · 일부 수치나 필수 과목이 임시 기준입니다. 학과의 공식 안내를
						확인해주세요.
					</p>{/if}
				<div class="metrics">
					<div>
						<small>전공 최소</small><strong
							>{current?.major_min_credits ?? '자료 없음'}<span> 학점</span></strong
						>
					</div>
					<div>
						<small>졸업 총학점</small><strong>{rule.total_credits}<span> 학점</span></strong>
					</div>
				</div>
				<p class="muted">
					Class Checker 가공 자료입니다. 졸업 판정 결과가 아니며, 승인·예외 조건은 아래 원문 출처 및
					학과 사무실에서 확인하세요.
				</p>
				<details open>
					<summary>이수 조건과 필수 과목</summary>
					<p class="muted">
						지난 학기의 내 시간표를 기준으로 계산합니다. 진행 중인 학기와 탐색 초안은 이수 학점에
						포함하지 않습니다. 동일·동등 과목은 한 번만 합산합니다. 성적 증명에 따른 공식 졸업
						판정은 아닙니다.
					</p>
					{#if current}<RuleTree
							{progress}
							value={Object.fromEntries(
								Object.entries(current).filter(
									([k]) => !['key', 'name', 'major_min_credits'].includes(k)
								)
							)}
						/>{:else}<p>선택한 유형의 자료가 없습니다.</p>{/if}
				</details>
				{#if extraKnown.length}<details open>
						<summary>학과 전공필수 참고 목록</summary>
						<p class="muted">
							현재 전공 유형의 조건에 없는 학과 참고 과목입니다. 복수·부전공 적용 여부는 학과에
							확인해주세요.
						</p>
						<RuleTree {progress} value={extraKnown} />
					</details>{/if}
				{#if rule.external_recognition}<details>
						<summary>타 전공 학점 인정</summary><RuleTree
							{progress}
							value={rule.external_recognition}
						/>
					</details>{/if}
				{#if rule.dept_required_general}<details>
						<summary>학과 지정 교양</summary><RuleTree
							{progress}
							value={rule.dept_required_general}
						/>
					</details>{/if}
				<details open>
					<summary>세부 규정·예외</summary>
					<ul>
						{#each rule.notes as note}<li><RuleText text={note} /></li>{/each}
					</ul>
				</details>
				<details>
					<summary>자료 출처</summary>
					<p class="source">{rule.source}</p>
					{#each rule.source_links || [] as link}<p>
							<a href={link} target="_blank" rel="noopener noreferrer"
								>학과 안내 · {new URL(link).hostname} ↗</a
							>
						</p>{/each}
					<a href="https://github.com/Rekhet/class-checker" target="_blank" rel="noreferrer"
						>Class Checker 이수규정 데이터 보기 ↗</a
					>
				</details>
			</section>{/if}
	{/if}
	<p class="muted">
		원본 갱신 {updated.slice(0, 10)} · 자료에 없는 학과·학번은 임의의 다른 학번 규정으로 대체하지 않습니다.
	</p>
</div>

<style>
	.major-tabs,
	.major-heading {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-bottom: 20px;
	}
	.major-heading {
		justify-content: space-between;
	}
	.major-tabs {
		flex-wrap: wrap;
	}
	.major-tabs .chosen {
		background: #25314a;
		color: white;
	}
	.major-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
		gap: 16px;
	}
	.major-card {
		border: 1px solid #dde0e7;
		padding: 18px;
		border-radius: 12px;
	}
	.major-card p,
	.major-card dl {
		font-size: 13px;
		line-height: 1.7;
	}
	.major-card dd {
		margin: 0 0 8px;
		font-weight: 600;
	}

	.rule {
		margin-top: 20px;
		max-width: 950px;
	}
	.metrics {
		display: flex;
		gap: 40px;
		padding: 20px 0;
	}
	.metrics small {
		display: block;
		font-size: 12px;
		color: #777;
		margin-bottom: 8px;
	}
	.metrics strong {
		font-size: 30px;
		letter-spacing: -1px;
	}
	.metrics span {
		font-size: 13px;
		font-weight: 400;
	}
	.rule details {
		border-top: 1px solid #e2e3e7;
	}
	.rule li {
		font-size: 13px;
		line-height: 1.8;
		margin: 10px 0;
	}
	.source {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 13px;
	}
</style>
