<!-- src/lib/odi/components/report/AIInsightCard.svelte -->

<script lang="ts">
	import type { ReportFeedback } from "./reportTypes";

	let {
		feedback,
		onStartTraining
	}: {
		feedback: ReportFeedback;
		onStartTraining?: () => void;
	} = $props();

	const title = $derived(feedback.ai_insight?.title ?? "AI 인사이트가 아직 생성되지 않았습니다.");
	const description = $derived(feedback.ai_insight?.description ?? "");
</script>

<section class="ai-card">
	<div class="text-area">
		<h2>AI 인사이트</h2>
		<strong>{title}</strong>

		{#if description}
			<p>{description}</p>
		{/if}
	</div>

	<button type="button" class="training-button clickable" onclick={onStartTraining}>
		<span>맞춤 훈련 시작</span>
		<span>›</span>
	</button>
</section>

<style>
	.ai-card {
		min-width: 0;
		padding: 8px 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.text-area {
		display: flex;
		flex-direction: column;
		gap: 11px;
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	strong {
		color: var(--primary);
		font-size: 22px;
		font-weight: var(--font-bold);
		line-height: 140%;
		white-space: pre-line;
	}

	p {
		color: var(--text-secondary);
		font-size: 18px;
		font-weight: var(--font-medium);
		line-height: 145%;
	}

	.training-button {
		width: 100%;
		height: 50px;
		padding: 11px 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border-radius: var(--radius-sm);
		background: var(--primary);
		color: var(--text-on-primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.training-button:hover {
		background: var(--primary-hover);
	}

</style>
