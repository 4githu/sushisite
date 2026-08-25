<!-- src/lib/odi/components/report/ReportPageView.svelte -->

<script lang="ts">
	import ReportHeader from "./ReportHeader.svelte";
	import ScoreOverviewCard from "./ScoreOverviewCard.svelte";
	import DetailAnalysisCard from "./DetailAnalysisCard.svelte";
	import TimelineFeedbackCard from "./TimelineFeedbackCard.svelte";
	import AudienceReactionCard from "./AudienceReactionCard.svelte";
	import AIInsightCard from "./AIInsightCard.svelte";

	import type { ReportFeedback, ReportSession } from "./reportTypes";

	let {
		session,
		onOpenPrevious,
		onDownload,
		onStartTraining
	}: {
		session: ReportSession;
		onOpenPrevious?: () => void;
		onDownload?: () => void;
		onStartTraining?: () => void;
	} = $props();

	const feedback = $derived((session.feedback ?? {}) as ReportFeedback);
	const generationWarnings = $derived(feedback.generation?.warnings ?? []);
</script>

<div class="report-page-view">
	<ReportHeader
		{session}
		{feedback}
		{onOpenPrevious}
		{onDownload}
	/>

	{#if generationWarnings.length > 0}
		<section class="generation-notice" aria-label="분석 데이터 안내">
			<strong>일부 입력이 제한된 상태로 분석되었습니다.</strong>
			<span>{generationWarnings.join(", ")}</span>
		</section>
	{/if}

	<section class="top-grid">
		<ScoreOverviewCard {feedback} />
		<DetailAnalysisCard {feedback} />
		<TimelineFeedbackCard {feedback} />
	</section>

	<section class="bottom-card">
		<div class="bottom-grid">
			<AudienceReactionCard {feedback} />
			<AIInsightCard {feedback} onStartTraining={onStartTraining} />
		</div>
	</section>
</div>

<style>
	.report-page-view {
		width: 100%;
		container-type: inline-size;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		background: var(--surface);
	}

	.generation-notice {
		padding: 12px 16px;
		display: flex;
		gap: var(--space-3);
		border-radius: var(--radius-sm);
		background: #fff8df;
		color: var(--text-secondary);
		font-size: 14px;
	}

	.generation-notice strong {
		color: var(--brand-black);
	}

	.top-grid {
		display: grid;
		grid-template-columns: 443px minmax(0, 1fr) 440px;
		gap: var(--space-5);
		align-items: stretch;
	}

	.bottom-card {
		padding: 24px 28px;
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
	}

	.bottom-grid {
		display: grid;
		grid-template-columns: minmax(0, 1.15fr) minmax(360px, 0.85fr);
		gap: var(--space-8);
		align-items: center;
	}

	/* 사이드바와 확대 배율을 포함한 실제 리포트 폭을 기준으로 전환합니다. */
	@container (max-width: 1500px) {
		.top-grid {
			grid-template-columns: 1fr;
		}
	}

	@container (max-width: 1100px) {
		.bottom-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
