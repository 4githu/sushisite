<script lang="ts">
	import { grade, shortDate, type SessionSummary } from '$lib/odi/domain/sessionSummary';
	let {
		latest,
		count,
		delta,
		selected = false,
		onselect
	}: {
		latest: SessionSummary;
		count: number;
		delta: number | null;
		selected?: boolean;
		onselect: () => void;
	} = $props();
</script>

<button class="topic" class:selected onclick={onselect} aria-pressed={selected}
	><div><span class="chip">{latest.type}</span><span class="rounds">{count}회 연습 중</span></div>
	<h3>{latest.title}</h3>
	<footer>
		<small>최근 {shortDate(latest.date)}</small><strong>{latest.score ?? '—'}점</strong
		>{#if delta !== null}<span class="delta" class:negative={delta < 0}
				>{delta > 0 ? '+' : ''}{delta}점</span
			>{/if}
	</footer></button
>

<style>
	.topic {
		text-align: left;
		min-width: 240px;
		width: 100%;
		padding: 22px;
		border: 1px solid #dce0ea;
		border-radius: 12px;
		background: white;
		box-shadow:
			3px -5px 0 #fafbff,
			6px -9px 0 #f1f3f8,
			0 2px 10px #05063213;
	}
	.topic.selected {
		border-color: #03f;
		background: #f3f5ff;
	}
	.topic > div {
		display: flex;
		justify-content: space-between;
		gap: 8px;
	}
	.rounds {
		font-size: 12px;
		color: #03f;
	}
	h3 {
		height: 72px;
		margin: 18px 0 !important;
		line-height: 1.4;
	}
	footer {
		display: flex;
		gap: 8px;
		align-items: center;
	}
	small {
		color: #81889a;
		font-size: 12px;
		flex: 1;
	}
	strong {
		color: #03f;
	}
	.delta {
		background: #e2f6f0;
		color: #199c7d;
		border-radius: 20px;
		padding: 3px 7px;
		font-size: 12px;
	}
	.delta.negative {
		color: #c44555;
		background: #ffedf0;
	}
</style>
