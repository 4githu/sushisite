<!-- src/routes/odi/session/presentation/ready/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { page } from "$app/state";
	import { onDestroy, onMount } from "svelte";

	import { session } from "$lib/odi/stores";
	import Button from "$lib/odi/components/common/Button.svelte";
	import SessionModeModal from "$lib/odi/components/session/SessionModeModal.svelte";

	const sessionStore = session as any;

	let pinCode = $state("");
	let preSessionState = $state("waiting");
	let sessionId = $state(null as string | null);
	let isRegenerating = $state(false);
	let presentationTimer: ReturnType<typeof setTimeout> | null = null;
	let showExperiencePrompt = $state(false);
	let sessionMode = $state<"waiting" | "experience" | "regular">("waiting");
	let presentationElapsed = $state(false);
	let isExperienceStarting = $state(false);
	let isRegularStarting = $state(false);
	let experienceError = $state("");
	const isExperienceSession = $derived(sessionMode === "experience");
	const displayedPinCode = $derived(isExperienceSession ? "1234" : pinCode);
	const fixedDemoDurationMs = 2 * 60 * 1000;

	function syncFromSessionStore(value: any = sessionStore) {
		const preSession = value.pre_session ?? value.preSession ?? {};

		pinCode = value.pin_code ?? value.pinCode ?? "";
		preSessionState = preSession.state ?? "waiting";
		sessionId = preSession.session_id ?? preSession.sessionId ?? null;
	}

	function startPresentationTimer() {
		if (presentationTimer !== null) clearTimeout(presentationTimer);
		presentationElapsed = false;
		presentationTimer = setTimeout(() => {
			presentationElapsed = true;
			presentationTimer = null;
		}, fixedDemoDurationMs);
	}

	onMount(() => {
		if (page.url.searchParams.get("choose") === "1") {
			sessionStore.clear?.();
		}
		syncFromSessionStore();

		if (pinCode) {
			sessionMode = "regular";
			sessionStore.pollUntilFinished?.();
		} else {
			// Wait VR의 첫 화면은 세션 생성이 아니라 사용자의 명시적인 모드 선택입니다.
			showExperiencePrompt = true;
		}
		if (preSessionState === "finished") {
			presentationElapsed = true;
		}
		const unsubscribe = sessionStore.subscribe?.((value: any) => {
			syncFromSessionStore(value);
		});

		return () => {
			if (presentationTimer !== null) clearTimeout(presentationTimer);
			if (typeof unsubscribe === "function") {
				unsubscribe();
			}
		};
	});

	onDestroy(() => {
		sessionStore.stopPolling?.();
	});

	const canOpenReport = $derived(preSessionState === "finished" && !!sessionId);
	const canClickReport = $derived(isExperienceSession ? !!sessionId : canOpenReport);
	const reportButtonVariant = $derived(isExperienceSession && !presentationElapsed ? "secondary" : "primary");

	async function startExperienceSession() {
		if (isExperienceStarting || isRegularStarting) return;

		isExperienceStarting = true;
		experienceError = "";
		showExperiencePrompt = false;
		sessionMode = "experience";

		try {
			await sessionStore.startFixedDemoPresentation?.();
			syncFromSessionStore(sessionStore.get?.());
			await sessionStore.finishFixedDemoPresentation?.();
			startPresentationTimer();
		} catch (error) {
			sessionMode = "waiting";
			experienceError = error instanceof Error ? error.message : "체험 세션을 시작하지 못했습니다.";
			showExperiencePrompt = true;
		} finally {
			isExperienceStarting = false;
		}
	}

	async function startRegularSession() {
		if (isExperienceStarting || isRegularStarting) return;

		isRegularStarting = true;
		experienceError = "";
		showExperiencePrompt = false;
		sessionMode = "regular";

		try {
			await sessionStore.startFromCurrentTemplate?.();
			syncFromSessionStore(sessionStore.get?.());
			sessionStore.pollUntilFinished?.();
		} catch (error) {
			sessionMode = "waiting";
			experienceError = error instanceof Error ? error.message : "일반 세션을 시작하지 못했습니다.";
			showExperiencePrompt = true;
		} finally {
			isRegularStarting = false;
		}
	}

	function selectSessionMode(mode: "experience" | "regular") {
		if (mode === "experience") {
			void startExperienceSession();
			return;
		}

		void startRegularSession();
	}

	async function regeneratePin() {
		if (isRegenerating) return;

		isRegenerating = true;

		try {
			showExperiencePrompt = true;
			sessionMode = "waiting";
			presentationElapsed = false;
			if (presentationTimer !== null) clearTimeout(presentationTimer);
			return;
		} finally {
			isRegenerating = false;
		}
	}

	async function openReport() {
		if (!canOpenReport || !sessionId) return;

		await sessionStore.getReport?.(sessionId);
		await goto(`/odi/report/${sessionId}`);
	}

</script>

<main class="ready-page">
	<div class="glow" aria-hidden="true"></div>

	<section class="ready-content">
		<div class="ready-title-group">
			<h1 class="text-title-main">{sessionMode === "waiting" ? "세션을 시작할 준비가 되었습니다" : "설정한 세션이 준비되었습니다"}</h1>
			<p class="pin-help text-title-middle">{sessionMode === "waiting" ? "시작하기를 눌러 진행할 세션을 선택하세요" : "생성된 PIN 번호를 가상 환경에서 입력하여 준비된 세션을 진행하세요"}</p>
		</div>

		{#if isExperienceSession}
			<p class="experience-chip">체험 세션</p>
		{/if}
		<p class="pin-code" class:demo-pin={isExperienceSession}>{displayedPinCode || "----"}</p>

		<div class="ready-actions">
			{#if sessionMode === "waiting"}
				<Button variant="primary" size="lg" width="464px" onclick={() => showExperiencePrompt = true}>세션 선택하기</Button>
			{:else}
				<Button variant="soft" size="lg" width="464px" disabled={isRegenerating} onclick={regeneratePin}>PIN 번호 다시 생성하기</Button>
			{/if}

			{#if canClickReport}
				<Button
					variant={reportButtonVariant}
					size="lg"
					width="464px"
					onclick={openReport}
				>
					결과 리포트 보기
				</Button>
			{:else}
				<Button
					variant="primary"
					size="lg"
					width="464px"
					disabled
				>
					발표가 완료되면 볼 수 있습니다
				</Button>
			{/if}

			<p class="report-help text-caption-medium">
				{isExperienceSession && canClickReport && !presentationElapsed
					? "발표 시간 전에도 리포트는 미리 확인할 수 있습니다."
					: canOpenReport
						? "세션이 완료되었습니다. 리포트를 확인할 수 있습니다."
						: isExperienceSession ? "체험 세션을 시작하면 결과 리포트를 볼 수 있습니다." : "발표가 끝나고 분석이 완료되면 리포트를 확인할 수 있습니다."}
			</p>

			{#if experienceError && !showExperiencePrompt}
				<p class="experience-error" role="alert">{experienceError}</p>
			{/if}
		</div>
	</section>

	{#if showExperiencePrompt}
		<SessionModeModal
			busy={isExperienceStarting || isRegularStarting}
			errorMessage={experienceError}
			onselect={selectSessionMode}
		/>
	{/if}
</main>

<style>
	.ready-page {
		position: relative;
		width: 100%;
		min-height: 100vh;
		display: flex;
		justify-content: center;
		background: var(--surface);
		overflow: hidden;
	}

	.glow {
		position: absolute;
		width: 160vw;
		height: 120vh;
		left: 50%;
		top: -70vh;
		transform: translateX(-50%);
		border-radius: var(--radius-full);
		background: radial-gradient(ellipse at center, rgba(0, 51, 255, 0.28) 0%, rgba(0, 51, 255, 0) 68%);
		pointer-events: none;
	}

	.ready-content {
		position: relative;
		z-index: 1;
		width: min(900px, 100%);
		padding: 120px 40px 80px;
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
	}

	.ready-title-group {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-4);
	}

	.pin-help {
		color: var(--primary);
		font-weight: var(--font-medium);
	}

	.pin-code {
		margin-top: 96px;
		color: var(--brand-dark);
		font-family: var(--font-family);
		font-size: 190px;
		font-weight: var(--font-medium);
		line-height: 1;
		letter-spacing: 7.6px;
	}

	.pin-code.demo-pin {
		color: var(--primary);
	}

	.experience-chip { margin: 46px 0 -74px; padding: 6px 12px; border-radius: var(--radius-full); background: rgba(0, 51, 255, 0.08); color: var(--primary); font-size: 14px; font-weight: var(--font-bold); }

	.ready-actions {
		margin-top: 86px;
		width: 464px;
		display: flex;
		flex-direction: column;
		align-items: stretch;
		gap: var(--space-4);
	}

	.report-help {
		color: var(--text-disabled);
	}

	.experience-error { margin: 0; color: var(--accent); }

</style>
