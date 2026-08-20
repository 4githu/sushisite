<!-- src/routes/odi/session/presentation/audience/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { template, type PresentationTemplate } from "$lib/odi/stores";
	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import TipCard from "$lib/odi/components/session/TipCard.svelte";
	import PresentationAISettingCard from "$lib/odi/components/session/PresentationAISettingCard.svelte";
	import {Check, whiteright as grayright} from "$lib/odi/icons"

	type PersonaType = "" | "general" | "student" | "judge" | "mixed";

	const steps = [
		{ label: "발표 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 청중 설정" },
		{ label: "세션 확인" }
	];

	let ready = $state(false);
	let isSaving = $state(false);
	let saveError = $state("");

	let personaType = $state("" as PersonaType);
	let audienceSize = $state(0);
	let expertiseLevel = $state(0);
	let interestLevel = $state(0);

	function ensurePresentationDraft(): PresentationTemplate {
		const current = template.get();

		if (current?.type === "presentation") {
			return current;
		}

		// HMR/새로고침으로 store가 비어도 다른 사용자의 recent draft를 복원하지 않습니다.
		template.setDefault("presentation");
		return template.get() as PresentationTemplate;
	}

	function toPersonaType(value: string): PersonaType {
		if (value === "general" || value === "student" || value === "judge" || value === "mixed") {
			return value;
		}

		if (value === "일반 청중") return "general";
		if (value === "학생 중심") return "student";
		if (value === "심사위원 중심") return "judge";
		if (value === "혼합") return "mixed";

		return "";
	}

	function toAudienceType(value: PersonaType) {
		if (value === "") return "";
		if (value === "general") return "일반 청중";
		if (value === "student") return "학생 중심";
		if (value === "judge") return "심사위원 중심";
		return "혼합";
	}

	function toLevelNumber(value: string) {
		if (!value) return 0;
		if (value === "낮음") return 1;
		if (value === "높음") return 3;
		return 2;
	}

	function toLevelText(value: number) {
		if (value === 0) return "";
		if (value === 1) return "낮음";
		if (value === 3) return "높음";
		return "중간";
	}

	onMount(() => {
		const draft = ensurePresentationDraft();

		personaType = toPersonaType(draft.audience.audience_type);
		audienceSize = draft.audience.audience_count || 6;
		expertiseLevel = toLevelNumber(draft.audience.expertise_level) || 2;
		interestLevel = toLevelNumber(draft.audience.interest_level) || 2;

		ready = true;
	});

	$effect(() => {
		if (!ready) return;

		template.patchAudience({
			audience_type: toAudienceType(personaType),
			audience_count: audienceSize,
			expertise_level: toLevelText(expertiseLevel),
			interest_level: toLevelText(interestLevel)
		});
	});

	const canNext = $derived(
		personaType !== "" &&
		expertiseLevel >= 1 &&
		interestLevel >= 1
	);

	async function goNext() {
		if (isSaving) return;

		isSaving = true;
		saveError = "";

		try {
			// Wait VR에서 새로고침되어 메모리 store가 초기화돼도 일반 세션이 현재
			// 발표 자료와 옵션을 서버 recent_template에서 복구할 수 있게 보존합니다.
			await template.saveToRecent();
			await goto("/odi/session/presentation/confirm");
		} catch (error) {
			saveError = error instanceof Error ? error.message : "발표 설정을 저장하지 못했습니다.";
		} finally {
			isSaving = false;
		}
	}
</script>

<main class="session-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">AI 청중 설정</h1>
			<p class="subtitle text-caption-main">청중 페르소나를 설정하여 원하는 발표 분위기를 구성할 수 있어요.</p>
		</div>
	</header>

	<ProgressStepper {steps} currentStep={2} />

	<section class="content-grid">
		<PresentationAISettingCard
			bind:personaType
			bind:audienceSize
			bind:expertiseLevel
			bind:interestLevel
		/>

		<TipCard
			title="청중 페르소나 선택 TIP"
			description="AI 청중은 실시간으로 발표에 반응합니다."
			tips={[
				{
					icon: Check,
					description: "청중 유형에 따라 질문 수준과 반응이 달라집니다."
				},
				{
					icon: Check,
					description: "발표 내용에 맞춰 피드백을 제공합니다."
				},
				{
					icon: Check,
					description: "실제 청중처럼 다양한 반응을 경험할 수 있습니다."
				},
				{
					icon: Check,
					description: "전문성을 고려한 현실적인 질의를 제공합니다."
				},
				{
					icon: Check,
					description: "청중 규모와 분위기에 따라 발표 몰입도와 대응력을 효과적으로 훈련할 수 있습니다."
				}
			]}
		/>
	</section>

	<footer class="page-actions">
		{#if saveError}
			<p class="save-error" role="alert">{saveError}</p>
		{/if}
		<Button
			variant="primary"
			width="212px"
			onclick={() => goto("/odi/session/presentation/upload")}
		>
			이전 단계
		</Button>

		<Button
			variant="primary"
			width="212px"
			disabled={!canNext || isSaving}
			trailingIcon={grayright}
			onclick={goNext}
		>
			{isSaving ? "설정 저장 중..." : "다음 단계"}
		</Button>
	</footer>
</main>

<style>
	.session-page {
		width: 100%;
		min-height: 100vh;
		padding: 36px 48px 40px;
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

	.page-label {
		color: var(--primary);
	}

	.title-group {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.subtitle {
		color: var(--text-secondary);
	}

	.content-grid {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 432px;
		gap: var(--space-5);
		align-items: stretch;
	}

	.page-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-4);
	}

	.save-error { margin: auto 0; color: var(--accent); font-size: 14px; }

	@media (max-width: 1280px) {
		.content-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 640px) {
		.session-page { padding: 24px 16px 32px; }
		.page-actions { align-items: stretch; flex-direction: column-reverse; }
		.page-actions :global(.button) { width: 100% !important; }
	}
</style>
