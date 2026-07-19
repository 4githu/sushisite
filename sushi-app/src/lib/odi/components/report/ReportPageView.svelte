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
		onOpenAllFeedback,
		onStartTraining
	}: {
		session: ReportSession;
		onOpenPrevious?: () => void;
		onDownload?: () => void;
		onOpenAllFeedback?: () => void;
		onStartTraining?: () => void;
	} = $props();

	const feedback = $derived((session.feedback ?? {}) as ReportFeedback);
</script>

<div class="report-page-view">
	<ReportHeader
		{session}
		{feedback}
		{onOpenPrevious}
		{onDownload}
	/>

	<section class="top-grid">
		<ScoreOverviewCard {feedback} />
		<DetailAnalysisCard {feedback} />
		<TimelineFeedbackCard {feedback} onOpenAll={onOpenAllFeedback} />
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
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
		background: var(--surface);
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
		grid-template-columns: minmax(0, 1.15fr) minmax(420px, 0.85fr);
		gap: var(--space-10);
		align-items: center;
	}

	@media (max-width: 1500px) {
		.top-grid {
			grid-template-columns: 1fr;
		}

		.bottom-grid {
			grid-template-columns: 1fr;
		}
	}
</style>