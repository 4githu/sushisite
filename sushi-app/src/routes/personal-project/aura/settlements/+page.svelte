<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { SchoolSettlement } from '$lib/personal-project/shared/types';

	const now = new Date();
	let year = $state(now.getFullYear());
	let month = $state(now.getMonth() + 1);
	let data = $state<SchoolSettlement | null>(null);
	let loading = $state(true);
	let error = $state('');

	async function load() {
		loading = true;
		try {
			data = await personalApi.settlements(year, month);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '정산을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	function moveMonth(step: number) {
		const date = new Date(year, month - 1 + step, 1);
		year = date.getFullYear();
		month = date.getMonth() + 1;
		load();
	}

	async function download() {
		const response = await fetch(personalApi.settlementExportUrl(year, month), {
			credentials: 'include'
		});
		if (!response.ok) {
			error = '엑셀 파일을 만들지 못했습니다.';
			return;
		}
		const url = URL.createObjectURL(await response.blob());
		const anchor = document.createElement('a');
		anchor.href = url;
		anchor.download = `aura-${year}-${String(month).padStart(2, '0')}.xlsx`;
		anchor.click();
		URL.revokeObjectURL(url);
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Monthly settlement</p>
		<h1>학교별 월 정산</h1>
		<p>완료된 학교 회차를 기준으로 시급과 진행 시간의 스냅샷을 합산합니다.</p>
	</div>
	<button class="ghost-button" onclick={download}>↓ 엑셀 내보내기</button>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}

<div class="settlement-top">
	<div class="month-picker">
		<button onclick={() => moveMonth(-1)}>‹</button><strong>{year}년 {month}월</strong><button
			onclick={() => moveMonth(1)}>›</button
		>
	</div>
	<div class="summary card">
		<span>완료 {data?.completedCount ?? 0}회</span><strong
			>{(data?.totalAmount ?? 0).toLocaleString()}원</strong
		>
	</div>
</div>

<section class="card table" aria-busy={loading}>
	<div class="table-head">
		<span>일시</span><span>학교</span><span>회차</span><span>학생</span><span>지급</span><span
			>금액</span
		>
	</div>
	{#each data?.items ?? [] as item (item.id)}
		<a href={`/personal-project/aura/schools/${item.schoolId}`} class="table-row">
			<time>{new Date(item.startTime).toLocaleString('ko-KR')}</time>
			<strong>{item.schoolName}</strong>
			<span>{item.roundLabel}</span>
			<span>{item.targets.length}명</span>
			<span class={`status-pill ${item.paymentStatus}`}
				>{item.paymentStatus === 'paid' ? '지급 완료' : '미지급'}</span
			>
			<b>{item.amount.toLocaleString()}원</b>
		</a>
	{:else}
		<div class="empty">{loading ? '불러오는 중…' : '완료된 회차가 없습니다.'}</div>
	{/each}
</section>

<style>
	.settlement-top {
		margin-bottom: 18px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 18px;
	}
	.month-picker {
		display: flex;
		align-items: center;
		gap: 13px;
	}
	.month-picker button {
		width: 34px;
		height: 34px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: white;
		cursor: pointer;
	}
	.month-picker strong {
		min-width: 105px;
		font:
			500 16px Georgia,
			'Noto Sans KR',
			serif;
		text-align: center;
	}
	.summary {
		padding: 14px 19px;
		display: flex;
		gap: 20px;
		align-items: center;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.summary strong {
		color: var(--pp-sage-dark);
		font:
			500 18px Georgia,
			serif;
	}
	.table {
		overflow: hidden;
	}
	.table-head,
	.table-row {
		padding: 14px 21px;
		display: grid;
		grid-template-columns: 1.3fr 1.2fr 0.6fr 0.6fr 0.8fr 0.8fr;
		align-items: center;
		gap: 13px;
	}
	.table-head {
		background: #efede7;
		color: var(--pp-muted);
		font-size: 9px;
		font-weight: 700;
	}
	.table-row {
		border-top: 1px solid var(--pp-line);
		color: inherit;
		font-size: 10px;
		text-decoration: none;
	}
	.table-row time {
		color: var(--pp-muted);
		font-size: 9px;
	}
	.table-row > b {
		color: var(--pp-sage-dark);
		text-align: right;
	}
	.empty {
		padding: 65px;
		color: var(--pp-muted);
		font-size: 11px;
		text-align: center;
	}
	@media (max-width: 720px) {
		.settlement-top {
			align-items: stretch;
			flex-direction: column;
		}
		.table-head {
			display: none;
		}
		.table-row {
			grid-template-columns: 1fr auto;
		}
		.table-row > *:nth-child(1),
		.table-row > *:nth-child(3),
		.table-row > *:nth-child(4),
		.table-row > *:nth-child(5) {
			display: none;
		}
	}
</style>
