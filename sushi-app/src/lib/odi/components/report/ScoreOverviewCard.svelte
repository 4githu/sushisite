<!-- src/lib/odi/components/report/ScoreOverviewCard.svelte -->

<script lang="ts">
	import ReportCard from "./ReportCard.svelte";
	import { clampScore, scoreCardLabel } from "./reportUtils";
	import type { ReportFeedback } from "./reportTypes";

	let {
		feedback
	}: {
		feedback: ReportFeedback;
	} = $props();

	const scores = $derived(feedback.score_card?.scores ?? {});
	const descriptions = $derived(feedback.score_card?.descriptions ?? {});
	const overall = $derived(feedback.score?.overall_score ?? 0);
	const percentile = $derived(feedback.score?.percentile ?? 0);

	const radarValues = $derived([
		clampScore(scores.engagement),
		clampScore(scores.clarity),
		clampScore(scores.credibility)
	]);

	const averageValues = [70, 74, 72];

	function point(index: number, value: number, radius = 92) {
		const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
		const scaled = radius * (value / 100);
		const x = 160 + Math.cos(angle) * scaled;
		const y = 125 + Math.sin(angle) * scaled;

		return `${x},${y}`;
	}

	function polygon(values: number[]) {
		return values.map((value, index) => point(index, value)).join(" ");
	}

	function axisPoint(index: number, radius = 105) {
		const angle = -Math.PI / 2 + index * ((Math.PI * 2) / 3);
		const x = 160 + Math.cos(angle) * radius;
		const y = 125 + Math.sin(angle) * radius;

		return `${x},${y}`;
	}
</script>

<ReportCard padding="22px 16px" minHeight="524px">
	<div class="score-card">
		<h2>나의 발표 점수</h2>

		<div class="score-main">
			<span class="percent-chip">발표자 중 상위 {percentile}%예요</span>

			<div class="score-number">
				<strong>{overall}</strong>
				<span>점</span>
			</div>
		</div>

		<div class="radar-wrap">
			<svg class="radar" viewBox="0 0 320 250" aria-label="발표 점수 레이더 그래프">
				<polygon class="grid" points={`${axisPoint(0, 105)} ${axisPoint(1, 105)} ${axisPoint(2, 105)}`} />
				<polygon class="grid" points={`${axisPoint(0, 78)} ${axisPoint(1, 78)} ${axisPoint(2, 78)}`} />
				<polygon class="grid" points={`${axisPoint(0, 52)} ${axisPoint(1, 52)} ${axisPoint(2, 52)}`} />
				<polygon class="grid" points={`${axisPoint(0, 26)} ${axisPoint(1, 26)} ${axisPoint(2, 26)}`} />

				<line class="axis" x1="160" y1="125" x2="160" y2="20" />
				<line class="axis" x1="160" y1="125" x2="70" y2="178" />
				<line class="axis" x1="160" y1="125" x2="250" y2="178" />

				<polygon class="average-polygon" points={polygon(averageValues)} />
				<polygon class="user-polygon" points={polygon(radarValues)} />
			</svg>

			<div class="radar-label top">몰입도 {scores.engagement ?? 0}</div>
			<div class="radar-label left">신뢰도 {scores.credibility ?? 0}</div>
			<div class="radar-label right">명확도 {scores.clarity ?? 0}</div>

			<div class="legend">
				<span><i class="dot user"></i>나의 발표</span>
				<span><i class="dot avg"></i>평균 발표</span>
			</div>
		</div>

		<div class="score-descriptions">
			{#each ["engagement", "credibility", "clarity"] as key}
				<div class="desc-row">
					<strong>{scoreCardLabel(key as "engagement" | "clarity" | "credibility")}</strong>
					<p>{descriptions[key as keyof typeof descriptions] ?? "분석 설명이 없습니다."}</p>
				</div>
			{/each}
		</div>
	</div>
</ReportCard>

<style>
	.score-card {
		position: relative;
		height: 480px;
		display: flex;
		flex-direction: column;
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.score-main {
		margin-top: var(--space-6);
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
		top: 88px;
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

	.score-descriptions {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.desc-row {
		min-height: 50px;
		padding: 11px 16px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
		border: 1px solid #caced9;
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.desc-row strong {
		color: var(--brand-black);
		font-size: 16px;
		font-weight: var(--font-bold);
		white-space: nowrap;
	}

	.desc-row p {
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
		text-align: right;
	}

	/* 리포트 3단 그리드와 브라우저 확대 시 카드 자체 폭이 좁아집니다.
	 * 이때는 절대 위치 레이더와 하단 설명을 분리해 서로 침범하지 않게 합니다. */
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

		.score-descriptions {
			margin-top: 8px;
		}

		.desc-row {
			min-height: 0;
			align-items: flex-start;
			flex-direction: column;
			gap: 4px;
		}

		.desc-row p {
			margin: 0;
			font-size: 14px;
			line-height: 1.45;
			text-align: left;
		}
	}
</style>
