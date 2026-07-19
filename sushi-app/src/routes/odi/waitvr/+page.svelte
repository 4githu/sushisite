<!-- src/routes/odi/session/presentation/ready/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onDestroy, onMount } from "svelte";

	import { session } from "$lib/odi/stores";
	import Button from "$lib/odi/components/common/Button.svelte";

	const sessionStore = session as any;

	let pinCode = $state("");
	let preSessionState = $state("waiting");
	let sessionId = $state(null as string | null);
	let isRegenerating = $state(false);

	function syncFromSessionStore(value: any = sessionStore) {
		const preSession = value.pre_session ?? value.preSession ?? {};

		pinCode = value.pin_code ?? value.pinCode ?? "";
		preSessionState = preSession.state ?? "waiting";
		sessionId = preSession.session_id ?? preSession.sessionId ?? null;
	}

	onMount(() => {
		syncFromSessionStore();

		sessionStore.pollUntilFinished?.();

		const unsubscribe = sessionStore.subscribe?.((value: any) => {
			syncFromSessionStore(value);
		});

		return () => {
			if (typeof unsubscribe === "function") {
				unsubscribe();
			}
		};
	});

	onDestroy(() => {
		sessionStore.stopPolling?.();
	});

	const canOpenReport = $derived(preSessionState === "finished" && !!sessionId);

	async function regeneratePin() {
		if (isRegenerating) return;

		isRegenerating = true;

		try {
			await sessionStore.startFromCurrentTemplate?.();
			syncFromSessionStore();
			sessionStore.pollUntilFinished?.();
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
			<h1 class="text-title-main">설정한 세션이 준비되었습니다</h1>
			<p class="pin-help text-title-middle">생성된 PIN 번호를 가상 환경에서 입력하여 준비된 세션을 진행하세요</p>
		</div>

		<p class="pin-code">{pinCode || "----"}</p>

		<div class="ready-actions">
			<Button
				variant="soft"
				size="lg"
				width="464px"
				disabled={isRegenerating}
				onclick={regeneratePin}
			>
				PIN 번호 다시 생성하기
			</Button>

			<Button
				variant="primary"
				size="lg"
				width="464px"
				disabled={!canOpenReport}
				onclick={openReport}
			>
				리포트 보러가기
			</Button>

			<p class="report-help text-caption-medium">
				{canOpenReport ? "세션이 완료되었습니다. 리포트를 확인할 수 있습니다." : "세션이 완료되면 버튼이 활성화됩니다."}
			</p>
		</div>
	</section>
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
</style>