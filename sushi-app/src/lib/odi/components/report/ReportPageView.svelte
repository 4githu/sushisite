<script lang="ts">
	import ReportHeader from './ReportHeader.svelte';
	import ScoreOverviewCard from './ScoreOverviewCard.svelte';
	import MetricMeaningCard from './MetricMeaningCard.svelte';
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

<div class="report-page-view" data-report-version="v2">
	<ReportHeader {session} {feedback} {onOpenPrevious} {onDownload} />

	{#if generationWarnings.length > 0}
		<section class="generation-notice" aria-label="분석 데이터 안내">
			<strong>일부 입력이 제한된 상태로 분석되었습니다.</strong>
			<span>{generationWarnings.join(', ')}</span>
		</section>
	{/if}

	<section class="report-section" aria-labelledby="summary-title">
		<div class="section-heading">
			<span>1</span>
			<div>
				<p>한눈에 보는 결과</p>
				<h2 id="summary-title">총점과 핵심 결과</h2>
			</div>
		</div>

		<div class="summary-grid">
			<ScoreOverviewCard {feedback} comparison={session.comparison} />
			<div class="key-result-card">
				<AIInsightCard {feedback} {onStartTraining} />
			</div>
		</div>
	</section>

	<section class="report-section" aria-labelledby="meaning-title">
		<div class="section-heading">
			<span>2</span>
			<div>
				<p>점수 해석</p>
				<h2 id="meaning-title">지표의 의미와 평가 기준</h2>
			</div>
		</div>
		<MetricMeaningCard {feedback} />
	</section>

	<section class="report-section" aria-labelledby="action-title">
		<div class="section-heading">
			<span>3</span>
			<div>
				<p>다음 발표에서 바꿀 점</p>
				<h2 id="action-title">개선이 필요한 행동</h2>
			</div>
		</div>
		<TimelineFeedbackCard {feedback} sessionId={session.session_id} showMedia={showTimelineVideo} />
	</section>

	<section class="report-section" aria-labelledby="evidence-title">
		<div class="section-heading">
			<span>4</span>
			<div>
				<p>점수의 근거</p>
				<h2 id="evidence-title">상세 분석과 청중 반응</h2>
			</div>
		</div>

		<div class="evidence-grid">
			<DetailAnalysisCard {feedback} />
			<div class="audience-card-shell"><AudienceReactionCard {feedback} /></div>
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
		gap: clamp(32px, 4vw, 64px);
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

	.report-section {
		display: grid;
		gap: var(--space-5);
	}

	.section-heading {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.section-heading > span {
		width: 34px;
		height: 34px;
		flex: 0 0 34px;
		display: grid;
		place-items: center;
		border-radius: var(--radius-full);
		background: var(--brand-dark);
		color: var(--lime);
		font-size: 14px;
		font-weight: var(--font-bold);
	}

	.section-heading p {
		margin-bottom: 2px;
		color: var(--primary);
		font-size: 12px;
		font-weight: var(--font-bold);
	}

	.section-heading h2 {
		color: var(--brand-black);
		font-size: 24px;
		font-weight: var(--font-bold);
	}

	.summary-grid {
		display: grid;
		grid-template-columns: minmax(360px, 0.72fr) minmax(0, 1.28fr);
		gap: var(--space-5);
		align-items: stretch;
	}

	.key-result-card,
	.audience-card-shell {
		padding: 24px 28px;
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
	}

	.key-result-card {
		display: flex;
		align-items: stretch;
	}

	.evidence-grid {
		display: grid;
		grid-template-columns: minmax(420px, 0.85fr) minmax(0, 1.15fr);
		gap: var(--space-5);
		align-items: stretch;
	}

	@container (max-width: 1050px) {
		.summary-grid,
		.evidence-grid {
			grid-template-columns: 1fr;
		}
	}

	@container (max-width: 520px) {
		.section-heading h2 {
			font-size: 20px;
		}

		.key-result-card,
		.audience-card-shell {
			padding: 20px;
		}
	}
</style>
