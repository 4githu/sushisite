<script lang="ts">
	import type { SessionSummary } from '$lib/odi/domain/sessionSummary';
	import { grade, shortDate } from '$lib/odi/domain/sessionSummary';
	import Button from '../common/Button.svelte';
	import { formatKoreanDuration } from '../report/reportUtils';
	import preview from '$lib/odi/assets/home-202609/recent.png';
	let {
		rows,
		onrepeat,
		busy = false
	}: { rows: SessionSummary[]; onrepeat: (row: SessionSummary) => void; busy?: boolean } = $props();
	const recent = $derived(rows[0]);
</script>

<section class="surface">
	<div class="section-head">
		<h2>가장 최근 연습</h2>
		<a href="/odi/report">전체 보기 ›</a>
	</div>
	{#if recent}<div class="featured">
			<img src={preview} alt="가상 발표 환경" />
			<div>
				<span class="chip">가장 최근 연습</span>
				<h3>{recent.title}</h3>
				<p class="muted">
					{shortDate(recent.date)} · {recent.audience}인 · {formatKoreanDuration(recent.seconds)}
				</p>
				<strong class="score">{recent.score ?? '—'}</strong><span>
					/100 · {grade(recent.score)}</span
				>
				<div class="actions">
					<Button size="sm" href={`/odi/report/${recent.id}`}>리포트 이어보기 →</Button><Button
						size="sm"
						variant="outline"
						disabled={busy}
						onclick={() => onrepeat(recent)}>다시 연습하기</Button
					>
				</div>
			</div>
		</div>
		{#each rows.slice(1, 3) as row, rowIndex0 (rowIndex0)}<a
				class="recent-row"
				href={`/odi/report/${row.id}`}
				><img src={preview} alt="" />
				<div>
					<strong>{row.title}</strong><small
						>{shortDate(row.date)} · {formatKoreanDuration(row.seconds)}</small
					>
				</div>
				<b>{row.score ?? '—'}</b><span>›</span></a
			>{/each}{/if}
</section>

<style>
	.featured {
		display: grid;
		grid-template-columns: 32% 1fr;
		gap: 16px;
		margin: 4px 0 16px;
	}
	.featured > img {
		width: 100%;
		height: 100%;
		max-height: 210px;
		object-fit: cover;
		border-radius: 12px;
	}
	h3 {
		margin: 8px 0 !important;
	}
	p {
		font-size: 13px;
	}
	.actions {
		margin-top: 12px;
	}
	.recent-row {
		display: flex;
		gap: 14px;
		align-items: center;
		border: 1px solid #e2e5ef;
		border-radius: 8px;
		padding: 10px;
		margin-top: 8px;
		color: inherit !important;
	}
	.recent-row img {
		width: 62px;
		height: 43px;
		object-fit: cover;
		border-radius: 6px;
	}
	.recent-row div {
		flex: 1;
	}
	.recent-row small {
		display: block;
		color: #747d90;
		margin-top: 4px;
	}
	.recent-row b {
		font-size: 26px;
		color: #03f;
	}
	.recent-row strong {
		font-size: 14px;
	}
	@media (max-width: 800px) {
		.featured {
			grid-template-columns: 1fr;
		}
		.featured > img {
			height: 130px;
		}
		.recent-row img {
			display: none;
		}
	}
</style>
