<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { request } from '../shared/api';
	let { term, code, section }: { term: string; code: string; section: string } = $props();
	type Point = {
		time: number;
		applied: number | null;
		enrolled: number | null;
		cart: number | null;
		capacity: number | null;
	};
	let data = $state<{
			points: Point[];
			windows: string[];
			observedAt: string | null;
			stale?: boolean;
			error?: string;
			source?: string;
		} | null>(null),
		error = $state(''),
		window = $state('live'),
		metric = $state<'applied' | 'enrolled' | 'cart'>('applied'),
		loading = $state(false);
	let version = 0;
	async function load() {
		const n = ++version;
		loading = true;
		try {
			const result = await request<typeof data>(
				`/student/trends?${new URLSearchParams({ term, code, section, window })}`
			);
			if (n === version) data = result;
		} catch (e) {
			if (n === version) error = String(e);
		} finally {
			if (n === version) loading = false;
		}
	}
	$effect(() => {
		term;
		code;
		section;
		window;
		void untrack(load);
	});
	onMount(() => {
		const id = setInterval(() => void load(), 600000);
		return () => clearInterval(id);
	});
	const max = $derived(Math.max(1, ...(data?.points || []).map((p) => p[metric] || 0)));
	const points = $derived((data?.points || []).filter((p) => p[metric] !== null));
	const path = $derived(
		points
			.map(
				(p, i) =>
					`${i ? 'L' : 'M'}${30 + (i / Math.max(1, points.length - 1)) * 650},${170 - ((p[metric] || 0) / max) * 150}`
			)
			.join(' ')
	);
</script>

<section>
	<h3>인원 추이</h3>
	<div class="filters">
		<select aria-label="추이 구간" bind:value={window}
			>{#each data?.windows || ['live'] as w}<option value={w}
					>{w === 'live' ? '최근 관측' : `이전 구간 ${Number(w.slice(1)) + 1}`}</option
				>{/each}</select
		><select aria-label="인원 지표" bind:value={metric}
			><option value="applied">신청 인원</option><option value="cart">장바구니</option><option
				value="enrolled">수강 인원</option
			></select
		>
	</div>
	{#if loading}<p role="status">인원 자료 갱신 중…</p>{/if}{#if error || data?.error}<p
			role="status"
		>
			{error || data?.error}
		</p>{/if}{#if points.length}<svg
			viewBox="0 0 710 200"
			role="img"
			aria-label={`${code} 인원 추이`}
			><line x1="30" x2="680" y1="170" y2="170" stroke="currentColor" opacity=".25" /><text
				x="0"
				y="25"
				fill="currentColor"
				font-size="14">{max}</text
			><path d={path} fill="none" stroke="#8470c4" stroke-width="2" /><text
				x="30"
				y="195"
				fill="currentColor"
				font-size="13">{new Date(points[0].time * 1000).toLocaleDateString('ko-KR')}</text
			><text x="570" y="195" fill="currentColor" font-size="13"
				>{new Date(points.at(-1)!.time * 1000).toLocaleDateString('ko-KR')}</text
			></svg
		>
		<p>
			마지막 관측: {points.at(-1)?.[metric]}명 · 정원 {points.at(-1)?.capacity ?? '자료 없음'}
		</p>{:else if !loading}<p>이 지표의 관측 자료가 없습니다.</p>{/if}<small
		>{data?.observedAt ? `관측 시각 ${data.observedAt.replace('T', ' ')} (한국 시간)` : ''}
		{data?.stale ? '· 최신 관측이 아닙니다.' : ''}</small
	>
</section>

<style>
	section {
		padding: 16px 0;
	}
	svg {
		width: 100%;
		max-height: 240px;
	}
	.filters {
		display: flex;
		gap: 12px;
	}
	small {
		opacity: 0.7;
	}
</style>
