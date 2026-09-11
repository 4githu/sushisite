<script lang="ts">
	import ReportHeader from './ReportHeader.svelte';
	import ScoreOverviewCard from './ScoreOverviewCard.svelte';
	import DetailAnalysisCard from './DetailAnalysisCard.svelte';
	import TimelineFeedbackCard from './TimelineFeedbackCard.svelte';
	import AudienceReactionCard from './AudienceReactionCard.svelte';
	import AIInsightCard from './AIInsightCard.svelte';

	import type { ReportFeedback, ReportSession } from './reportTypes';

	let {
		session,
		showTimelineVideo = true,
		onOpenPrevious,
		onDownload,
		onStartTraining
	}: {
		session: ReportSession;
		showTimelineVideo?: boolean;
		onOpenPrevious?: () => void;
		onDownload?: () => void;
		onStartTraining?: () => void;
	} = $props();

	const feedback = $derived((session.feedback ?? {}) as ReportFeedback);
	const generationWarnings = $derived(feedback.generation?.warnings ?? []);
</script>

<div class="report-page-view-v1" data-report-version="v1">
	<ReportHeader {session} {feedback} {onOpenPrevious} {onDownload} />

	{#if generationWarnings.length > 0}
		<section class="generation-notice" aria-label="분석 데이터 안내">
			<strong>일부 입력이 제한된 상태로 분석되었습니다.</strong>
			<span>{generationWarnings.join(', ')}</span>
		</section>
	{/if}

	<section class="top-grid" aria-label="기본 결과 리포트">
		<ScoreOverviewCard {feedback} comparison={session.comparison} />
		<DetailAnalysisCard {feedback} />
		<TimelineFeedbackCard {feedback} sessionId={session.session_id} showMedia={showTimelineVideo} />
	</section>

	<section class="bottom-card">
		<div class="bottom-grid">
			<AudienceReactionCard {feedback} />
			<AIInsightCard {feedback} {onStartTraining} />
		</div>
	</section>
</div>

<style>
	.report-page-view-v1 {
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
		flex-wrap: wrap;
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

	@container (max-width: 520px) {
		.bottom-card {
			padding: 20px;
		}
	}
</style>
