<!-- src/routes/odi/session/presentation/ready/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onDestroy, onMount } from "svelte";

	import { API_BASE as API } from "$lib/config/api";
	import { session } from "$lib/odi/stores";
	import Button from "$lib/odi/components/common/Button.svelte";

	const sessionStore = session as any;

	let pinCode = $state("");
	let preSessionState = $state("waiting");
	let sessionId = $state(null as string | null);
	let previewSessionId = $state(null as string | null);
	let isRegenerating = $state(false);

	function syncFromSessionStore(value: any = sessionStore) {
		const preSession = value.pre_session ?? value.preSession ?? {};

		pinCode = value.pin_code ?? value.pinCode ?? "";
		preSessionState = preSession.state ?? "waiting";
		sessionId = preSession.session_id ?? preSession.sessionId ?? null;
	}

	async function loadPreviewReport() {
		try {
			// 계정별 저장 목록이 아닌 공용 시연 리포트를 사용합니다.
			const response = await fetch(`${API}/odi/db/demo-report`, { credentials: "include" });
			const data = await response.json().catch(() => null);
			previewSessionId = response.ok ? (data?.session?.session_id ?? null) : null;
		} catch {
			previewSessionId = null;
		}
	}

	onMount(() => {
		syncFromSessionStore();

		sessionStore.pollUntilFinished?.();
		void loadPreviewReport();

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

	async function openPreviewReport() {
		if (!previewSessionId) return;

		await sessionStore.getReport?.(previewSessionId);
		await goto(`/odi/report/${previewSessionId}`);
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

			{#if canOpenReport}
				<Button
					variant="primary"
					size="lg"
					width="464px"
					onclick={openReport}
				>
					리포트 보기
				</Button>
			{:else}
				<Button
					variant="primary"
					size="lg"
					width="464px"
					disabled={!previewSessionId}
					onclick={openPreviewReport}
				>
					리포트 보기
				</Button>
			{/if}

			<p class="report-help text-caption-medium">
				{canOpenReport
					? "세션이 완료되었습니다. 리포트를 확인할 수 있습니다."
					: previewSessionId
						? "발표가 끝난 뒤 들어가시면 만들어진 리포트를 보실 수 있습니다."
						: "저장된 리포트를 불러오는 중입니다."}
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
