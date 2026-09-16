<script lang="ts">
	import { onMount } from 'svelte';
	import { session, type OdiSession } from '$lib/odi/stores';
	import {
		completedSummaries,
		summarizeHistory,
		groupSessions,
		type SessionSummary
	} from '$lib/odi/domain/sessionSummary';
	import { formatKoreanDuration } from '$lib/odi/components/report/reportUtils';
	import SessionTopicCard from '$lib/odi/components/report/SessionTopicCard.svelte';
	import SessionHistoryTable from '$lib/odi/components/report/SessionHistoryTable.svelte';
	import Button from '$lib/odi/components/common/Button.svelte';
	let records = $state<OdiSession[]>([]),
		loading = $state(true),
		error = $state(''),
		tab = $state('topics'),
		selected = $state(''),
		query = $state(''),
		sort = $state('recent'),
		page = $derived.by(() => {
			tab;
			selected;
			query;
			sort;
			pages;
			return 1;
		}),
		deletingId = $state('');
	const rows = $derived(completedSummaries(records));
	const summary = $derived(summarizeHistory(rows));
	const topics = $derived(groupSessions(rows));
	const active = $derived(topics.find((t) => t.id === selected) ?? topics[0]);
	const filtered = $derived(
		(tab === 'topics' ? (active?.items ?? []) : rows)
			.filter((r) => r.title.toLowerCase().includes(query.toLowerCase()))
			.toSorted((a, b) =>
				tab === 'all' && sort === 'score'
					? (b.score ?? -1) - (a.score ?? -1) || b.date.localeCompare(a.date)
					: b.date.localeCompare(a.date)
			)
	);
	const pages = $derived(Math.max(1, Math.ceil(filtered.length / 5)));
	async function load() {
		loading = true;
		error = '';
		try {
			records = await session.listAllSessions();
		} catch (e) {
			error = e instanceof Error ? e.message : '기록을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}
	async function remove(row: SessionSummary) {
		if (!confirm(`“${row.title}” 리포트를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;
		deletingId = row.id;
		try {
			await session.deleteSession(row.id);
			records = records.filter((r) => r.session_id !== row.id);
		} catch (e) {
			error = e instanceof Error ? e.message : '삭제 실패';
		} finally {
			deletingId = '';
		}
	}
	onMount(load);
</script>

<svelte:head><title>세션 리포트 | Re:hear</title></svelte:head>
<main class="odi-workspace">
	<header>
		<p class="eyebrow">Report</p>
		<h1>세션 리포트</h1>
	</header>
	<div class="stat-grid">
		<article class="stat">
			<div>
				나의 평균 점수
				<p>최고 점수 {summary.best ?? '—'}점</p>
			</div>
			<strong>{summary.average ?? '—'}<small>점</small></strong>
		</article>
		<article class="stat">
			<div>
				총 연습 시간
				<p>완료한 발표·면접 세션</p>
			</div>
			<strong class="time">{formatKoreanDuration(summary.seconds)}</strong>
		</article>
	</div>
	<div class="tabs report-tabs">
		<button class:active={tab === 'topics'} onclick={() => (tab = 'topics')}>세션 주제</button
		><button class:active={tab === 'all'} onclick={() => (tab = 'all')}>전체 기록</button>
	</div>
	{#if error}<p class="error" role="alert">{error}</p>
		<Button onclick={load}>다시 시도</Button>{/if}
	{#if loading}<p class="state">리포트를 불러오는 중…</p>{:else if !rows.length}<div class="state">
			<h2>아직 완료한 세션이 없어요</h2>
			<p>첫 발표를 완료하면 리포트를 확인할 수 있어요.</p>
			<Button href="/odi">홈으로</Button>
		</div>{:else}{#if tab === 'topics'}<div class="topics">
				{#each topics as topic (topic.id)}<SessionTopicCard
						latest={topic.latest}
						count={topic.items.length}
						delta={topic.delta}
						selected={active?.id === topic.id}
						onselect={() => (selected = topic.id)}
					/>{/each}
			</div>
			{#if active}<h2>{active.latest.title}</h2>
				<p class="muted">{active.latest.details} · 청중 {active.latest.audience}인</p>{/if}{/if}
		<div class="toolbar">
			<span class="muted">총 {filtered.length}개 기록</span>
			<div class="actions">
				<input
					bind:value={query}
					aria-label="세션 이름 검색"
					placeholder="세션 이름 검색"
				/>{#if tab === 'all'}<select bind:value={sort} aria-label="정렬"
						><option value="recent">최신순</option><option value="score">점수 높은 순</option
						></select
					>{/if}
			</div>
		</div>
		{#if filtered.length}<SessionHistoryTable
				rows={filtered.slice((page - 1) * 5, page * 5)}
				ondelete={remove}
				{deletingId}
				rounds={tab === 'topics'}
				roundNumbers={Object.fromEntries(
					(active?.items ?? []).map((r, i) => [r.id, (active?.items.length ?? 0) - i])
				)}
				total={filtered.length}
				offset={(page - 1) * 5}
			/>{:else}<p class="state">검색 결과가 없어요.</p>{/if}
		<nav class="pagination" aria-label="페이지 이동">
			{#each Array(pages) as _, i (i)}<button
					class:active={page === i + 1}
					onclick={() => (page = i + 1)}>{i + 1}</button
				>{/each}
		</nav>{/if}
</main>

<style>
	.report-tabs {
		margin: 28px 0 !important;
	}
	.report-tabs button {
		width: 50%;
	}
	.topics {
		display: flex;
		gap: 20px;
		overflow-x: auto;
		padding: 12px 4px 22px;
		margin-bottom: 24px;
	}
	.topics :global(.topic) {
		flex: 0 0 calc((100% - 60px) / 4);
	}
	.stat small {
		font-size: 14px;
	}
	.stat .time {
		color: #e8ebff;
		font-size: clamp(24px, 3vw, 42px);
	}
</style>
