<!-- src/routes/odi/join/+page.svelte -->
<script lang="ts">
	import "$lib/odi/styles/globals.css";

	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { auth } from "$lib/stores/mainauth";
	import { odiuser, type JsonObject } from "$lib/odi/stores";
	import { API_BASE as API } from '$lib/config/api';

	import Button from "$lib/odi/components/common/Button.svelte";
	import AuthField from "$lib/odi/components/login/AuthField.svelte";
	import AgreementBox from "$lib/odi/components/login/AgreementBox.svelte";
	import AuthStepper from "$lib/odi/components/login/AuthStepper.svelte";
	import OdiJoinGoalStep, {
		type FocusArea,
		type PracticeFrequency,
		type TrainingType
	} from "$lib/odi/components/login/OdiJoinGoalStep.svelte";
	import OdiJoinCompleteStep from "$lib/odi/components/login/OdiJoinCompleteStep.svelte";

	import {
		account_circle as AccountCircle,
		home as Mail,
		home as Person
	} from "$lib/odi/icons";

	const steps = ["계정 확인", "훈련 목표 설정", "계정 설정 완료"];

	let currentStep = $state(0);
	let loading = $state(false);
	let errorMessage = $state("");

	let authId = $state("");
	let mainName = $state("");
	let mainEmail = $state("");

	let nickname = $state("");
	let allAgreed = $state(false);
	let serviceAgreed = $state(false);
	let privacyAgreed = $state(false);
	let marketingAgreed = $state(false);

	let trainingType = $state("both" as TrainingType);
	let focusArea = $state("delivery" as FocusArea);
	let practiceFrequency = $state(3 as PracticeFrequency);

	const nicknameOk = $derived(nickname.trim().length >= 2);
	const canNextFromAccount = $derived(nicknameOk && serviceAgreed && privacyAgreed && !loading);
	const canFinishGoal = $derived(Boolean(trainingType && focusArea && practiceFrequency) && !loading);

	onMount(async () => {
		const existingOdiUser = odiuser.get();

		if (existingOdiUser !== null) {
			goto("/odi");
			return;
		}

		const payload = await auth.check();

		if (payload === null) {
			goto("/odi");
			return;
		}

		authId = String(payload.data?.id ?? "");
		mainName = payload.data?.name ?? "";
		mainEmail = payload.data?.email ?? "";

		nickname = mainName || "리히어";

		if (!authId) {
			errorMessage = "mainauth 계정 정보를 확인할 수 없습니다.";
		}
	});

	async function logoutMainAuth() {
		await Promise.all([
			fetch(`${API}/auth/logout`, {
				method: "POST",
				credentials: "include"
			}).catch(() => null),
			odiuser.logout().catch(() => null)
		]);

		auth.logout();
		odiuser.clear();
		goto("/odi");
	}

	function goNextFromAccount() {
		if (!canNextFromAccount) return;
		errorMessage = "";
		currentStep = 1;
	}

	function goPrevious() {
		if (currentStep === 0) {
			goto("/odi");
			return;
		}

		currentStep -= 1;
	}

	async function completeJoin() {
		if (!canFinishGoal || !authId) return;

		loading = true;
		errorMessage = "";

		try {
			const config = createDefaultOdiConfig({
				authId,
				nickname: nickname.trim(),
				trainingType,
				focusArea,
				practiceFrequency
			});

			await odiuser.join(config, null);

			currentStep = 2;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "Re:hear 계정 설정에 실패했습니다.";
		} finally {
			loading = false;
		}
	}

	function startFirstSession() {
		goto("/odi/session/presentation");
	}

	function goHome() {
		goto("/odi");
	}

	function openTerm(type: "all" | "service" | "privacy" | "marketing") {
		console.log("open odi term", type);
	}

	function trainingTypeLabel(value: TrainingType) {
		if (value === "presentation") return "발표 연습";
		if (value === "interview") return "면접 연습";
		return "발표와 면접";
	}

	function focusAreaLabel(value: FocusArea) {
		if (value === "content") return "내용 구성";
		return "전달 방식";
	}

	function createTrainingTitle(value: PracticeFrequency) {
		return `주 ${value}회 연습 루틴 만들기`;
	}

	function createDefaultOdiConfig({
		authId,
		nickname,
		trainingType,
		focusArea,
		practiceFrequency
	}: {
		authId: string;
		nickname: string;
		trainingType: TrainingType;
		focusArea: FocusArea;
		practiceFrequency: PracticeFrequency;
	}): JsonObject {
		const now = new Date().toISOString();
		const trainingLabel = trainingTypeLabel(trainingType);
		const focusLabel = focusAreaLabel(focusArea);

		return {
			owner_id: authId,
			updated_at: now,

			profile: {
				nickname,
				level: "새싹 보이스",
				level_icon: "seed_voice",
				current_exp: 0,
				next_level_exp: 300,
				profile_image: null
			},

			statistics: {
				session_count: 0,
				practice_minutes: 0,
				current_streak: 0,
				best_streak: 0
			},

			dashboard: {
				average_score: 0,
				best_skill: focusLabel,
				best_skill_score: 0,
				best_skill_percentile: 100
			},

			favorite_templates: [],
			recent_sessions: [],
			evc_trend: [],

			today_insight: {
				title: "첫 연습은 나의 말하기 기준을 세우는 시간입니다.",
				description: "Re:hear와 함께 발표와 면접에서 필요한 전달력을 차근차근 쌓아보세요."
			},

			current_goal: {
				title: createTrainingTitle(practiceFrequency),
				current_score: 0,
				target_score: 85,
				remaining_sessions: practiceFrequency,
				training_type: trainingType,
				training_type_label: trainingLabel,
				focus_area: focusArea,
				focus_area_label: focusLabel,
				practice_frequency: practiceFrequency
			},

			recommended_trainings: [
				{
					template_id: "training_01",
					title: focusArea === "content" ? "핵심 메시지 구조화" : "시선과 발화 속도 안정화",
					category: focusArea === "content" ? "내용 구성" : "전달 방식",
					difficulty: "쉬움"
				},
				{
					template_id: "training_02",
					title: trainingType === "interview" ? "면접 답변 구조 강화" : "발표 도입부 설득력 강화",
					category: trainingLabel,
					difficulty: "보통"
				},
				{
					template_id: "training_03",
					title: "Q&A 대응 루틴 만들기",
					category: "실전 대응",
					difficulty: "보통"
				}
			]
		};
	}
</script>

{#if currentStep === 2}
	<OdiJoinCompleteStep
		{nickname}
		level="새싹 보이스"
		onStartSession={startFirstSession}
		onGoHome={goHome}
	/>
{:else}
	<main class="join-page">
		<header class="page-header">
			<div class="title-group">
				<h1 class="text-title-main">{currentStep === 0 ? "Re:hear 시작하기" : "훈련 목표 설정하기"}</h1>
				<p class="subtitle text-caption-main">
					{currentStep === 0 ? "현재 로그인된 계정을 확인하고 Re:hear를 시작해보세요" : "훈련 목표를 설정하고 나에게 맞는 미션을 제공받으세요"}
				</p>
			</div>
		</header>

		<AuthStepper {steps} currentStep={currentStep} />

		{#if errorMessage}
			<p class="error-message text-caption-main">{errorMessage}</p>
		{/if}

		<section class="join-content">
			{#if currentStep === 0}
				<div class="account-step">
					<div class="account-summary">
						<div class="summary-icon">
							<img src={AccountCircle} alt="" />
						</div>

						<div class="summary-text">
							<p class="text-caption-main">현재 로그인된 MainAuth 계정</p>
							<strong>{mainName || "이름 없음"}</strong>
							<span>{mainEmail || "이메일 정보 없음"}</span>
						</div>

						<Button variant="secondary" width="180px" onclick={logoutMainAuth}>
							다른 계정으로
						</Button>
					</div>

					<div class="nickname-grid">
						<AuthField
							label="닉네임"
							placeholder="Re:hear에서 사용할 닉네임"
							icon={Person}
							bind:value={nickname}
							success={nicknameOk ? "사용할 수 있는 닉네임입니다" : ""}
							required
						/>

						<AuthField
							label="이메일"
							type="email"
							placeholder="현재 로그인 이메일"
							icon={Mail}
							value={mainEmail}
							disabled
						/>
					</div>

					<AgreementBox
						bind:allAgreed
						bind:serviceAgreed
						bind:privacyAgreed
						bind:marketingAgreed
						onOpenTerm={openTerm}
					/>
				</div>
			{:else}
				<OdiJoinGoalStep
					bind:trainingType
					bind:focusArea
					bind:practiceFrequency
				/>
			{/if}
		</section>

		<footer class="page-actions">
			<Button variant="secondary" width="360px" onclick={goPrevious}>
				이전 단계
			</Button>

			{#if currentStep === 0}
				<Button variant="primary" width="360px" disabled={!canNextFromAccount} onclick={goNextFromAccount}>
					다음 단계
				</Button>
			{:else}
				<Button variant="primary" width="360px" disabled={!canFinishGoal} onclick={completeJoin}>
					계정 설정 완료
				</Button>
			{/if}
		</footer>
	</main>
{/if}

<style>
	.join-page {
		min-height: calc(100vh - 72px);
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		background: var(--surface);
	}

	.page-header {
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.join-content {
		width: 100%;
		max-width: 1225px;
		margin: 0 auto;
	}

	.account-step {
		display: flex;
		flex-direction: column;
		gap: 48px;
	}

	.account-summary {
		width: 100%;
		padding: var(--space-5);
		display: flex;
		align-items: center;
		gap: var(--space-5);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.summary-icon {
		width: 56px;
		height: 56px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		background: var(--blue-light);
		flex-shrink: 0;
	}

	.summary-icon img {
		width: 36px;
		height: 36px;
		object-fit: contain;
	}

	.summary-text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.summary-text p {
		color: var(--text-secondary);
	}

	.summary-text strong {
		color: var(--brand-black);
		font-size: 22px;
		font-weight: var(--font-bold);
	}

	.summary-text span {
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
		word-break: break-all;
	}

	.nickname-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 40px;
	}

	.error-message {
		max-width: 1225px;
		width: 100%;
		margin: 0 auto;
		padding: var(--space-4) var(--space-5);
		border-radius: var(--radius-sm);
		background: var(--accent-light);
		color: var(--accent);
	}

	.page-actions {
		width: 100%;
		max-width: 1225px;
		margin: auto auto 0;
		display: flex;
		justify-content: flex-end;
		gap: var(--space-4);
	}

	@media (max-width: 1200px) {
		.nickname-grid {
			grid-template-columns: 1fr;
		}

		.account-summary {
			align-items: flex-start;
			flex-direction: column;
		}

		.page-actions {
			flex-direction: column;
		}
	}
</style>
