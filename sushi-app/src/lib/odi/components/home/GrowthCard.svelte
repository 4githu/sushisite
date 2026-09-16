<script lang="ts">
	import type { SessionSummary } from '$lib/odi/domain/sessionSummary';
	import { summarizeHistory, shortDate } from '$lib/odi/domain/sessionSummary';
	let { rows }: { rows: SessionSummary[] } = $props();
	const summary = $derived(summarizeHistory(rows));
	const points = $derived(rows.slice(0, 5).toReversed());
	const axes = [
		{ id: 'engagement', label: '몰입도', color: '#03f' },
		{ id: 'credibility', label: '신뢰도', color: '#9dbf23' },
		{ id: 'clarity', label: '명확도', color: '#807dfe' }
	] as const;
	function path(key: 'engagement' | 'credibility' | 'clarity') {
		let active = false;
		return points
			.map((p, i) => {
				const n = p.evc[key];
				if (n === null) {
					active = false;
					return '';
				}
				const command = active ? 'L' : 'M';
				active = true;
				return `${command}${30 + (i * 450) / Math.max(1, points.length - 1)},${150 - Math.max(0, Math.min(100, n)) * 1.3}`;
			})
			.join(' ');
	}
	const strongest = $derived(
		[...axes]
			.map((a) => ({ ...a, score: rows[0]?.evc[a.id] ?? null }))
			.filter((a) => a.score !== null)
			.sort((a, b) => b.score! - a.score!)[0]
	);
</script>

<section class="surface">
	<div class="section-head">
		<h2>나의 성장</h2>
		<a href="/odi/report">상세 보기 ›</a>
	</div>
	<div class="overview">
		<div>
			<p class="muted">평균 세션 점수</p>
			<strong>{summary.average ?? '—'}</strong><span>/100</span>
		</div>
		<div class="strength">
			<span>가장 강한 영역</span>
			<h3>{strongest?.label ?? '분석 기록이 없어요'}</h3>
		</div>
	</div>
	<h3>최근 5회 세션 추이</h3>
	<div class="legend">
		{#each axes as axis, rowIndex0 (rowIndex0)}<span
				><i style:background={axis.color}></i>{axis.label}</span
			>{/each}
	</div>
	<svg viewBox="0 0 510 180" role="img" aria-label="최근 5회 몰입도 신뢰도 명확도 점수 추이"
		>{#each [0, 50, 100] as n, rowIndex1 (rowIndex1)}<line
				x1="30"
				x2="480"
				y1={150 - n * 1.3}
				y2={150 - n * 1.3}
				stroke="#e2e5ef"
			/><text x="0" y={154 - n * 1.3}>{n}</text
			>{/each}{#each axes as axis, rowIndex2 (rowIndex2)}<path
				d={path(axis.id)}
				fill="none"
				stroke={axis.color}
				stroke-width="2.5"
			/>{#each points as point, i (i)}{#if point.evc[axis.id] !== null}<circle
						cx={30 + (i * 450) / Math.max(1, points.length - 1)}
						cy={150 - (point.evc[axis.id] ?? 0) * 1.3}
						r="3"
						fill={axis.color}
					/>{/if}{/each}{/each}</svg
	>
	<div class="dates">
		{#each points as point, rowIndex3 (rowIndex3)}<span>{shortDate(point.date)}</span>{/each}
	</div>
</section>

<style>
	.overview {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 15px;
		margin: 8px 0 25px;
	}
	.overview p {
		font-size: 14px;
		margin: 0;
	}
	.overview strong {
		font-size: 58px;
		color: #051b78;
	}
	.strength {
		padding: 20px;
		box-shadow: 0 2px 9px #05063218;
		border-radius: 10px;
	}
	.strength span {
		font-size: 13px;
		color: #737b8d;
	}
	.legend {
		display: flex;
		justify-content: flex-end;
		gap: 18px;
		font-size: 12px;
		margin: 14px 0;
	}
	.legend span {
		display: flex;
		gap: 6px;
		align-items: center;
	}
	i {
		width: 7px;
		height: 7px;
		border-radius: 50%;
	}
	svg {
		width: 100%;
		height: auto;
	}
	text {
		font-size: 11px;
		fill: #8a92a4;
	}
	.dates {
		display: flex;
		justify-content: space-between;
		color: #747d90;
		font-size: 11px;
	}
</style>
