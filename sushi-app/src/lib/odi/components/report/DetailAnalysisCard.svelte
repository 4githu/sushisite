<!-- src/lib/odi/components/report/DetailAnalysisCard.svelte -->

<script lang="ts">
	import ReportCard from "./ReportCard.svelte";
	import MetricBadge from "./MetricBadge.svelte";
	import { contentMetricLabel, deliveryMetricLabel, scoreGrade, scoreGradeType } from "./reportUtils";
	import type { ReportFeedback } from "./reportTypes";

	let {
		feedback
	}: {
		feedback: ReportFeedback;
	} = $props();

	const detail = $derived(feedback.detail_analysis ?? {});
	const highlights = $derived(detail.highlight_metrics ?? []);
	const contentEntries = $derived(Object.entries(detail.content_analysis ?? {}));
	const deliveryEntries = $derived(Object.entries(detail.delivery_analysis ?? {}));
</script>

<ReportCard padding="22px 18px" minHeight="524px">
	<div class="detail-card">
		<h2>세부 요소 분석</h2>

		<div class="highlight-grid">
			{#each highlights as metric}
				<div class="highlight-card">
					<p>{metric.name}</p>
					<strong>{metric.score}</strong>
					<MetricBadge label={scoreGrade(metric.score)} type={scoreGradeType(metric.score)} size="lg" />
				</div>
			{/each}
		</div>

		<div class="analysis-columns">
			<section>
				<h3>내용 구성</h3>

				<div class="metric-list">
					{#each contentEntries as [key, value]}
						<div class="metric-row">
							<span>{contentMetricLabel(key)}</span>
							<MetricBadge label={scoreGrade(value)} type={scoreGradeType(value)} />
						</div>
					{/each}
				</div>
			</section>

			<section>
				<h3>전달 방식</h3>

				<div class="metric-list">
					{#each deliveryEntries as [key, value]}
						<div class="metric-row">
							<span>{deliveryMetricLabel(key)}</span>
							<MetricBadge label={scoreGrade(value)} type={scoreGradeType(value)} />
						</div>
					{/each}
				</div>
			</section>
		</div>
	</div>
</ReportCard>

<style>
	.detail-card {
		display: flex;
		flex-direction: column;
		gap: var(--space-8);
	}

	h2,
	h3 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.highlight-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--space-2);
	}

	.highlight-card {
		height: 144px;
		padding: 16px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
		border: 1px solid #caced9;
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.highlight-card p {
		color: var(--text-primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.highlight-card strong {
		color: var(--brand-black);
		font-size: 32px;
		font-weight: var(--font-bold);
		line-height: 140%;
	}

	.analysis-columns {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: var(--space-8);
	}

	.analysis-columns section {
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.metric-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.metric-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
		color: var(--text-primary);
		font-size: 17px;
		font-weight: var(--font-medium);
	}

	@container (max-width: 720px) {
		.highlight-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.analysis-columns {
			grid-template-columns: 1fr;
		}
	}

	@container (max-width: 420px) {
		.highlight-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
