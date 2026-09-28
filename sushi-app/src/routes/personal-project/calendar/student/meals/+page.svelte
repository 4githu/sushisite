<script lang="ts">
	import { onMount } from 'svelte';
	import { request } from '$lib/personal-project/shared/api';
	import '$lib/personal-project/student/student.css';
	type Menu = {
		date: string;
		restaurants: { title: string; breakfast: string; lunch: string; dinner: string }[];
		source: string;
		fetchedAt: string;
		stale: boolean;
	};
	let date = $state(
			new Intl.DateTimeFormat('en-CA', {
				timeZone: 'Asia/Seoul',
				year: 'numeric',
				month: '2-digit',
				day: '2-digit'
			}).format(new Date())
		),
		data = $state<Menu | null>(null),
		loading = $state(true),
		error = $state(''),
		allOpen = $state(false),
		openVersion = $state(0);
	let version = 0;
	async function load() {
		const n = ++version;
		loading = true;
		error = '';
		data = null;
		try {
			const result = await request<Menu>(`/student/meals?day=${date}`);
			if (n === version) data = result;
		} catch (e) {
			if (n === version) error = e instanceof Error ? e.message : '식단 불러오기 실패';
		} finally {
			if (n === version) loading = false;
		}
	}
	function shift(days: number) {
		const d = new Date(`${date}T12:00:00Z`);
		d.setUTCDate(d.getUTCDate() + days);
		date = d.toISOString().slice(0, 10);
		void load();
	}
	onMount(load);
</script>

<svelte:head><title>서울대 학식 · NETAQ</title></svelte:head>
<div class="student-page">
	<header class="page-heading">
		<div>
			<span class="eyebrow">CAMPUS / DINING</span>
			<h1>오늘 뭐 먹지?</h1>
			<p class="muted">서울대학교 생활협동조합의 식당별 식단입니다.</p>
		</div>
		<div class="fields">
			<button aria-label="이전 날짜" onclick={() => shift(-1)}>‹</button><input
				aria-label="식단 날짜"
				type="date"
				bind:value={date}
				onchange={() => {
					if (date) void load();
				}}
			/><button aria-label="다음 날짜" onclick={() => shift(1)}>›</button>
		</div>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>
		<button onclick={load}>다시 불러오기</button>{/if}
	<div class="fields">
		<button
			onclick={() => {
				allOpen = !allOpen;
				openVersion++;
			}}>{allOpen ? '모두 접기' : '모두 펼치기'}</button
		><a href={`https://snuco.snu.ac.kr/foodmenu/?date=${date}`} target="_blank" rel="noreferrer"
			>공식 식단 ↗</a
		>
	</div>
	{#if loading}<p role="status">공식 식단을 불러오는 중…</p>{:else if data}
		{#if data.stale}<p class="notice">
				새 식단을 가져오지 못해 마지막으로 불러온 자료를 표시합니다.
			</p>{/if}
		<p class="muted">
			{data.date} · {data.restaurants.length}개 식당 · 조회 {new Date(
				data.fetchedAt
			).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' })}
		</p>
		<div class="restaurants">
			{#key openVersion}{#each data.restaurants as restaurant, i}<details
						class="panel"
						open={allOpen || (openVersion === 0 && i === 0)}
					>
						<summary>{restaurant.title}<span>메뉴 보기</span></summary>
						<div class="meals">
							{#each [['breakfast', '아침'], ['lunch', '점심'], ['dinner', '저녁']] as [key, label]}<section
								>
									<h2>{label}</h2>
									<p>
										{restaurant[key as 'breakfast' | 'lunch' | 'dinner'] ||
											'등록된 메뉴가 없습니다.'}
									</p>
								</section>{/each}
						</div>
					</details>{:else}<section class="panel">
						<h2>등록된 식단이 없습니다</h2>
						<p>다른 날짜를 선택하거나 공식 식단을 확인해주세요.</p>
					</section>{/each}{/key}
		</div>{/if}
</div>

<style>
	.restaurants {
		display: grid;
		gap: 12px;
	}
	.restaurants summary {
		display: flex;
		justify-content: space-between;
		gap: 10px;
	}
	.restaurants summary span {
		font-size: 11px;
		color: #777;
		font-weight: 400;
	}
	.meals {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 24px;
		padding: 16px 0;
	}
	.meals h2 {
		font-size: 13px;
		color: var(--ondo-accent);
	}
	.meals p {
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		font-size: 13px;
	}
	.meals section + section {
		border-left: 1px solid #e2e3e7;
		padding-left: 24px;
	}
	@media (max-width: 760px) {
		.meals {
			grid-template-columns: 1fr;
			gap: 10px;
		}
		.meals section + section {
			border-left: 0;
			border-top: 1px solid #e2e3e7;
			padding: 16px 0 0;
		}
	}
</style>
