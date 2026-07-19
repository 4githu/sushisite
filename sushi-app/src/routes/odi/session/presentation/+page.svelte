<!-- src/routes/odi/session/presentation/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { template, type PresentationTemplate } from "$lib/odi/stores";
	import ProgressStepper from "$lib/odi/components/session/ProgressStepper.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import PresentationSessionBasicInfoCard from "$lib/odi/components/session/PresentationSessionBasicInfoCard.svelte";

	import {whiteright} from '$lib/odi/icons'
	const steps = [
		{ label: "발표 기본 정보" },
		{ label: "자료 업로드" },
		{ label: "AI 청중 설정" },
		{ label: "세션 확인" }
	];


	let ready = $state(false);

	let title = $state("");
	let purpose = $state("");
	let language = $state("한국어");
	let place = $state("");
	let durationMinutes = $state(10);
	let questionCount = $state(3);

	function ensurePresentationDraft(): PresentationTemplate {
		const current = template.get();

		if (current?.type === "presentation") {
			return current;
		}

		return template.loadOrCreate("presentation") as PresentationTemplate;
	}

	onMount(() => {
		const draft = ensurePresentationDraft();

		title = draft.environment.title;
		purpose = draft.environment.purpose;
		language = draft.environment.language;
		place = draft.environment.place;
		durationMinutes = draft.environment.duration_minutes;
		questionCount = draft.environment.question_count;

		ready = true;
	});

	$effect(() => {
		if (!ready) return;

		template.patchEnvironment({
			title,
			purpose,
			language,
			place,
			duration_minutes: durationMinutes,
			question_count: questionCount
		});
	});

	const canNext = $derived(
		title.trim().length > 0 &&
		purpose.trim().length > 0 &&
		language.trim().length > 0 &&
		place.trim().length > 0 &&
		durationMinutes > 0 &&
		questionCount > 0
	);
</script>

<main class="session-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">발표 기본 정보</h1>
			<p class="subtitle text-caption-main">실전과 같은 환경을 설정하고, AI 청중과 함께 연습을 시작해요.</p>
		</div>
	</header>

	<ProgressStepper {steps} currentStep={0} />

	<PresentationSessionBasicInfoCard
		bind:title
		bind:purpose
		bind:language
		bind:place
		bind:durationMinutes
		bind:questionCount
	/>

	<footer class="page-actions">
		<Button variant="secondary" width="212px" onclick={() => goto("/odi")} >홈으로</Button>

		<Button
			variant="primary"
			width="212px"
			trailingIcon={whiteright}
			onclick={() => goto("/odi/session/presentation/upload")}
		>
			다음 단계
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

	.page-actions {
		display: flex;
		justify-content: flex-end;
		gap: var(--space-4);
	}
</style>