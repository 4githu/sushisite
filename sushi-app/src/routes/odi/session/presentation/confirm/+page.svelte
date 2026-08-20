<!-- src/routes/odi/session/presentation/confirm/+page.svelte -->

<script lang="ts">
	import { onMount } from "svelte";
	import presenimage from "$lib/odi/assets/presentation-ready.png";

	import { template, type PresentationTemplate } from "$lib/odi/stores";
	import { auth } from "$lib/stores/mainauth";
	import SessionConfirmCard from "$lib/odi/components/session/SessionConfirmCard.svelte";
	import SessionModeModal from "$lib/odi/components/session/SessionModeModal.svelte";

	import {
		sessiontime,
		audiencenum,
		audiencepersona,
		podium as sessionenviron,
		goggle
	} from "$lib/odi/icons";

	let draft = $state(null as PresentationTemplate | null);
	let clientReady = $state(false);
	let showSessionModeModal = $state(false);
	let isCheckingAccount = $state(false);
	let startError = $state("");

	const EXPERIENCE_ACCOUNT_EMAIL = "xrealrehear@gmail.com";

	function ensurePresentationDraft(): PresentationTemplate {
		const current = template.get();

		if (current?.type === "presentation") {
			return current;
		}

		// 확인 화면도 새 세션 흐름에서 이전 recent_template를 표시하면 안 됩니다.
		template.setDefault("presentation");
		return template.get() as PresentationTemplate;
	}

	onMount(() => {
		draft = ensurePresentationDraft();
		clientReady = true;
	});

	async function getCurrentEmail() {
		// 레이아웃에 남아 있을 수 있는 이전 인증 store 대신 서버 쿠키를 다시 확인합니다.
		const payload = await auth.check();
		return payload?.data?.email?.trim().toLowerCase() ?? "";
	}

	async function openSession() {
		if (!clientReady || isCheckingAccount) return;

		isCheckingAccount = true;
		startError = "";

		try {
			const email = await getCurrentEmail();

			if (email === EXPERIENCE_ACCOUNT_EMAIL) {
				showSessionModeModal = true;
				return;
			}

			window.location.assign("/odi/waitvr?mode=regular");
		} catch (error) {
			startError = error instanceof Error ? error.message : "세션을 시작하지 못했습니다.";
		} finally {
			isCheckingAccount = false;
		}
	}

	function selectSessionMode(mode: "experience" | "regular") {
		showSessionModeModal = false;
		window.location.assign(`/odi/waitvr?mode=${mode}`);
	}

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

</script>

<main class="confirm-page">
	<header class="page-header">
		<p class="page-label text-caption-main">Session Setup</p>

		<div class="title-group">
			<h1 class="text-title-main">Ready for Re:hear 🌟</h1>
			<p class="subtitle text-caption-main">모든 설정이 완료되었어요. 대기 중인 AI 청중과 함께 실전 같은 발표 연습을 시작해보세요!</p>
		</div>
	</header>

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
		<button
			type="button"
			class="start-link clickable text-button-start"
			disabled={!clientReady || isCheckingAccount}
			onclick={openSession}
		>
			<img src={goggle} alt="" />
			<span>{!clientReady ? "페이지 준비 중..." : isCheckingAccount ? "계정 확인 중..." : "시작하기"}</span>
		</button>

		<p class="start-help text-caption-medium">클릭하면 업로드 파일이 세션 파일로 확정되고, 발표 PDF는 이미지로 변환됩니다.</p>
		{#if startError}
			<p class="start-error" role="alert">{startError}</p>
		{/if}
	</section>

	{#if showSessionModeModal}
		<SessionModeModal onselect={selectSessionMode} />
	{/if}
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

	.start-link {
		width: 464px;
		height: 63px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
		padding-inline: var(--space-5);
		border-radius: var(--radius-sm);
		border: 0;
		background: var(--primary);
		color: var(--text-on-primary);
		text-decoration: none;
	}

	.start-link:hover { background: var(--primary-hover); }
	.start-link:disabled { cursor: wait; opacity: .7; }
	.start-link img { width: 24px; height: 24px; }

	.start-help {
		color: var(--text-disabled);
	}

	.start-error { margin: 0; color: var(--accent); font-size: 14px; }
</style>
