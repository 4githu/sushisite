<script lang="ts">
	import { grade, shortDate, type SessionSummary } from '$lib/odi/domain/sessionSummary';
	import { formatKoreanDuration } from './reportUtils';
	import Button from '../common/Button.svelte';
	let {
		rows,
		ondelete,
		deletingId = '',
		rounds = false,
		total = 0,
		offset = 0,
		roundNumbers = {}
	}: {
		rows: SessionSummary[];
		ondelete: (row: SessionSummary) => void;
		deletingId?: string;
		rounds?: boolean;
		total?: number;
		offset?: number;
		roundNumbers?: Record<string, number>;
	} = $props();
</script>

<div class="table-scroll">
	<table>
		<thead
			><tr
				><th>{rounds ? '회차' : '세션 정보'}</th><th>소요 시간</th><th>점수</th><th>피드백 요약</th
				><th>날짜</th><th><span class="sr-only">동작</span></th></tr
			></thead
		><tbody
			>{#each rows as row, i (row.id)}<tr
					><td
						>{#if rounds}<span class="chip">{roundNumbers[row.id] ?? total - offset - i}회차</span
							>{:else}<span class="chip">{row.type}</span><strong>{row.title}</strong><small
								>{row.details} · 청중 {row.audience}인</small
							>{/if}</td
					><td>{formatKoreanDuration(row.seconds)}</td><td
						><b>{row.score ?? '—'}</b><small>{grade(row.score)}</small></td
					><td class="feedback">{row.summary}</td><td>{shortDate(row.date)}</td><td
						><div class="actions">
							<Button size="sm" href={`/odi/report/${row.id}`}>자세히 보기</Button><button
								class="delete"
								disabled={deletingId === row.id}
								onclick={() => ondelete(row)}
								aria-label={`${row.title} 리포트 삭제`}>×</button
							>
						</div></td
					></tr
				>{/each}</tbody
		>
	</table>
</div>

<style>
	.table-scroll {
		position: relative;
		overflow-x: auto;
		max-width: 100%;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		min-width: 740px;
		text-align: left;
		font-size: 14px;
	}
	th {
		font-weight: 500;
		color: #7c8497;
		padding: 14px 10px;
		border-bottom: 2px solid #dce0ea;
	}
	td {
		border-bottom: 1px solid #dce0ea;
		padding: 22px 10px;
	}
	td:first-child {
		min-width: 180px;
		max-width: 280px;
	}
	strong {
		display: block;
		margin: 8px 0;
	}
	small {
		display: block;
		color: #7c8497;
		font-size: 12px;
		margin-top: 6px;
	}
	.feedback {
		max-width: 300px;
		color: #697287;
		font-size: 13px;
	}
	.delete {
		background: none;
		border: 0;
		color: #747c91;
		font-size: 22px;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
	}
</style>
