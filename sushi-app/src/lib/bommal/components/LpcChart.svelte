<script lang="ts">
	import type { GraphPoint } from '$lib/bommal/types';

	let {
		user = [],
		target = []
	}: {
		user?: GraphPoint[];
		target?: GraphPoint[];
	} = $props();

	const width = 680;
	const height = 260;
	const padding = { left: 48, right: 18, top: 24, bottom: 34 };

	function pointFrequency(point: GraphPoint) {
		return point.frequency_hz ?? point.frequencyHz ?? 0;
	}

	function pointMagnitude(point: GraphPoint) {
		return point.magnitude_db ?? point.magnitudeDb ?? 0;
	}

	const allMagnitudes = $derived([...user, ...target].map(pointMagnitude));
	const minMagnitude = $derived(Math.min(-40, ...allMagnitudes));
	const maxMagnitude = $derived(Math.max(4, ...allMagnitudes));

	function x(frequency: number) {
		const plotWidth = width - padding.left - padding.right;
		return padding.left + (Math.min(5000, Math.max(0, frequency)) / 5000) * plotWidth;
	}

	function y(magnitude: number) {
		const plotHeight = height - padding.top - padding.bottom;
		const range = Math.max(1, maxMagnitude - minMagnitude);
		return padding.top + ((maxMagnitude - magnitude) / range) * plotHeight;
	}

	function path(points: GraphPoint[]) {
		if (!points.length) return '';
		return points
			.map((point, index) => {
				const command = index === 0 ? 'M' : 'L';
				return `${command} ${x(pointFrequency(point)).toFixed(2)} ${y(pointMagnitude(point)).toFixed(2)}`;
			})
			.join(' ');
	}

	const targetPath = $derived(path(target));
	const userPath = $derived(path(user));
	const hasData = $derived(user.length > 0 && target.length > 0);
</script>

<div class="chart-card">
	<div class="chart-header">
		<div>
			<p>LPC Envelope</p>
			<h3>기준 곡선과 사용자 곡선 비교</h3>
		</div>
		<div class="legend">
			<span><i class="target"></i>정답</span>
			<span><i class="user"></i>사용자</span>
		</div>
	</div>

	{#if hasData}
		<svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="LPC envelope comparison">
			<line class="axis" x1={padding.left} y1={height - padding.bottom} x2={width - padding.right} y2={height - padding.bottom} />
			<line class="axis" x1={padding.left} y1={padding.top} x2={padding.left} y2={height - padding.bottom} />
			{#each [1000, 2000, 3000, 4000, 5000] as tick}
				<line class="grid" x1={x(tick)} y1={padding.top} x2={x(tick)} y2={height - padding.bottom} />
				<text x={x(tick)} y={height - 10}>{tick / 1000}k</text>
			{/each}
			<path class="target-line" d={targetPath} />
			<path class="user-line" d={userPath} />
		</svg>
	{:else}
		<div class="empty">word 평가 JSON을 실행하면 LPC 곡선이 여기에 표시됩니다.</div>
	{/if}
</div>

<style>
	.chart-card {
		display: grid;
		gap: 18px;
		border: 1px solid rgba(7, 1, 0, 0.08);
		border-radius: 20px;
		background: #ffffff;
		padding: 22px;
		box-shadow: 0 18px 54px rgba(7, 1, 0, 0.08);
	}

	.chart-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
	}

	p {
		margin: 0 0 4px;
		color: #4088ee;
		font-size: 13px;
		font-weight: 700;
	}

	h3 {
		margin: 0;
		color: #070100;
		font-size: 20px;
		font-weight: 700;
		letter-spacing: 0;
	}

	.legend {
		display: flex;
		gap: 12px;
		color: rgba(7, 1, 0, 0.58);
		font-size: 13px;
		font-weight: 600;
	}

	.legend span {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	i {
		display: block;
		width: 18px;
		height: 4px;
		border-radius: 999px;
	}

	i.target {
		background: #4088ee;
	}

	i.user {
		background: #daff1c;
	}

	svg {
		width: 100%;
		height: auto;
		border-radius: 14px;
		background: #f8faf4;
	}

	text {
		fill: rgba(7, 1, 0, 0.46);
		font-size: 12px;
		text-anchor: middle;
	}

	.axis {
		stroke: rgba(7, 1, 0, 0.18);
	}

	.grid {
		stroke: rgba(7, 1, 0, 0.08);
	}

	path {
		fill: none;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.target-line {
		stroke: #4088ee;
		stroke-width: 3.2;
	}

	.user-line {
		stroke: #a2da0a;
		stroke-width: 3;
	}

	.empty {
		display: grid;
		min-height: 260px;
		place-items: center;
		border-radius: 14px;
		background: #f8faf4;
		color: rgba(7, 1, 0, 0.48);
		font-size: 15px;
	}
</style>
