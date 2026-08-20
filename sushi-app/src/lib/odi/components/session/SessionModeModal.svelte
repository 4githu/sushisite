<script lang="ts">
	import SessionTypeCard from "$lib/odi/components/session/SessionTypeCard.svelte";
	import Button from "$lib/odi/components/common/Button.svelte";
	import ExperienceImage from "$lib/odi/assets/presentation-ready.png";
	import RegularImage from "$lib/odi/assets/session-presentation.png";

	type SessionMode = "experience" | "regular";

	let {
		busy = false,
		errorMessage = "",
		onselect
	}: {
		busy?: boolean;
		errorMessage?: string;
		onselect?: (mode: SessionMode) => void;
	} = $props();

	let selectedMode = $state<SessionMode | null>(null);

	function startSelectedSession() {
		if (selectedMode === null || busy) return;
		onselect?.(selectedMode);
	}
</script>

<div class="modal-overlay" role="presentation">
	<div class="popup-card" role="dialog" aria-modal="true" aria-labelledby="session-mode-title">
		<div class="modal-content">
			<header class="modal-header">
				<p class="eyebrow">Session Type</p>
				<h2 id="session-mode-title" class="modal-title">진행할 세션을 선택해 주세요</h2>
				<p class="modal-description text-caption-medium">
					처음 이용한다면 주요 기능을 자연스럽게 둘러볼 수 있는 체험 세션을 추천해요.
				</p>
			</header>

			<div class="card-row">
				<SessionTypeCard
					title="체험 세션"
					description={`AI 청중 반응부터 결과 리포트까지\nRe:hear의 주요 기능을 경험해요.`}
					meta="2분 · 한국어 · AI 청중 6명"
					badge="추천"
					image={ExperienceImage}
					selected={selectedMode === "experience"}
					onselect={() => selectedMode = "experience"}
				/>

				<SessionTypeCard
					title="일반 세션"
					description={`방금 설정한 발표 자료와 옵션으로\n실제 세션을 시작해요.`}
					meta="현재 설정 그대로 진행"
					image={RegularImage}
					selected={selectedMode === "regular"}
					onselect={() => selectedMode = "regular"}
				/>
			</div>

			<Button
				variant="primary"
				width="100%"
				disabled={selectedMode === null || busy}
				onclick={startSelectedSession}
			>
				{busy ? "세션 준비 중..." : "선택한 세션으로 시작하기"}
			</Button>

			{#if errorMessage}
				<p class="error-message" role="alert">{errorMessage}</p>
			{/if}
		</div>
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		inset: 0;
		z-index: 1100;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 16px;
		background: rgba(3, 8, 18, 0.55);
		backdrop-filter: blur(2px);
		overflow-y: auto;
	}

	.popup-card {
		position: relative;
		box-sizing: border-box;
		width: 720px;
		max-width: 100%;
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: 0 0 16px rgba(0, 0, 0, 0.15);
	}

	.modal-content {
		padding: 36px 40px 32px;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 22px;
	}

	.modal-header {
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		text-align: center;
	}

	.eyebrow {
		margin: 0;
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-bold);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.modal-title {
		margin: 0;
		color: var(--brand-black);
		font-size: 24px;
		font-weight: var(--font-bold);
	}

	.modal-description {
		margin: 0;
		color: var(--text-secondary);
	}

	.card-row {
		width: 100%;
		display: flex;
		justify-content: center;
		gap: 20px;
	}

	.error-message {
		margin: 0;
		color: var(--accent);
		font-size: 14px;
		text-align: center;
	}

	@media (max-width: 640px) {
		.modal-overlay { padding: 20px; align-items: flex-start; }
		.modal-content { padding: 36px 20px 24px; }
		.card-row { flex-direction: column; align-items: center; }
	}
</style>
