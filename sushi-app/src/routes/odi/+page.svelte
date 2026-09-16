<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { odiuser, session, template, type OdiSession } from '$lib/odi/stores';
	import { API_BASE } from '$lib/config/api';
	import HomeHero from '$lib/odi/components/home/HomeHero.svelte';
	import RecentPractice from '$lib/odi/components/home/RecentPractice.svelte';
	import GrowthCard from '$lib/odi/components/home/GrowthCard.svelte';
	import TrainingRecommendations from '$lib/odi/components/home/TrainingRecommendations.svelte';
	import {
		completedSummaries,
		recommendations,
		type SessionSummary
	} from '$lib/odi/domain/sessionSummary';
	import setup from '$lib/odi/assets/home-202609/step-setup.png';
	import present from '$lib/odi/assets/home-202609/step-present.png';
	import report from '$lib/odi/assets/home-202609/step-report.png';
	let sessions = $state<OdiSession[]>([]),
		loading = $state(false),
		error = $state(''),
		busy = $state(false);
	const rows = $derived(completedSummaries(sessions));
	const trainings = $derived(recommendations(rows[0]?.session));
	const name = $derived($odiuser?.config?.profile?.nickname || '리히어');
	onMount(() => {
		let generation = 0,
			lastId: string | undefined;
		const unsubscribe = odiuser.subscribe((user) => {
			const id = user?.user_id;
			if (id === lastId) return;
			lastId = id;
			const n = ++generation;
			sessions = [];
			loading = Boolean(id);
			error = '';
			if (id)
				void session
					.listAllSessions()
					.then((r) => {
						if (n === generation) sessions = r;
					})
					.catch((e) => {
						if (n === generation) error = e.message;
					})
					.finally(() => {
						if (n === generation) loading = false;
					});
		});
		return () => {
			generation++;
			unsubscribe();
		};
	});

	function start() {
		template.setDefault('presentation');
		void goto('/odi/session/presentation');
	}
	async function repeat(row: SessionSummary) {
		if (busy) return;
		busy = true;
		error = '';
		try {
			if (row.templateId) {
				const res = await fetch(`${API_BASE}/odi/db/templates/${row.templateId}`, {
					credentials: 'include'
				});
				if (!res.ok)
					throw new Error('원본 환경을 불러오지 못했습니다. 템플릿 목록에서 확인해 주세요.');
				const saved = (await res.json()).template;
				template.loadSaved(saved.template);
				template.set({
					...row.session.template,
					id: row.templateId,
					version: saved.version
				} as any);
			} else {
				template.set({ ...row.session.template, id: undefined } as any);
			}
			await goto(`/odi/session/${row.session.template.type ?? 'presentation'}/confirm`);
		} catch (e) {
			error = e instanceof Error ? e.message : '환경 불러오기 실패';
		} finally {
			busy = false;
		}
	}
	const steps = [
		{
			title: '세션 설정',
			description: '발표 주제와 자료를 업로드하고 연습 환경을 설정해요.',
			image: setup
		},
		{
			title: 'AI 청중과 발표',
			description: '다양한 상황의 AI 청중 앞에서 실전처럼 발표를 진행해요.',
			image: present
		},
		{
			title: '결과 확인',
			description: '발표가 끝나면 상세한 피드백으로 다음 목표를 정해요.',
			image: report
		}
	];
</script>

<svelte:head><title>Home | Re:hear</title></svelte:head>
<main class="odi-workspace">
	<header>
		<h1>안녕하세요, {name}님 ✋</h1>
		<p class="muted">꾸준한 연습이 자신감을 만듭니다. 오늘도 한 걸음 더 성장해요!</p>
	</header>
	{#if error}<p role="alert" class="error">{error}</p>{/if}{#if loading}<p class="state">
			연습 기록을 불러오는 중…
		</p>{:else if error && !rows.length}<p class="state">
			기록을 불러오지 못했습니다. 잠시 후 페이지를 새로고침해 주세요.
		</p>{:else}<HomeHero first={!rows.length} onstart={start} />{#if rows.length}<div
				class="dashboard"
			>
				<RecentPractice {rows} onrepeat={repeat} {busy} /><GrowthCard {rows} />
			</div>
			<TrainingRecommendations ids={trainings} />{:else}<section>
				<h2>어떻게 진행되나요?</h2>
				<p class="muted">간단한 3단계로, 누구나 쉽게 시작할 수 있어요.</p>
				<div class="onboarding">
					{#each steps as step, i (i)}<article class="surface">
							<span class="chip">0{i + 1}</span>
							<h3>{step.title}</h3>
							<p>{step.description}</p>
							<img src={step.image} alt={step.title} />
						</article>{/each}
				</div>
				<div class="promise">
					<strong>Re:hear와 함께하면, 이런 점이 달라져요.</strong>
					<p>실전과 유사한 연습 환경 · AI 기반 피드백 · 나에게 맞는 훈련 추천</p>
				</div>
			</section>{/if}{/if}
</main>

<style>
	header p {
		margin: 0;
	}
	.dashboard {
		display: grid;
		grid-template-columns: 1.05fr 1fr;
		gap: 20px;
		margin-bottom: 20px;
	}
	.onboarding {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 20px;
	}
	.onboarding h3 {
		margin-top: 14px;
	}
	.onboarding p {
		font-size: 15px;
		color: #616678;
	}
	.onboarding img {
		width: 100%;
		height: 150px;
		object-fit: cover;
		border-radius: 8px;
	}
	.promise {
		padding: 22px 30px;
		background: #e6ebff;
		margin-top: 20px;
		border-radius: 10px;
	}
	.promise p {
		font-size: 14px;
	}
	@media (max-width: 1000px) {
		.dashboard {
			grid-template-columns: 1fr;
		}
	}
	@media (max-width: 700px) {
		.onboarding {
			grid-template-columns: 1fr;
		}
	}
</style>
