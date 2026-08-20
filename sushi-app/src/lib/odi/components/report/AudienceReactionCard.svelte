<!-- src/lib/odi/components/report/AudienceReactionCard.svelte -->

<script lang="ts">
	import type { AudienceGraphPoint, ReportFeedback } from "./reportTypes";
	import { Exclude, sentiment_satisfied, sms } from "$lib/odi/icons";

	let {
		feedback
	}: {
		feedback: ReportFeedback;
	} = $props();

	const graph = $derived(feedback.audience_analysis?.graph ?? []);
	const maxTime = $derived(Math.max(...graph.map((point) => point.time_sec), 1));
	const xTicks = $derived([0, maxTime / 3, (maxTime * 2) / 3, maxTime]);

	function formatTime(seconds: number) {
		const rounded = Math.max(0, Math.round(seconds));
		return `${String(Math.floor(rounded / 60)).padStart(2, "0")}:${String(rounded % 60).padStart(2, "0")}`;
	}

	function pathFor(points: AudienceGraphPoint[], key: "E" | "V" | "C") {
		if (points.length === 0) return "";

		const width = 430;
		const height = 150;

		return points
			.map((point, index) => {
				const x = (point.time_sec / maxTime) * width;
				const y = height - point[key] * height;
				const command = index === 0 ? "M" : "L";

				return `${command} ${x.toFixed(2)} ${y.toFixed(2)}`;
			})
			.join(" ");
	}

	const summaryCards = $derived([
		{
			type: "eye",
			icon: Exclude,
			title: "시선이 집중되는 발표였어요",
			description: "핵심 구간에서 정면 응시가 길게 유지되었어요"
		},
		{
			type: "question",
			icon: sms,
			title: "질문이 생기는 흥미로운 흐름이었어요",
			description: "결론에서 질문 의도가 가장 많이 나타났어요"
		},
		{
			type: "positive",
			icon: sentiment_satisfied,
			title: "공감으로 고개가 절로 끄덕여져요",
			description: "연구와 사례가 연결될 때 긍정이 증가했어요"
		}
	]);
</script>

<div class="audience-shell">
	<div class="audience-card">
		<section class="chart-area">
			<div class="chart-header">
				<h2>청중 반응 분석</h2>

				<div class="legend">
					<span><i class="dot e"></i>시선 응시</span>
					<span><i class="dot v"></i>질문 생성</span>
					<span><i class="dot c"></i>긍정 반응</span>
				</div>
			</div>

			<div class="chart-wrap">
				<div class="y-labels">
					<span>100</span>
					<span>50</span>
					<span>0</span>
				</div>

				<svg viewBox="0 0 430 170" class="line-chart" aria-label="청중 반응 그래프">
					<line class="grid" x1="0" y1="10" x2="430" y2="10" />
					<line class="grid" x1="0" y1="85" x2="430" y2="85" />
					<line class="grid" x1="0" y1="160" x2="430" y2="160" />

					<path class="line e" d={pathFor(graph, "E")} />
					<path class="line v" d={pathFor(graph, "V")} />
					<path class="line c" d={pathFor(graph, "C")} />
				</svg>

				<div class="x-labels">
					{#each xTicks as tick}
						<span>{formatTime(tick)}</span>
					{/each}
				</div>
			</div>
		</section>

		<section class="summary-list">
			{#each summaryCards as card}
				<article class="summary-card">
					<div class={`summary-icon ${card.type}`}>
						<img src={card.icon} alt="" aria-hidden="true" />
					</div>

					<div>
						<strong>{card.title}</strong>
						<p>{card.description}</p>
					</div>
				</article>
			{/each}
		</section>
	</div>
</div>

<style>
	.audience-shell {
		container-type: inline-size;
		min-width: 0;
	}

	.audience-card {
		display: grid;
		grid-template-columns: minmax(320px, 1.25fr) minmax(220px, 0.75fr);
		gap: var(--space-6);
		align-items: center;
	}

	.chart-area {
		display: flex;
		flex-direction: column;
		gap: var(--space-6);
	}

	.chart-header {
		display: flex;
		align-items: center;
		gap: var(--space-8);
	}

	h2 {
		color: var(--brand-black);
		font-size: 20px;
		font-weight: var(--font-bold);
	}

	.legend {
		display: flex;
		align-items: center;
		gap: var(--space-4);
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

	.dot.e {
		background: var(--primary);
	}

	.dot.v {
		background: var(--purple-dark);
	}

	.dot.c {
		background: var(--lime);
	}

	.chart-wrap {
		position: relative;
		display: grid;
		grid-template-columns: 32px 1fr;
		gap: var(--space-3);
	}

	.y-labels {
		height: 170px;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		align-items: flex-end;
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: var(--font-medium);
	}

	.line-chart {
		width: 100%;
		height: 170px;
		overflow: visible;
	}

	.grid {
		stroke: #e4e7ef;
		stroke-width: 1;
		stroke-dasharray: 4 4;
	}

	.line {
		fill: none;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.line.e {
		stroke: var(--primary);
	}

	.line.v {
		stroke: var(--purple-dark);
	}

	.line.c {
		stroke: var(--lime);
	}

	.x-labels {
		grid-column: 2;
		display: flex;
		justify-content: space-between;
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: var(--font-medium);
	}

	.summary-list {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
	}

	.summary-card {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.summary-card > div:last-child {
		min-width: 0;
	}

	.summary-icon {
		width: 42px;
		height: 42px;
		border-radius: var(--radius-full);
		flex-shrink: 0;
		display: grid;
		place-items: center;
	}

	.summary-icon img {
		width: 24px;
		height: 24px;
		object-fit: contain;
	}

	.summary-icon.eye img {
		width: 26px;
		height: 18px;
	}

	.summary-icon.eye {
		background: rgba(0, 51, 255, 0.15);
	}

	.summary-icon.question {
		background: rgba(128, 125, 254, 0.15);
	}

	.summary-icon.positive {
		background: rgba(159, 227, 0, 0.15);
	}

	.summary-card strong {
		color: var(--brand-black);
		font-size: 15px;
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.summary-card p {
		margin-top: 4px;
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
		line-height: 135%;
	}

	/* 이 카드는 큰 화면 안에서도 좁은 열에 놓일 수 있으므로 viewport가 아닌 카드 폭을 봅니다. */
	@container (max-width: 580px) {
		.audience-card {
			grid-template-columns: 1fr;
		}
	}

	@container (max-width: 600px) {
		.chart-header,
		.legend {
			flex-wrap: wrap;
		}

		.summary-card strong {
			font-size: 14px;
		}
	}
</style>
