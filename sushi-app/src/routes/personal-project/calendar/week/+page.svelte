<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { CalendarEvent } from '$lib/personal-project/shared/types';

	let cursor = $state(new Date());
	let events = $state<CalendarEvent[]>([]);
	let selected = $state<CalendarEvent | null>(null);
	let error = $state('');
	let loading = $state(true);

	const slots = Array.from({ length: 34 }, (_, index) => index);
	const days = $derived(weekDays(cursor));
	const title = $derived(
		`${days[0]?.toLocaleDateString('ko-KR')} — ${days[6]?.toLocaleDateString('ko-KR')}`
	);

	function startOfWeek(date: Date) {
		const result = new Date(date);
		const day = result.getDay();
		result.setDate(result.getDate() - (day === 0 ? 6 : day - 1));
		result.setHours(0, 0, 0, 0);
		return result;
	}

	function weekDays(date: Date) {
		const monday = startOfWeek(date);
		return Array.from({ length: 7 }, (_, index) => {
			const day = new Date(monday);
			day.setDate(monday.getDate() + index);
			return day;
		});
	}

	function slotDate(day: number, slot: number) {
		const value = new Date(days[day]);
		value.setHours(8, slot * 30, 0, 0);
		return value;
	}

	function eventsAt(day: number, slot: number) {
		const start = slotDate(day, slot);
		const end = new Date(start.getTime() + 30 * 60_000);
		return events.filter((event) => {
			const eventStart = new Date(event.startTime);
			const eventEnd = event.endTime
				? new Date(event.endTime)
				: new Date(eventStart.getTime() + 60 * 60_000);
			return eventStart < end && eventEnd > start;
		});
	}

	function timeLabel(slot: number) {
		const minutes = 8 * 60 + slot * 30;
		return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
	}

	async function load() {
		loading = true;
		error = '';
		const from = startOfWeek(cursor);
		const to = new Date(from);
		to.setDate(to.getDate() + 7);
		try {
			events = await personalApi.events(from.toISOString(), to.toISOString());
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '일정을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	function move(step: number) {
		const next = new Date(cursor);
		next.setDate(next.getDate() + step * 7);
		cursor = next;
		load();
	}

	async function open(event: CalendarEvent) {
		if (event.type === 'aura') {
			const detail = await personalApi.event(event.id);
			location.href = detail.serviceLink ?? '/personal-project/aura';
			return;
		}
		selected = event;
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Weekly calendar</p>
		<h1>주간 시간표</h1>
		<p>모든 개인 일정과 아우라 클리닉을 로컬 시간 기준으로 표시합니다.</p>
	</div>
	<div class="week-nav">
		<button onclick={() => move(-1)} aria-label="이전 주">‹</button>
		<strong>{title}</strong>
		<button onclick={() => move(1)} aria-label="다음 주">›</button>
	</div>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}

<section class="card timetable" aria-busy={loading}>
	<div class="grid">
		<div class="corner"></div>
		{#each days as day}
			<header class:today={day.toDateString() === new Date().toDateString()}>
				<span>{day.toLocaleDateString('ko-KR', { weekday: 'short' })}</span>
				<strong>{day.getDate()}</strong>
			</header>
		{/each}
		{#each slots as slot}
			<div class:majorBoundary={slot === 8 || slot === 20} class="time">
				{slot % 2 === 0 ? timeLabel(slot) : ''}
			</div>
			{#each days as _, dayIndex}
				{@const busy = eventsAt(dayIndex, slot)}
				<div
					class:busy={busy.length}
					class:aura={busy[0]?.type === 'aura'}
					class:majorBoundary={slot === 8 || slot === 20}
					class="slot"
				>
					{#if busy.length && slot % 2 === 0}
						<button onclick={() => open(busy[0])}>{busy[0].title}</button>
					{/if}
				</div>
			{/each}
		{/each}
	</div>
</section>

{#if selected}
	<div
		class="modal-backdrop"
		role="presentation"
		onclick={(event) => event.target === event.currentTarget && (selected = null)}
	>
		<section class="modal detail" role="dialog" tabindex="-1">
			<p class="eyebrow">Personal event</p>
			<h2>{selected.title}</h2>
			<p>{new Date(selected.startTime).toLocaleString('ko-KR')}</p>
			<p>{selected.description || '메모 없음'}</p>
			{#if selected.recurrenceGroupId}<span>반복 일정 #{(selected.recurrenceIndex ?? 0) + 1}</span
				>{/if}
			<div class="modal-actions">
				<button class="ghost-button" onclick={() => (selected = null)}>닫기</button>
				<a class="primary-button" href={`/personal-project/calendar?event=${selected.id}`}
					>월간에서 수정</a
				>
			</div>
		</section>
	</div>
{/if}

<style>
	.week-nav {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.week-nav button {
		width: 32px;
		height: 32px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		background: white;
		cursor: pointer;
	}
	.week-nav strong {
		min-width: 170px;
		font-size: 10px;
		text-align: center;
	}
	.timetable {
		overflow: visible;
	}
	.grid {
		min-width: 0;
		display: grid;
		grid-template-columns: 58px repeat(7, 1fr);
	}
	.corner,
	header {
		position: sticky;
		top: 0;
		z-index: 2;
		height: 58px;
		border-bottom: 1px solid var(--pp-line);
		background: var(--pp-card);
	}
	header {
		display: grid;
		place-content: center;
		text-align: center;
	}
	header span {
		color: var(--pp-muted);
		font-size: 9px;
	}
	header strong {
		font:
			600 15px Georgia,
			serif;
	}
	header.today strong {
		color: var(--pp-sage-dark);
	}
	.time {
		height: 31px;
		padding: 5px 8px;
		border-right: 1px solid var(--pp-line);
		color: var(--pp-muted);
		font-size: 8px;
		text-align: right;
	}
	.slot {
		height: 31px;
		border-right: 1px solid var(--pp-line);
		border-bottom: 1px solid #efede7;
	}
	.time.majorBoundary,
	.slot.majorBoundary {
		border-top: 3px solid #87968b !important;
		box-shadow: inset 0 1px 0 #ffffff;
	}
	.slot.busy {
		background: #e5ece6;
	}
	.slot.aura {
		background: #f1ddd3;
	}
	.slot button {
		width: 100%;
		height: 100%;
		overflow: hidden;
		border: 0;
		background: transparent;
		color: #4d675b;
		font-size: 8px;
		font-weight: 700;
		text-overflow: ellipsis;
		white-space: nowrap;
		cursor: pointer;
	}
	.detail h2 {
		margin: 0;
		font:
			500 22px Georgia,
			'Noto Sans KR',
			serif;
	}
	.detail p {
		color: var(--pp-muted);
		font-size: 11px;
	}
	.detail > span {
		font-size: 9px;
	}
	.detail a {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}
</style>
