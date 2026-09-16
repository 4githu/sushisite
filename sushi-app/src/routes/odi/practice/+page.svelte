<script lang="ts">
	import { session } from '$lib/odi/stores';
	import {
		recommendations,
		completedSummaries,
		trainingNames
	} from '$lib/odi/domain/sessionSummary';
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { API_BASE } from '$lib/config/api';
	import type { PracticeData, PracticeExercise } from '$lib/odi/domain/practice';
	import PracticeCard from '$lib/odi/components/practice/PracticeCard.svelte';
	import PracticeRecorder from '$lib/odi/components/practice/PracticeRecorder.svelte';
	import Button from '$lib/odi/components/common/Button.svelte';
	import { formatKoreanDuration } from '$lib/odi/components/report/reportUtils';
	let data = $state<PracticeData | null>(null),
		loading = $state(true),
		error = $state(''),
		selected = $state<PracticeExercise | null>(null),
		activeId = $state(''),
		disposed = false,
		poll: ReturnType<typeof setTimeout> | undefined;
	let recommended = $state<string[]>(recommendations());
	const active = $derived(data?.attempts.find((a) => a.attempt_id === activeId) ?? null);
	const pending = $derived(
		data?.attempts.some((a) => ['queued', 'analyzing'].includes(a.state)) ?? false
	);
	async function load(initial = false) {
		try {
			const res = await fetch(`${API_BASE}/odi/coaching/practice`, { credentials: 'include' });
			if (!res.ok) throw new Error('훈련 기록을 불러오지 못했습니다. 로그인 상태를 확인해 주세요.');
			const result = await res.json();
			if (disposed) return;
			data = result;
			error = '';
			if (initial) {
				const id = page.url.searchParams.get('training');
				selected = data?.catalog.find((e) => e.id === id && e.available) ?? null;
			}
			if (result.attempts.some((a: { state: string }) => ['queued', 'analyzing'].includes(a.state)))
				poll = setTimeout(() => load(), 1800);
		} catch (e) {
			if (!disposed) error = e instanceof Error ? e.message : '불러오기 실패';
		} finally {
			if (!disposed) loading = false;
		}
	}
	function created(id: string) {
		activeId = id;
		clearTimeout(poll);
		void load();
	}
	onMount(() => {
		void session
			.listAllSessions()
			.then((rows) => {
				if (!disposed) recommended = recommendations(completedSummaries(rows)[0]?.session);
			})
			.catch(() => {});
		void load(true);
		return () => {
			disposed = true;
			clearTimeout(poll);
		};
	});
</script>

<svelte:head><title>My Practice | Re:hear</title></svelte:head>
<main class="odi-workspace">
	<header>
		<h1>My Practice</h1>
		<p class="muted">영역별 훈련을 선택하고, 짧은 음성 연습으로 말하기 역량을 키워보세요.</p>
	</header>
	{#if error}<p role="alert" class="error">{error}</p>
		<Button onclick={() => load()}>다시 시도</Button>{/if}{#if loading}<p class="state">
			훈련 기록을 불러오는 중…
		</p>{:else if data}<div class="practice-overview">
			<section class="intro">
				<p class="eyebrow">WEB VOICE PRACTICE</p>
				<h2>한 번에 하나씩,<br />나의 말하기를 더 선명하게.</h2>
				<p>60초부터 시작하세요. 80점 이상 3회마다 레벨이 올라갑니다.</p>
			</section>
			<section class="my-progress">
				<h2>My Progress</h2>
				<div>
					<strong>{data.progress.completed_count}<small>완료 훈련</small></strong><strong
						>{formatKoreanDuration(data.progress.total_seconds)}<small>총 훈련 시간</small></strong
					>
				</div>
				<p>이번 주 80점 이상 <b>{data.progress.weekly_successes} / 5회</b></p>
				<progress
					max="5"
					value={Math.min(5, data.progress.weekly_successes)}
					aria-label="이번 주 80점 이상 5회 목표"
				></progress>
			</section>
		</div>
		<section class="surface">
			<h2>오늘의 추천 훈련</h2>
			<div class="actions">
				{#each recommended as id, rowIndex0 (rowIndex0)}<Button
						variant="outline"
						onclick={() => {
							selected = data?.catalog.find((e) => e.id === id) ?? null;
							activeId = '';
						}}>{trainingNames[id]}</Button
					>{/each}
			</div>
		</section>
		{#if selected}{#key selected.id}<PracticeRecorder
					exercise={selected}
					attempt={active?.metric_id === selected.id ? active : null}
					oncreated={created}
					onclose={() => {
						selected = null;
						activeId = '';
					}}
				/>{/key}{/if}
		{#each [{ id: 'content', label: '내용 구성' }, { id: 'delivery', label: '전달 방식' }] as group, rowIndex1 (rowIndex1)}<section
				class="exercise-section"
			>
				<h2>{group.label}</h2>
				<div class="exercise-grid">
					{#each data.catalog.filter((e) => e.group === group.id) as exercise, rowIndex2 (rowIndex2)}<PracticeCard
							{exercise}
							level={data.progress.metrics[exercise.id]?.level ?? 0}
							progress={data.progress.metrics[exercise.id]?.next_progress ?? 0}
							onselect={() => {
								selected = exercise;
								activeId = '';
							}}
						/>{/each}
				</div>
			</section>{/each}
		<section class="surface history">
			<h2>나의 훈련 기록</h2>
			{#if pending}<p role="status">
					녹음을 분석하고 있어요. 완료되면 진도가 갱신됩니다.
				</p>{/if}{#each data.attempts as attempt (attempt.attempt_id)}<details>
					<summary
						><span>{data.catalog.find((e) => e.id === attempt.metric_id)?.title}</span><span
							>{new Date(attempt.created_at).toLocaleDateString('ko-KR')}</span
						><strong
							>{attempt.state === 'completed'
								? `${attempt.score}점`
								: attempt.state === 'failed'
									? '분석 실패'
									: '분석 중'}</strong
						></summary
					>{#if attempt.state === 'completed'}<p>{attempt.feedback?.feedback}</p>
						<blockquote>{attempt.feedback?.evidence}</blockquote>
						<p class="muted">{attempt.transcript}</p>{:else if attempt.error}<p class="error">
							{attempt.error}
						</p>{/if}
				</details>{:else}<p class="muted">첫 훈련을 완료하면 나의 변화가 여기에 기록돼요.</p>{/each}
		</section>{/if}
</main>

<style>
	.practice-overview {
		display: grid;
		grid-template-columns: 1.7fr 1fr;
		gap: 18px;
		margin-bottom: 30px;
	}
	.intro,
	.my-progress {
		padding: 28px 32px;
		border-radius: 14px;
		color: white;
		background: #050632;
	}
	.intro {
		background: linear-gradient(120deg, #050632, #37316e);
	}
	.intro h2 {
		font-size: 30px !important;
		line-height: 1.35;
	}
	.intro .eyebrow {
		color: #bfc5ff !important;
		font-size: 12px;
	}
	.intro p {
		color: #d0d4ed;
		font-size: 14px;
	}
	.my-progress > div {
		display: flex;
		justify-content: space-between;
		gap: 20px;
	}
	.my-progress strong {
		font-size: 28px;
	}
	.my-progress small {
		display: block;
		font-size: 12px;
		font-weight: 400;
		color: #bfc5df;
		margin-top: 8px;
	}
	.my-progress progress {
		width: 100%;
		accent-color: #cfff5e;
		height: 7px;
	}
	.my-progress p {
		font-size: 14px;
	}
	.exercise-section {
		margin: 30px 0;
	}
	.exercise-grid {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 14px;
	}
	.history summary {
		display: flex;
		gap: 20px;
		justify-content: space-between;
		cursor: pointer;
		padding: 18px 0;
	}
	.history details {
		border-bottom: 1px solid #e0e4ec;
	}
	.history summary span:first-child {
		flex: 1;
	}
	.history summary strong {
		color: #03f;
	}
	.history p,
	.history blockquote {
		font-size: 14px;
	}
	@media (max-width: 1550px) {
		.exercise-grid {
			grid-template-columns: repeat(3, 1fr);
		}
	}
	@media (max-width: 750px) {
		.practice-overview {
			grid-template-columns: 1fr;
		}
		.exercise-grid {
			grid-template-columns: 1fr 1fr;
		}
		.history summary {
			flex-wrap: wrap;
			font-size: 13px;
		}
	}
	@media (max-width: 440px) {
		.exercise-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
