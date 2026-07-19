<!-- src/routes/odi/session/presentation/confirm/+page.svelte -->

<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import presenimage from "$lib/odi/assets/presentation-ready.png";

	import { template, session, type PresentationTemplate } from "$lib/odi/stores";
	import Button from "$lib/odi/components/common/Button.svelte";
	import SessionConfirmCard from "$lib/odi/components/session/SessionConfirmCard.svelte";

	import {
		sessiontime,
		audiencenum,
		audiencepersona,
		podium as sessionenviron,
		goggle
	} from "$lib/odi/icons";

	const sessionStore = session as any;

	let draft = $state(null as PresentationTemplate | null);
	let isStarting = $state(false);
	let errorMessage = $state("");

	function ensurePresentationDraft(): PresentationTemplate {
		const current = template.get();

		if (current?.type === "presentation") {
			return current;
		}

		return template.loadOrCreate("presentation") as PresentationTemplate;
	}

	onMount(() => {
		draft = ensurePresentationDraft();
	});

	const title = $derived(draft?.environment.title || "발표 제목 없음");
	const purpose = $derived(draft?.environment.purpose || "발표 목적 없음");
	const duration = $derived(`${draft?.environment.duration_minutes ?? 10}분`);
	const place = $derived(draft?.environment.place || "발표 환경 없음");
	const audienceSize = $derived(`${draft?.audience.audience_count ?? 6}명`);
	const persona = $derived(
		`전문성 ${draft?.audience.expertise_level ?? "중간"} + 관심도 ${draft?.audience.interest_level ?? "중간"}`
	);

	const slideName = $derived(draft?.files.slide?.original_name ?? "발표자료 없음");
	const paperName = $derived(draft?.files.paper?.original_name ?? "논문 없음");

	const summaryItems = $derived([
		{ label: "발표 시간", value: duration, icon: sessiontime },
		{ label: "발표 환경", value: place, icon: sessionenviron },
		{ label: "청중 규모", value: audienceSize, icon: audiencenum },
		{ label: "청중 페르소나", value: persona, icon: audiencepersona }
	]);

	async function startPresentationSession() {
		if (isStarting) return;

		isStarting = true;
		errorMessage = "";

		try {
			await sessionStore.startFromCurrentTemplate?.();
			await goto("/odi/waitvr");
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "세션 시작에 실패했습니다.";
		} finally {
			isStarting = false;
		}
	}
</script>

<main class="confirm-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">Ready for Re:hear 🌟</h1>
			<p class="subtitle text-caption-main">모든 설정이 완료되었어요. 대기 중인 AI 청중과 함께 실전 같은 발표 연습을 시작해보세요!</p>
		</div>
	</header>

	{#if errorMessage}
		<p class="error-message text-caption-medium">{errorMessage}</p>
	{/if}

	<section class="info-card">
		<p class="text-body-medium">발표 정보</p>

		<div class="info-line">
			<strong class="text-body-bold">{title}</strong>
			<span class="dot">·</span>
			<strong class="text-body-bold">{purpose}</strong>
		</div>

		<div class="file-line text-caption-medium">
			<span>발표자료: {slideName}</span>
			<span>논문: {paperName}</span>
		</div>
	</section>

	<SessionConfirmCard
		previewImage={presenimage}
		items={summaryItems}
	/>

	<section class="start-area">
		<Button
			variant="primary"
			size="lg"
			width="464px"
			leadingIcon={goggle}
			disabled={isStarting}
			onclick={startPresentationSession}
		>
			{isStarting ? "세션 파일 준비 중..." : "시작하기"}
		</Button>

		<p class="start-help text-caption-medium">클릭하면 업로드 파일이 세션 파일로 확정되고, 발표 PDF는 이미지로 변환됩니다.</p>
	</section>
</main>

<style>
	.confirm-page {
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

	.error-message {
		padding: var(--space-4) var(--space-5);
		border-radius: var(--radius-sm);
		background: var(--accent-light);
		color: var(--accent);
	}

	.info-card {
		min-height: 132px;
		padding: var(--space-3);
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 14px;
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
	}

	.info-line {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 14px;
		color: var(--text-primary);
	}

	.file-line {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-6);
		color: var(--text-secondary);
	}

	.dot {
		font-size: 22px;
		font-weight: var(--font-bold);
		color: var(--text-primary);
	}

	.start-area {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-3);
		margin-top: var(--space-2);
	}

	.start-help {
		color: var(--text-disabled);
	}
</style>