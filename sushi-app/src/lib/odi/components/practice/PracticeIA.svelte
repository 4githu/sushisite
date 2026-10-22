<script lang="ts">
	import type { PracticeData, PracticeExercise, PracticeAttempt } from '$lib/odi/domain/practice';
	import { API_BASE } from '$lib/config/api';
	import { onMount } from 'svelte';
	import { session, type OdiSession } from '$lib/odi/stores';
	import PracticeCard from './PracticeCard.svelte';
	let {
		data,
		active,
		onselect,
		onviewchange
	}: {
		data: PracticeData;
		active: PracticeAttempt | null;
		onselect: (
			exercise: PracticeExercise,
			runId: string,
			stage: string,
			restartFailed?: boolean
		) => void;
		onviewchange: (view: View) => void;
	} = $props();
	type View = 'home' | 'skill' | 'training' | 'session' | 'result';
	let view = $state<View>('home');
	$effect(() => {
		onviewchange(view);
	});
	let skill = $state('delivery');
	let training = $state<PracticeExercise | null>(null);
	let runId = $state('');
	let stage = $state('baseline');
	let starting = $state(false);
	let error = $state('');
	type RunListItem = { run_id: string; metric_id: string; created_at: string };
	let runs = $state<RunListItem[]>([]);
	let runsError = $state('');
	let restoring = $state(false);
	let restoredAttemptId = $state('');
	let restoredState = $state('');
	type RunStage = {
		stage: string;
		attempt_id: string;
		state: string;
		score: number | null;
		target_seconds?: number | null;
		duration_seconds?: number | null;
		completed_at?: string | null;
	};
	let runStages = $state<RunStage[]>([]);
	let runCreatedAt = $state('');
	let runSourceSessionId = $state('');
	let followups = $state<string[]>([]);
	let followupCandidates = $state<OdiSession[]>([]);
	let selectedFollowup = $state('');
	let followupError = $state('');
	let linking = $state(false);
	function sessionTitle(row: OdiSession) {
		const environment = row.template?.environment;
		return typeof environment === 'object' && environment !== null && 'title' in environment
			? String(environment.title)
			: row.session_id;
	}
	async function loadFollowups() {
		const completedAt = runStages.find(
			(row) => row.stage === 'transfer_challenge' && row.state === 'completed'
		)?.completed_at;
		const after = Math.max(Date.parse(runCreatedAt), Date.parse(completedAt ?? ''));
		if (!Number.isFinite(after)) {
			followupCandidates = [];
			followupError = '전이 단계 완료 시각을 확인할 수 없어 후속 세션을 선택할 수 없습니다.';
			return;
		}
		try {
			followupCandidates = (await session.listAllSessions()).filter(
				(row) =>
					row.state === 'completed' &&
					row.session_id !== runSourceSessionId &&
					Date.parse(row.started_at ?? '') > after &&
					Date.parse(row.ended_at ?? '') >= Date.parse(row.started_at ?? '')
			);
			followupError = '';
		} catch {
			followupError = '세션 목록을 불러오지 못했습니다.';
		}
	}
	async function linkFollowup() {
		if (!selectedFollowup || !runId || linking) return;
		linking = true;
		followupError = '';
		try {
			const response = await fetch(
				`${API_BASE}/odi/coaching/practice/runs/${encodeURIComponent(runId)}/followups`,
				{
					method: 'POST',
					credentials: 'include',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ session_id: selectedFollowup })
				}
			);
			if (!response.ok)
				throw new Error('연결할 수 없습니다. 세션 시각과 소유 상태를 확인해 주세요.');
			const check = await fetch(
				`${API_BASE}/odi/coaching/practice/runs/${encodeURIComponent(runId)}`,
				{ credentials: 'include' }
			);
			if (!check.ok) throw new Error('연결 결과를 확인하지 못했습니다.');
			const result = await check.json();
			if (
				!Array.isArray(result.follow_up_sessions) ||
				!result.follow_up_sessions.includes(selectedFollowup)
			)
				throw new Error('연결 결과를 확인하지 못했습니다.');
			followups = result.follow_up_sessions;
			selectedFollowup = '';
		} catch (e) {
			followupError = e instanceof Error ? e.message : '세션 연결 실패';
		} finally {
			linking = false;
		}
	}
	const stages = [
		'baseline',
		'guided_practice',
		'independent_retry',
		'transfer_challenge'
	] as const;
	const stageNames: Record<string, string> = {
		baseline: 'Baseline',
		guided_practice: 'Guided Practice',
		independent_retry: 'Independent Retry',
		transfer_challenge: 'Transfer Challenge'
	};
	const nextStage = $derived(stages[stages.indexOf(stage as (typeof stages)[number]) + 1] ?? null);
	const displayedAttempt = $derived(
		restoredAttemptId
			? (data.attempts.find((item) => item.attempt_id === restoredAttemptId) ?? null)
			: active
	);
	const names: Record<string, string> = { content: 'Content', delivery: 'Delivery', qa: 'Q&A' };
	const descriptions: Record<string, string> = {
		content: '무엇을 말할 것인가 · 메시지와 논리 구성',
		delivery: '어떻게 말할 것인가 · 속도와 전달 방식',
		qa: '어떻게 대응할 것인가 · 질문 이해와 답변'
	};
	function openSkill(group: string) {
		skill = group;
		view = 'skill';
	}
	function openTraining(exercise: PracticeExercise) {
		training = exercise;
		skill = exercise.group;
		restoredAttemptId = '';
		view = 'training';
	}
	async function loadRuns() {
		try {
			const response = await fetch(`${API_BASE}/odi/coaching/practice/runs?limit=50&offset=0`, {
				credentials: 'include'
			});
			if (!response.ok) throw new Error('연습 흐름 목록을 불러오지 못했습니다.');
			const result = await response.json();
			runs = Array.isArray(result.runs) ? result.runs : [];
			runsError = '';
		} catch (e) {
			runsError = e instanceof Error ? e.message : '목록 불러오기 실패';
		}
	}
	async function restore(id: string) {
		if (restoring) return;
		restoring = true;
		error = '';
		try {
			const response = await fetch(
				`${API_BASE}/odi/coaching/practice/runs/${encodeURIComponent(id)}`,
				{ credentials: 'include' }
			);
			if (!response.ok) throw new Error('연습 상세를 불러오지 못했습니다.');
			const result = await response.json();
			const exercise = data.catalog.find((item) => item.id === result.metric_id && item.available);
			if (!exercise) throw new Error('이 연습은 현재 사용할 수 없습니다.');
			if (!Array.isArray(result.stages)) throw new Error('연습 단계 정보가 올바르지 않습니다.');
			training = exercise;
			skill = exercise.group;
			runId = id;
			runStages = result.stages;
			runCreatedAt = result.created_at ?? '';
			runSourceSessionId = result.source_session_id ?? '';
			followups = Array.isArray(result.follow_up_sessions) ? result.follow_up_sessions : [];
			const latest = [...runStages].sort(
				(a, b) =>
					stages.indexOf(b.stage as (typeof stages)[number]) -
					stages.indexOf(a.stage as (typeof stages)[number])
			)[0];
			stage = latest?.stage ?? 'baseline';
			restoredAttemptId = latest?.attempt_id ?? '';
			restoredState = latest?.state ?? '';
			if (!latest) {
				onselect(exercise, id, stage);
				view = 'session';
			} else if (latest.state === 'completed') {
				view = 'result';
				if (latest.stage === 'transfer_challenge') void loadFollowups();
			} else view = 'session';
		} catch (e) {
			error = e instanceof Error ? e.message : '연습 복원 실패';
		} finally {
			restoring = false;
		}
	}
	onMount(() => {
		void loadRuns();
	});
	$effect(() => {
		if (active?.state !== 'completed' || !runId || restoredAttemptId) return;
		const id = runId;
		void fetch(`${API_BASE}/odi/coaching/practice/runs/${encodeURIComponent(id)}`, {
			credentials: 'include'
		})
			.then(async (response) => {
				if (!response.ok) return;
				const result = await response.json();
				if (runId === id && Array.isArray(result.stages)) {
					runStages = result.stages;
					if (stage === 'transfer_challenge') void loadFollowups();
				}
			})
			.catch(() => {});
	});
	async function start() {
		if (!training?.available || starting) return;
		starting = true;
		error = '';
		try {
			const response = await fetch(`${API_BASE}/odi/coaching/practice/runs`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ metric_id: training.id, source_session_id: null, origin: 'manual' })
			});
			if (!response.ok) throw new Error('연습을 시작하지 못했습니다. 다시 시도해 주세요.');
			const result = await response.json();
			if (typeof result.run_id !== 'string')
				throw new Error('연습 흐름 정보를 확인할 수 없습니다.');
			runId = result.run_id;
			stage = 'baseline';
			runStages = [];
			runCreatedAt = new Date().toISOString();
			runSourceSessionId = '';
			followups = [];
			restoredAttemptId = '';
			restoredState = '';
			void loadRuns();
			onselect(training, runId, stage);
			view = 'session';
		} catch (e) {
			error = e instanceof Error ? e.message : '연습을 시작하지 못했습니다.';
		} finally {
			starting = false;
		}
	}
	function advance() {
		if (!training || !runId || !nextStage || displayedAttempt?.state !== 'completed') return;
		stage = nextStage;
		restoredAttemptId = '';
		restoredState = '';
		onselect(training, runId, stage);
		view = 'session';
	}
	function restart() {
		if (!training || !runId || restoredState !== 'failed') return;
		restoredAttemptId = '';
		restoredState = '';
		onselect(training, runId, stage, true);
	}
</script>

<section class="practice-ia" aria-label="My Practice 학습 경로">
	<nav class="path" aria-label="연습 화면 이동">
		<button
			type="button"
			aria-current={view === 'home' ? 'page' : undefined}
			onclick={() => (view = 'home')}>홈</button
		>
		{#if view !== 'home'}<span aria-hidden="true">/</span><button
				type="button"
				aria-current={view === 'skill' ? 'page' : undefined}
				onclick={() => openSkill(skill)}>{names[skill] ?? skill}</button
			>{/if}
		{#if training && view !== 'home' && view !== 'skill'}<span aria-hidden="true">/</span><button
				type="button"
				aria-current={view === 'training' ? 'page' : undefined}
				onclick={() => (view = 'training')}>{training.title}</button
			>{/if}
	</nav>
	{#if view === 'home'}
		<h2>내 역량 살펴보기</h2>
		<p>역량을 선택해 훈련을 살펴보고, 연습 결과를 확인해 보세요.</p>
		<section aria-label="최근 연습 흐름">
			<h3>최근 연습 이어보기</h3>
			{#if runsError}<p role="status">
					{runsError} <button type="button" onclick={loadRuns}>다시 시도</button>
				</p>{/if}
			{#each runs as run (run.run_id)}
				<button type="button" disabled={restoring} onclick={() => restore(run.run_id)}
					>{data.catalog.find((e) => e.id === run.metric_id)?.title ?? '알 수 없는 훈련'} 연습 이어보기
					· {new Date(run.created_at).toLocaleDateString('ko-KR')}</button
				>
			{/each}
			{#if error}<p role="alert">{error}</p>{/if}
		</section>
		<div class="skill-grid">
			{#each ['content', 'delivery', 'qa'] as group (group)}
				<button
					type="button"
					class="skill-tile"
					aria-label={`${names[group]} 역량 보기`}
					onclick={() => openSkill(group)}
					><strong>{names[group]}</strong><span>{descriptions[group]}</span></button
				>
			{/each}
		</div>
	{:else if view === 'skill'}
		<h2>{names[skill] ?? skill} 역량</h2>
		<p>{descriptions[skill] ?? '훈련 가능한 역량을 살펴보세요.'}</p>
		<div class="exercise-grid">
			{#each data.catalog.filter((e) => e.group === skill) as exercise (exercise.id)}
				<div class="exercise">
					<PracticeCard
						{exercise}
						level={data.progress.metrics[exercise.id]?.level ?? 0}
						progress={data.progress.metrics[exercise.id]?.next_progress ?? 0}
						onselect={() => openTraining(exercise)}
					/><button
						type="button"
						disabled={!exercise.available}
						onclick={() => openTraining(exercise)}>{exercise.title} 훈련 상세 보기</button
					>
				</div>
			{/each}
		</div>
		{#if !data.catalog.some((e) => e.group === skill)}<p role="status">
				이 역량의 훈련은 준비 중입니다.
			</p>{/if}
	{:else if view === 'training' && training}
		<h2>{training.title} 훈련</h2>
		<p>{training.task}</p>
		<p>
			현재 Lv. {data.progress.metrics[training.id]?.level ?? 0} · 다음 레벨 진도 {data.progress
				.metrics[training.id]?.next_progress ?? 0}/3
		</p>
		<p>이번 훈련에서 바꿀 행동을 생각한 뒤 녹음을 시작하세요.</p>
		<button type="button" disabled={!training.available || starting} onclick={start}
			>{starting ? '연습 준비 중…' : '연습 시작하기'}</button
		>
		{#if error}<p role="alert">{error}</p>{/if}
	{:else if view === 'session'}
		<h2>연습 수행</h2>
		<p><strong>{stageNames[stage] ?? stage}</strong> · {training?.task}</p>
		<p>
			{stage === 'baseline'
				? '현재 수행을 녹음해 기준을 확인합니다.'
				: stage === 'guided_practice'
					? '앞선 피드백을 참고해 다시 녹음합니다. 별도의 단계별 가이드 콘텐츠는 아직 제공되지 않습니다.'
					: stage === 'independent_retry'
						? '이전 결과를 참고하되 안내 없이 다시 수행합니다.'
						: '기존 훈련 과제로 전이 수행을 기록합니다. 새로운 상황별 과제는 아직 제공되지 않습니다.'}
		</p>
		{#if restoredAttemptId}<p role="status">
				{restoredState === 'failed'
					? '이전 분석이 실패했습니다. 원본 녹음은 복원되지 않지만, 새 녹음으로 이 단계를 다시 시작할 수 있습니다.'
					: '기존 녹음을 분석 중입니다. 완료되면 새로고침해 결과를 확인해 주세요.'}
			</p>{/if}
		{#if restoredState === 'failed'}<button type="button" onclick={restart}
				>새 녹음으로 다시 시작</button
			>{/if}
		{#if displayedAttempt?.state === 'completed'}<button
				type="button"
				onclick={() => (view = 'result')}>연습 결과 보기</button
			>{/if}
	{:else if view === 'result'}
		<h2>연습 결과</h2>
		<p>
			수행 비교 · 완료한 단계의 원점수만 나열합니다. 점수 차이가 실제 역량 개선을 뜻하지는 않습니다.
		</p>
		<p>녹음마다 목표 시간이 달라질 수 있어 원점수를 동일 조건의 향상 수치로 비교할 수 없습니다.</p>
		{#if stage === 'transfer_challenge'}<p role="status">
				현재는 별도의 새 상황 과제가 없습니다. 전이 성공 여부는 아직 판단할 수 없습니다.
			</p>{/if}
		<ul>
			{#each runStages as row (row.stage)}<li>
					{stageNames[row.stage] ?? row.stage}: {row.state === 'completed'
						? `${row.score ?? '—'}점`
						: row.state === 'failed'
							? '분석 실패'
							: '분석 중'}
					{#if row.state === 'completed' && typeof row.target_seconds === 'number' && typeof row.duration_seconds === 'number'}
						· 목표 {row.target_seconds}초 · 실제 {row.duration_seconds}초
					{/if}
				</li>{/each}
		</ul>
		{#if displayedAttempt?.state === 'completed'}
			<p>{stageNames[stage] ?? stage} 피드백</p>
			<p>{training?.title}: {displayedAttempt.score ?? '—'}점</p>
			<p>{displayedAttempt.feedback?.feedback}</p>
			<blockquote>{displayedAttempt.feedback?.evidence}</blockquote>
			<details>
				<summary>상세 분석 · 발화 내용</summary>
				<p>{displayedAttempt.transcript}</p>
			</details>
			<p>수행 전후 비교와 실제 세션 변화는 단계별 데이터가 연결된 뒤 제공됩니다.</p>
			{#if nextStage}<button type="button" onclick={advance}>{stageNames[nextStage]} 시작</button
				>{:else}<p role="status">
					네 단계의 녹음 분석을 마쳤습니다. 실제 Session 변화는 별도 기록이 연결되어야 확인할 수
					있습니다.
				</p>
				<section aria-label="실제 세션 연결">
					<h3>다음 발표에서 확인하기</h3>
					<p>
						완료한 발표·면접 세션을 직접 연결할 수 있습니다. 연결만으로 개선 효과가 입증되지는
						않습니다.
					</p>
					{#each followups as id (id)}<p>
							{sessionTitle(
								followupCandidates.find((row) => row.session_id === id) ??
									({ session_id: id, template: {} } as OdiSession)
							)} 연결됨 · <a href={`/odi/report/${encodeURIComponent(id)}`}>리포트 보기</a>
						</p>{/each}
					<label
						>후속 세션 선택 <select aria-label="후속 세션 선택" bind:value={selectedFollowup}>
							<option value="">세션 선택</option>
							{#each followupCandidates.filter((row) => !followups.includes(row.session_id)) as row (row.session_id)}<option
									value={row.session_id}>{sessionTitle(row)}</option
								>{/each}
						</select></label
					>
					<button type="button" disabled={!selectedFollowup || linking} onclick={linkFollowup}
						>{linking ? '연결 확인 중…' : '세션 연결하기'}</button
					>
					{#if followupError}<p role="alert">{followupError}</p>{/if}
				</section>{/if}
			<button type="button" onclick={start}>같은 훈련 다시 연습</button>
		{:else}<p role="status">완료된 분석 결과가 없습니다.</p>{/if}
	{/if}
</section>

<style>
	.practice-ia {
		padding: 26px;
		margin: 24px 0;
		border: 1px solid #dce0ea;
		border-radius: 14px;
		background: #fff;
		color: #111a3c;
	}
	.path {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-wrap: wrap;
		margin-bottom: 24px;
	}
	.path button {
		border: 0;
		background: none;
		color: #4054a2;
		text-decoration: underline;
		cursor: pointer;
		padding: 6px;
	}
	.path [aria-current='page'] {
		color: #111a3c;
		font-weight: 700;
		text-decoration: none;
	}
	.skill-grid,
	.exercise-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 14px;
		margin-top: 20px;
	}
	.skill-tile {
		display: flex;
		flex-direction: column;
		gap: 9px;
		text-align: left;
		border: 1px solid #dce0ea;
		border-radius: 12px;
		background: #f5f7fc;
		padding: 20px;
		cursor: pointer;
	}
	.skill-tile strong {
		color: #111a3c;
		font-size: 18px;
	}
	.skill-tile span {
		font-size: 13px;
		color: #56617b;
	}
	.exercise > button:last-child,
	.practice-ia > button {
		margin-top: 16px;
		padding: 10px 16px;
		border: 1px solid #515fd8;
		border-radius: 8px;
		background: #fff;
		color: #1f2e9d;
		cursor: pointer;
	}
	button:focus-visible {
		outline: 3px solid #2653ff;
		outline-offset: 2px;
	}
	button:disabled {
		cursor: not-allowed;
		opacity: 0.55;
	}
	@media (max-width: 750px) {
		.skill-grid,
		.exercise-grid {
			grid-template-columns: 1fr;
		}
		.practice-ia {
			padding: 18px;
		}
	}
</style>
