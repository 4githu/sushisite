<script lang="ts">
	import ReportCard from './ReportCard.svelte';
	import { goal, puplecheck, text_snippet } from '$lib/odi/icons';
	import type { ReportFeedback } from './reportTypes';

	let {
		feedback
	}: {
		feedback: ReportFeedback;
	} = $props();

	type MetricKey = 'engagement' | 'clarity' | 'credibility';

	const scores = $derived(feedback.score_card?.scores ?? {});
	const descriptions = $derived(feedback.score_card?.descriptions ?? {});
	const metrics: {
		key: MetricKey;
		label: string;
		icon: string;
		meaning: string;
		criteria: string;
	}[] = [
		{
			key: 'engagement',
			label: '몰입도',
			icon: goal,
			meaning: '청중이 발표 흐름에 관심을 유지하도록 이끈 정도예요.',
			criteria: '도입의 집중도, 말의 속도와 변화, 시선 유지, 핵심 구간의 반응을 함께 봐요.'
		},
		{
			key: 'clarity',
			label: '명확도',
			icon: text_snippet,
			meaning: '핵심 메시지와 설명 순서를 청중이 쉽게 이해한 정도예요.',
			criteria: '결론 우선 전달, 짧고 분명한 문장, 발음, 슬라이드와 말의 일치 여부를 봐요.'
		},
		{
			key: 'credibility',
			label: '신뢰도',
			icon: puplecheck,
			meaning: '주장에 근거가 있고 발표 태도가 믿음을 준 정도예요.',
			criteria: '자료와 사례의 근거, 안정적인 목소리와 시선, 질문에 직접 답했는지를 봐요.'
		}
	];
</script>

<ReportCard padding="24px" minHeight="0">
	<div class="metric-guide">
		<header>
			<div>
				<p class="eyebrow">지표를 읽는 법</p>
				<h2>세 가지 점수는 이렇게 평가해요</h2>
			</div>
			<p class="guide-copy">점수만 보지 말고, 이번 결과와 평가 기준을 함께 확인해 보세요.</p>
		</header>

		<div class="metric-grid">
			{#each metrics as metric}
				<article class="metric-item">
					<div class="metric-heading">
						<span class="metric-icon"><img src={metric.icon} alt="" aria-hidden="true" /></span>
						<div>
							<h3>{metric.label}</h3>
							<strong
								>{scores[metric.key] ?? '--'}{scores[metric.key] !== undefined ? '점' : ''}</strong
							>
						</div>
					</div>

					<p class="meaning">{metric.meaning}</p>
					<p class="criteria"><b>평가 기준</b>{metric.criteria}</p>

					{#if descriptions[metric.key]}
						<p class="result"><b>이번 결과</b>{descriptions[metric.key]}</p>
					{/if}
				</article>
			{/each}
		</div>
	</div>
</ReportCard>

<style>
	.metric-guide {
		container-type: inline-size;
		display: grid;
		gap: var(--space-6);
	}

	header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: var(--space-6);
	}

	.eyebrow {
		margin-bottom: 6px;
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-bold);
		letter-spacing: 0.08em;
	}

	h2 {
		color: var(--brand-black);
		font-size: 22px;
		font-weight: var(--font-bold);
	}

	.guide-copy {
		max-width: 480px;
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.5;
		text-align: right;
	}

	.metric-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--space-4);
	}

	.metric-item {
		min-width: 0;
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: 12px;
		background: var(--surface);
	}

	.metric-heading {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.metric-heading > div {
		min-width: 0;
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: var(--space-3);
		flex: 1;
	}

	.metric-icon {
		width: 42px;
		height: 42px;
		flex: 0 0 42px;
		display: grid;
		place-items: center;
		border-radius: 12px;
		background: var(--blue-light);
	}

	.metric-icon img {
		width: 24px;
		height: 24px;
		object-fit: contain;
	}

	h3 {
		color: var(--brand-black);
		font-size: 18px;
		font-weight: var(--font-bold);
	}

	.metric-heading strong {
		color: var(--primary);
		font-size: 20px;
		white-space: nowrap;
	}

	.meaning,
	.criteria,
	.result {
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.55;
		word-break: keep-all;
	}

	.criteria,
	.result {
		padding-top: var(--space-3);
		border-top: 1px solid var(--cool-grey-light-active);
	}

	.result {
		margin-top: auto;
		color: var(--text-primary);
	}

	.criteria b,
	.result b {
		display: block;
		margin-bottom: 4px;
		color: var(--brand-black);
		font-size: 13px;
	}

	@container (max-width: 860px) {
		header {
			align-items: flex-start;
			flex-direction: column;
			gap: var(--space-2);
		}

		.guide-copy {
			text-align: left;
		}

		.metric-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
