<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { CalendarEvent } from '$lib/personal-project/shared/types';

	type CalendarDay = { date: Date; key: string; currentMonth: boolean; isToday: boolean };

	let cursor = $state(new Date());
	let events = $state<CalendarEvent[]>([]);
	let loading = $state(true);
	let error = $state('');
	let showModal = $state(false);
	let selected = $state<CalendarEvent | null>(null);
	let saving = $state(false);

	let title = $state('');
	let description = $state('');
	let startTime = $state('');
	let endTime = $state('');
	let status = $state<'passive' | 'todo' | 'done'>('todo');
	let categoryName = $state('');
	let repeatUntil = $state('');
	let intervalWeeks = $state(1);
	let editScope = $state<'this' | 'following'>('this');

	const monthTitle = $derived(
		new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long' }).format(cursor)
	);
	const days = $derived.by(() => monthDays(cursor));

	function localKey(date: Date) {
		const y = date.getFullYear();
		const m = String(date.getMonth() + 1).padStart(2, '0');
		const d = String(date.getDate()).padStart(2, '0');
		return `${y}-${m}-${d}`;
	}

	function localInput(date: Date) {
		const hour = String(date.getHours()).padStart(2, '0');
		const minute = String(date.getMinutes()).padStart(2, '0');
		return `${localKey(date)}T${hour}:${minute}`;
	}

	function timeLabel(value: string) {
		return new Intl.DateTimeFormat('ko-KR', {
			hour: '2-digit',
			minute: '2-digit',
			hour12: false
		}).format(new Date(value));
	}

	function syncEndToStart() {
		if (!startTime) return;
		if (!endTime || new Date(endTime) < new Date(startTime)) endTime = startTime;
		const startDate = startTime.slice(0, 10);
		if (repeatUntil && repeatUntil < startDate) repeatUntil = startDate;
	}

	function monthDays(date: Date): CalendarDay[] {
		const first = new Date(date.getFullYear(), date.getMonth(), 1);
		const start = new Date(first);
		start.setDate(first.getDate() - first.getDay());
		const today = localKey(new Date());
		return Array.from({ length: 42 }, (_, index) => {
			const day = new Date(start);
			day.setDate(start.getDate() + index);
			const key = localKey(day);
			return {
				date: day,
				key,
				currentMonth: day.getMonth() === date.getMonth(),
				isToday: key === today
			};
		});
	}

	function eventsForDay(key: string) {
		return events.filter((event) => localKey(new Date(event.startTime)) === key);
	}

	async function loadEvents() {
		loading = true;
		error = '';
		const from = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
		const to = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
		from.setDate(from.getDate() - 7);
		to.setDate(to.getDate() + 7);
		try {
			events = await personalApi.events(from.toISOString(), to.toISOString());
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '일정을 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	function moveMonth(amount: number) {
		cursor = new Date(cursor.getFullYear(), cursor.getMonth() + amount, 1);
		loadEvents();
	}

	function openCreate(date = new Date()) {
		selected = null;
		title = '';
		description = '';
		const start = new Date(date);
		start.setHours(10, 0, 0, 0);
		const end = new Date(start);
		end.setHours(11);
		startTime = localInput(start);
		endTime = localInput(end);
		status = 'todo';
		categoryName = '';
		repeatUntil = '';
		intervalWeeks = 1;
		editScope = 'this';
		showModal = true;
	}

	async function openEvent(event: CalendarEvent) {
		if (event.type === 'aura') {
			try {
				const detail = await personalApi.event(event.id);
				window.location.href = detail.serviceLink ?? '/personal-project/aura';
			} catch {
				window.location.href = '/personal-project/aura';
			}
			return;
		}
		selected = event;
		title = event.title;
		description = event.description;
		startTime = localInput(new Date(event.startTime));
		endTime = event.endTime ? localInput(new Date(event.endTime)) : '';
		status = event.status;
		categoryName = event.categoryName ?? '';
		repeatUntil = '';
		editScope = 'this';
		showModal = true;
	}

	async function saveEvent(event: SubmitEvent) {
		event.preventDefault();
		if (!title.trim() || !startTime) return;
		saving = true;
		error = '';
		try {
			if (selected) {
				await personalApi.updateEventScope(selected.id, {
					title: title.trim(),
					description,
					start_time: new Date(startTime).toISOString(),
					end_time: endTime ? new Date(endTime).toISOString() : null,
					status,
					category_name: categoryName || null,
					scope: editScope
				});
			} else {
				const body = {
					title: title.trim(),
					description,
					start_time: new Date(startTime).toISOString(),
					end_time: endTime ? new Date(endTime).toISOString() : null,
					is_all_day: false,
					status,
					type: 'personal',
					category_name: categoryName || undefined
				};
				if (repeatUntil) {
					await personalApi.createEventSeries({
						...body,
						repeat_count: 2,
						interval_weeks: intervalWeeks,
						repeat_until: new Date(`${repeatUntil}T23:59:59`).toISOString()
					});
				} else {
					await personalApi.createEvent(body);
				}
			}
			showModal = false;
			await loadEvents();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	async function removeEvent() {
		if (!selected || !confirm('이 일정을 삭제할까요?')) return;
		saving = true;
		try {
			await personalApi.deleteEventScope(selected.id, editScope);
			showModal = false;
			await loadEvents();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '삭제하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	onMount(async () => {
		await loadEvents();
		const eventId = Number(page.url.searchParams.get('event'));
		if (!eventId) return;
		const event = events.find((item) => item.id === eventId) ?? (await personalApi.event(eventId));
		await openEvent(event);
	});
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">My rhythm</p>
		<h1>나의 캘린더</h1>
		<p>일정과 클리닉을 한눈에 보고, 하루의 흐름을 가볍게 정리하세요.</p>
	</div>
	<button class="primary-button" onclick={() => openCreate()}>＋ 새 일정</button>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}

<section class="calendar-card card" aria-busy={loading}>
	<header class="calendar-toolbar">
		<div>
			<button class="icon-button" onclick={() => moveMonth(-1)} aria-label="이전 달">‹</button>
			<button class="icon-button" onclick={() => moveMonth(1)} aria-label="다음 달">›</button>
			<button
				class="today-button"
				onclick={() => {
					cursor = new Date();
					loadEvents();
				}}>오늘</button
			>
		</div>
		<h2>{monthTitle}</h2>
		<div class="legend"><span></span> 개인 일정 <span class="aura"></span> 아우라</div>
	</header>

	<div class="weekdays" aria-hidden="true">
		<span class="sunday">일</span><span>월</span><span>화</span><span>수</span><span>목</span><span
			>금</span
		><span>토</span>
	</div>
	<div class="calendar-grid">
		{#each days as day (day.key)}
			<div class:outside={!day.currentMonth} class:today={day.isToday} class="day-cell">
				<button
					class="day-number"
					onclick={() => openCreate(day.date)}
					aria-label={`${day.key} 일정 추가`}
				>
					{day.date.getDate()}
				</button>
				<div class="events">
					{#each eventsForDay(day.key).slice(0, 3) as item (item.id)}
						<button
							class:aura={item.type === 'aura'}
							class="event-chip"
							onclick={() => openEvent(item)}
						>
							<time>{timeLabel(item.startTime)}</time>
							<span>{item.title}</span>
						</button>
					{/each}
					{#if eventsForDay(day.key).length > 3}
						<small>+ {eventsForDay(day.key).length - 3}개 더보기</small>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</section>

{#if showModal}
	<div
		class="modal-backdrop"
		role="presentation"
		onclick={(event) => event.target === event.currentTarget && (showModal = false)}
	>
		<form class="modal" onsubmit={saveEvent}>
			<h2>{selected ? '일정 편집' : '새 일정 만들기'}</h2>
			<div class="form-grid">
				<div class="field full">
					<label for="event-title">일정 이름</label>
					<input id="event-title" bind:value={title} placeholder="무엇을 할 예정인가요?" required />
				</div>
				<div class="field">
					<label for="event-start">시작</label>
					<input
						id="event-start"
						type="datetime-local"
						step="1800"
						bind:value={startTime}
						onchange={syncEndToStart}
						required
					/>
				</div>
				<div class="field">
					<label for="event-end">종료</label>
					<input
						id="event-end"
						type="datetime-local"
						step="1800"
						min={startTime}
						bind:value={endTime}
						onchange={syncEndToStart}
					/>
				</div>
				<div class="field">
					<label for="event-status">상태</label>
					<select id="event-status" bind:value={status}>
						<option value="todo">할 일</option>
						<option value="done">완료</option>
						<option value="passive">정보성</option>
					</select>
				</div>
				<div class="field">
					<label for="event-category">카테고리</label>
					<input id="event-category" bind:value={categoryName} placeholder="예: 개인, 공부" />
				</div>
				<div class="field full">
					<label for="event-description">메모</label>
					<textarea
						id="event-description"
						bind:value={description}
						placeholder="기억할 내용을 남겨주세요"
					></textarea>
				</div>
				{#if selected?.recurrenceGroupId}
					<div class="field full recurrence-scope">
						<label for="event-scope">반복 일정 수정 범위</label>
						<select id="event-scope" bind:value={editScope}>
							<option value="this">이 일정만 변경</option>
							<option value="following">이 일정 및 이후 일정 변경</option>
						</select>
					</div>
				{:else if !selected}
					<div class="field">
						<label for="event-repeat">반복 종료 날짜</label>
						<input
							id="event-repeat"
							type="date"
							min={startTime.slice(0, 10)}
							bind:value={repeatUntil}
						/>
					</div>
					{#if repeatUntil}
						<div class="field">
							<label for="event-interval">반복 간격</label>
							<select id="event-interval" bind:value={intervalWeeks}>
								<option value={1}>매주</option>
								<option value={2}>2주마다</option>
								<option value={3}>3주마다</option>
								<option value={4}>4주마다</option>
							</select>
						</div>
					{/if}
				{/if}
			</div>
			<div class="modal-actions">
				{#if selected}
					<button type="button" class="danger-button" onclick={removeEvent} disabled={saving}
						>삭제</button
					>
				{/if}
				<button type="button" class="ghost-button" onclick={() => (showModal = false)}>취소</button>
				<button class="primary-button" disabled={saving}>{saving ? '저장 중…' : '저장하기'}</button>
			</div>
		</form>
	</div>
{/if}

<style>
	.calendar-card {
		overflow: hidden;
	}

	.calendar-toolbar {
		min-height: 76px;
		padding: 0 22px;
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		align-items: center;
		border-bottom: 1px solid var(--pp-line);
	}

	.calendar-toolbar h2 {
		margin: 0;
		font-family: Georgia, 'Noto Sans KR', serif;
		font-size: 19px;
		font-weight: 500;
	}

	.icon-button,
	.today-button {
		border: 1px solid var(--pp-line);
		background: white;
		color: var(--pp-ink);
		cursor: pointer;
	}

	.icon-button {
		width: 32px;
		height: 32px;
		font-size: 22px;
		line-height: 1;
	}

	.icon-button:first-child {
		border-radius: 7px 0 0 7px;
	}

	.icon-button:nth-child(2) {
		margin-left: -1px;
		border-radius: 0 7px 7px 0;
	}

	.today-button {
		height: 32px;
		margin-left: 8px;
		padding: 0 11px;
		border-radius: 7px;
		font-size: 11px;
		font-weight: 700;
	}

	.legend {
		justify-self: end;
		display: flex;
		align-items: center;
		gap: 6px;
		color: var(--pp-muted);
		font-size: 10px;
	}

	.legend span {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--pp-sage);
	}

	.legend span.aura {
		margin-left: 8px;
		background: var(--pp-peach);
	}

	.weekdays,
	.calendar-grid {
		display: grid;
		grid-template-columns: repeat(7, minmax(0, 1fr));
	}

	.weekdays {
		border-bottom: 1px solid var(--pp-line);
		background: #faf9f5;
	}

	.weekdays span {
		padding: 10px;
		color: var(--pp-muted);
		font-size: 10px;
		font-weight: 700;
		text-align: center;
	}

	.weekdays .sunday {
		color: #b76e5d;
	}

	.day-cell {
		min-height: 116px;
		padding: 8px;
		border-right: 1px solid var(--pp-line);
		border-bottom: 1px solid var(--pp-line);
		background: rgba(255, 255, 255, 0.25);
	}

	.day-cell:nth-child(7n) {
		border-right: 0;
	}

	.day-cell.outside {
		background: #faf9f6;
		color: #b8b9b5;
	}

	.day-number {
		width: 25px;
		height: 25px;
		padding: 0;
		border: 0;
		border-radius: 50%;
		background: transparent;
		color: inherit;
		font-size: 11px;
		cursor: pointer;
	}

	.today .day-number {
		background: var(--pp-sage-dark);
		color: white;
		font-weight: 700;
	}

	.events {
		margin-top: 5px;
		display: grid;
		gap: 4px;
	}

	.event-chip {
		width: 100%;
		min-width: 0;
		padding: 5px 6px;
		display: flex;
		gap: 5px;
		border: 0;
		border-left: 3px solid var(--pp-sage);
		border-radius: 4px;
		background: #e8eee8;
		color: #405348;
		font-size: 9px;
		text-align: left;
		cursor: pointer;
	}

	.event-chip.aura {
		border-left-color: var(--pp-peach);
		background: #f7e8df;
		color: #825a45;
	}

	.event-chip time {
		opacity: 0.72;
	}

	.event-chip span {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.events small {
		padding-left: 7px;
		color: var(--pp-muted);
		font-size: 9px;
	}

	@media (max-width: 700px) {
		.calendar-toolbar {
			grid-template-columns: 1fr auto;
		}

		.calendar-toolbar h2 {
			grid-row: 1;
			grid-column: 2;
		}

		.legend {
			display: none;
		}

		.day-cell {
			min-height: 86px;
			padding: 4px;
		}

		.event-chip {
			padding: 4px;
		}

		.event-chip time {
			display: none;
		}
	}
</style>
