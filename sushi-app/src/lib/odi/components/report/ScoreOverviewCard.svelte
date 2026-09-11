<!-- src/lib/odi/components/report/ScoreOverviewCard.svelte -->

<script lang="ts">
	import ReportCard from './ReportCard.svelte';
	import { clampScore } from './reportUtils';
	import type { ReportComparison, ReportFeedback } from './reportTypes';

	let {
		feedback,
		comparison,
		variant = 'default'
	}: {
		feedback: ReportFeedback;
		comparison?: ReportComparison;
		variant?: 'default' | 'v3';
	} = $props();

	const scores = $derived(feedback.score_card?.scores ?? {});
	const overall = $derived(feedback.score?.overall_score ?? null);
	const percentile = $derived(feedback.score?.percentile ?? null);
	const averageScores = $derived(
		comparison?.account_average ?? feedback.score_card?.average_scores
	);
	const hasUserScores = $derived(
		[scores.engagement, scores.clarity, scores.credibility].some((value) => Number.isFinite(value))
	);
	const hasAverageScores = $derived(
		Boolean(averageScores) &&
			[averageScores?.engagement, averageScores?.clarity, averageScores?.credibility].every(
				(value) => Number.isFinite(value)
			)
	);

	const radarValues = $derived([
		clampScore(scores.engagement),
		clampScore(scores.clarity),
		clampScore(scores.credibility)
	]);

	const averageValues = $derived([
		clampScore(averageScores?.engagement),
		clampScore(averageScores?.clarity),
		clampScore(averageScores?.credibility)
	]);

	function point(index: number, value: number, radius = 92) {
		const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
		const scaled = radius * (value / 100);
		const x = 160 + Math.cos(angle) * scaled;
		const y = 125 + Math.sin(angle) * scaled;

		return `${x},${y}`;
	}

	function polygon(values: number[]) {
		return values.map((value, index) => point(index, value)).join(' ');
	}

	function axisPoint(index: number, radius = 105) {
		const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
		const x = 160 + Math.cos(angle) * radius;
		const y = 125 + Math.sin(angle) * radius;

		return `${x},${y}`;
	}
</script>

<ReportCard padding="24px" minHeight="380px">
	<div class:v3={variant === 'v3'} class="score-card">
		<h2>나의 발표 점수</h2>

		<div class="score-main">
			{#if percentile !== null}
				<span class="percent-chip">발표자 중 상위 {percentile}%예요</span>
			{:else}
				<span class="percent-chip neutral">비교 데이터 준비 중</span>
			{/if}

			<div class="score-number">
				<strong>{Number.isFinite(overall) ? overall : '--'}</strong>
				{#if Number.isFinite(overall)}<span>점</span>{/if}
			</div>
		</div>

		<div class="radar-wrap">
			<svg class="radar" viewBox="0 0 320 250" aria-label="발표 점수 레이더 그래프">
				<polygon
					class="grid"
					points={`${axisPoint(0, 105)} ${axisPoint(1, 105)} ${axisPoint(2, 105)}`}
				/>
				<polygon
					class="grid"
					points={`${axisPoint(0, 78)} ${axisPoint(1, 78)} ${axisPoint(2, 78)}`}
				/>
				<polygon
					class="grid"
					points={`${axisPoint(0, 52)} ${axisPoint(1, 52)} ${axisPoint(2, 52)}`}
				/>
				<polygon
					class="grid"
					points={`${axisPoint(0, 26)} ${axisPoint(1, 26)} ${axisPoint(2, 26)}`}
				/>

				<line class="axis" x1="160" y1="125" x2="160" y2="20" />
				<line class="axis" x1="160" y1="125" x2="70" y2="178" />
				<line class="axis" x1="160" y1="125" x2="250" y2="178" />

				{#if hasAverageScores}
					<polygon class="average-polygon" points={polygon(averageValues)} />
				{/if}
				{#if hasUserScores}<polygon class="user-polygon" points={polygon(radarValues)} />{/if}
			</svg>

			<div class="radar-label top">몰입도 {scores.engagement ?? '--'}</div>
			<div class="radar-label left">신뢰도 {scores.credibility ?? '--'}</div>
			<div class="radar-label right">명확도 {scores.clarity ?? '--'}</div>

			<div class="legend">
				{#if hasUserScores}<span><i class="dot user"></i>나의 발표</span>{/if}
				{#if hasAverageScores}<span><i class="dot avg"></i>평균 발표</span>{/if}
			</div>
		</div>
	</div>
</ReportCard>

<style>
	.score-card {
		position: relative;
		height: 332px;
		display: flex;
		flex-direction: column;
	}

	.score-card.v3 {
		height: 780px;
	}

	.score-card.v3 h2 {
		font-size: 40px;
	}

	.score-card.v3 .score-main {
		margin-top: 30px;
	}

	.score-card.v3 .score-number strong {
		font-size: 128px;
	}

	.score-card.v3 .radar-wrap {
		left: 61%;
		top: 42px;
		width: min(900px, 58vw);
		height: 660px;
	}

	.score-card.v3 .radar {
		width: 100%;
		height: 634px;
	}

	.score-card.v3 .radar-label {
		font-size: 28px;
	}

	.score-card.v3 .radar-label.top {
		left: 50%;
		transform: translateX(-50%);
	}

	.score-card.v3 .radar-label.left {
		left: 0;
	}

	.score-card.v3 .radar-label.right {
		right: 0;
	}

	.score-card.v3 .legend {
		left: -52%;
		right: auto;
		top: 390px;
		font-size: 18px;
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.score-main {
		margin-top: var(--space-4);
		display: flex;
		flex-direction: column;
		align-items: flex-start;
	}

	.percent-chip {
		padding: 8px;
		border-radius: var(--radius-sm);
		background: rgba(0, 51, 255, 0.05);
		color: var(--primary);
		font-size: 13px;
		font-weight: var(--font-medium);
	}
	.score-card.v3 .percent-chip {
		padding: 8px;
		font-size: 24px;
	}
	.score-card.v3 .score-number span {
		padding-bottom: 12px;
		font-size: 40px;
	}

	.percent-chip.neutral {
		background: var(--cool-grey-light);
		color: var(--text-secondary);
	}

	.score-number {
		display: flex;
		align-items: flex-end;
		gap: var(--space-1);
		color: var(--primary);
	}

	.score-number strong {
		font-size: 42px;
		font-weight: var(--font-bold);
		line-height: 1;
	}

	.score-number span {
		font-size: 24px;
		font-weight: var(--font-medium);
	}

	.radar-wrap {
		position: absolute;
		left: 50%;
		top: 76px;
		width: 320px;
		height: 230px;
		transform: translateX(-50%);
	}

	.radar {
		width: 320px;
		height: 250px;
	}

	.grid,
	.axis {
		fill: none;
		stroke: #caced9;
		stroke-width: 1;
	}

	.average-polygon {
		fill: rgba(207, 255, 94, 0.22);
		stroke: #9fe300;
		stroke-width: 1.2;
	}

	.user-polygon {
		fill: rgba(0, 51, 255, 0.3);
		stroke: var(--primary);
		stroke-width: 1.5;
	}

	.radar-label {
		position: absolute;
		color: var(--brand-black);
		font-size: 14px;
		font-weight: var(--font-medium);
	}

	.radar-label.top {
		left: 135px;
		top: 0;
	}

	.radar-label.left {
		left: 0;
		bottom: 8px;
	}

	.radar-label.right {
		right: 0;
		bottom: 8px;
	}

	.legend {
		position: absolute;
		right: 0;
		top: 32px;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: var(--font-medium);
	}

	.legend span {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.dot {
		width: 8px;
		height: 8px;
		border-radius: var(--radius-full);
	}

	.dot.user {
		background: var(--primary);
	}

	.dot.avg {
		background: var(--lime);
	}

	/* 카드 폭이 좁아지면 절대 위치 레이더를 문서 흐름으로 되돌립니다. */
	@container (max-width: 540px) {
		.score-card {
			height: auto;
			min-height: 0;
		}

		.radar-wrap {
			position: relative;
			left: auto;
			top: auto;
			width: min(320px, 100%);
			height: 230px;
			margin: 10px auto 0;
			transform: none;
		}

		.radar {
			width: 100%;
			height: 250px;
		}

		.score-card.v3 {
			height: auto;
		}

		.score-card.v3 .radar-wrap {
			left: auto;
			top: auto;
			width: 100%;
			height: 280px;
		}

		.score-card.v3 .radar {
			height: 280px;
		}

		.score-card.v3 .legend {
			right: 0;
			top: 38px;
		}
	}
</style>
