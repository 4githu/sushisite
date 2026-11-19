<script lang="ts">
	import { onMount, onDestroy, tick, getContext } from 'svelte';
	import DailyNotebook from './DailyNotebook.svelte';
	import { request } from './api';
	import { verifiedPrivateOwner, samePrivateOwner } from './private-owner';
	import type { MemoBridge } from './memo-context';
	import { beforeNavigate } from '$app/navigation';
	import { readCaptures, updateCapture, type Capture } from './capture';
	import { taskDeadline, taskTiming, taskWaiting } from './planner';
	import { changePlan, readPlan, clockLabel, positionDay, type TimeBlock } from './day-planning';
	import type { CalendarEvent } from './types';
	let {
		date,
		events,
		tasks,
		pendingTasks = [],
		onedit,
		oncomplete,
		oncreate,
		onaddtask,
		onrefresh,
		onbusy
	}: {
		date: string;
		events: CalendarEvent[];
		tasks: CalendarEvent[];
		pendingTasks?: number[];
		onedit: (event: CalendarEvent) => void;
		oncomplete: (event: CalendarEvent) => void;
		oncreate: (minute: number) => void;
		onaddtask: () => void;
		onrefresh: () => void;
		onbusy: (value: boolean) => void;
	} = $props();
	const memoBridge = getContext<MemoBridge | undefined>('netaq-memo');
	let mobileTab = $state<'schedule'|'tasks'|'memo'>('schedule');
	let activeTask = $state(''),
		taskTitle = $state(''),
		eventTitle = $state(''),
		quickMinute = $state(540),
		quickBusy = $state(false);
	let eventInput: HTMLInputElement;
	$effect(() => {
		if (memoBridge) memoBridge.day = date;
	});
	onDestroy(() => {
		if (memoBridge?.day === date) memoBridge.day = '';
	});
	type Item = {
		key: string;
		title: string;
		done: boolean;
		detail: string;
		event?: CalendarEvent;
		capture?: Capture;
	};
	let blocks = $state<TimeBlock[]>([]),
		captures = $state<Capture[]>([]),
		loading = $state(true),
		saving = $state(false),
		error = $state(''),
		notice = $state(''),
		showDone = $state(false),
		completing = $state<string[]>([]);
	let dragKey = $state(''),
		dragBlock = $state(''),
		hoverMinute = $state<number | null>(null);
	let selected = $state<Item | null>(null),
		editingBlock = $state<TimeBlock | null>(null),
		start = $state(660),
		duration = $state(60),
		placementError = $state('');
	let dialog: HTMLDialogElement;

	let generation = 0;
	const items = $derived<Item[]>([
		...tasks.map((event) => ({
			key: 'event:' + event.id,
			title: event.title,
			done: event.status === 'done',
			detail: taskTiming(event),
			event
		})),
		...captures
			.filter((c) => c.kind === 'task')
			.map((capture) => ({
				key: 'capture:' + capture.id,
				title: capture.text,
				done: capture.done,
				detail: capture.today === date ? '이 날짜에 할 일' : '날짜 미정',
				capture
			}))
	]);
	const available = $derived(
		items
			.filter(
				(i) =>
					(showDone || !i.done) &&
					(!i.event || !taskWaiting(i.event, +new Date(date + 'T23:59:59')))
			)
			.sort(
				(a, b) =>
					Number(a.done) - Number(b.done) ||
					(a.event && taskDeadline(a.event) ? +new Date(taskDeadline(a.event)!) : Infinity) -
						(b.event && taskDeadline(b.event) ? +new Date(taskDeadline(b.event)!) : Infinity)
			)
	);
	const positioned = $derived(
		positionDay(
			date,
			events,
			blocks.map((b) => ({ ...b, title: items.find((i) => i.key === b.taskKey)?.title || b.title }))
		)
	);
	const dayStart = $derived(+new Date(date + 'T00:00:00'));
	const allDay = $derived(
		events.filter(
			(e) =>
				e.status === 'passive' &&
				(e.isAllDay || e.timeUnspecified) &&
				e.startTime.slice(0, 10) <= date &&
				(!e.endTime || e.endTime.slice(0, 10) >= date)
		)
	);
	function taskOf(block: TimeBlock) {
		return items.find((i) => i.key === block.taskKey);
	}
	function range(from: number, until: number) {
		return (
			clockLabel(Math.round((from - dayStart) / 60000)) +
			'–' +
			clockLabel(Math.round((until - dayStart) / 60000))
		);
	}
	async function load(day: string) {
		const serial = ++generation;
		loading = true;
		error = '';
		blocks = [];
		try {
			const [p, c] = await Promise.all([readPlan(day), readCaptures()]);
			if (serial === generation) {
				blocks = p;
				captures = c;
			}
		} catch (e) {
			if (serial === generation)
				error = e instanceof Error ? e.message : '계획을 불러오지 못했어요.';
		} finally {
			if (serial === generation) loading = false;
		}
	}
	$effect(() => {
		void load(date);
	});
	$effect(() => {
		onbusy(saving || quickBusy);
	});
	onDestroy(() => {
		generation++;
		onbusy(false);
	});
	onMount(() => {
		const changed = () => {
			void readCaptures()
				.then((c) => (captures = c))
				.catch(() => {});
		};
		window.addEventListener('netaq-captures-changed', changed);
		return () => window.removeEventListener('netaq-captures-changed', changed);
	});
	beforeNavigate(({ cancel }) => {
		if (saving || quickBusy) cancel();
	});
	function nextFree() {
		for (let minute = 540; minute <= 1500; minute += 30)
			if (
				!positioned.some(
					(p) => p.from < dayStart + (minute + 60) * 60000 && p.until > dayStart + minute * 60000
				)
			)
				return minute;
		return 540;
	}
	async function choose(item: Item, block: TimeBlock | null = null) {
		if (saving || loading) return;
		selected = item;
		editingBlock = block || blocks.find((b) => b.taskKey === item.key) || null;
		start = editingBlock?.start ?? nextFree();
		duration = editingBlock?.duration ?? 60;
		placementError = '';
		dialog.showModal();
		await tick();
	}
	async function place(
		item: Item,
		minute: number,
		minutes: number,
		existing: TimeBlock | null = null
	) {
		if (saving || loading) return false;
		if (
			!Number.isInteger(minute) ||
			!Number.isInteger(minutes) ||
			minute < 480 ||
			minutes < 15 ||
			minute + minutes > 1560
		) {
			placementError = '오전 8시부터 다음 날 오전 2시 안으로 시간을 정해주세요.';
			return false;
		}
		const day = date,
			serial = generation;
		const block: TimeBlock = {
			id: existing?.id || 'task:' + item.key,
			taskKey: item.key,
			title: item.title,
			start: minute,
			duration: minutes
		};
		saving = true;
		error = '';
		placementError = '';
		notice = '';
		try {
			const result = await changePlan(day, (list) => [
				...list.filter((b) => b.id !== block.id && b.taskKey !== item.key),
				block
			]);
			if (serial === generation) {
				blocks = result;
				notice = `${item.title} · ${clockLabel(minute)}–${clockLabel(minute + minutes)}에 배치했어요`;
				await tick();
			}
			return true;
		} catch (e) {
			if (serial === generation) {
				error = e instanceof Error ? e.message : '계획을 저장하지 못했어요.';
				placementError = error;
			}
			return false;
		} finally {
			saving = false;
		}
	}
	async function savePlacement(e: SubmitEvent) {
		e.preventDefault();
		if (selected && (await place(selected, Number(start), Number(duration), editingBlock)))
			dialog.close();
	}
	async function removePlacement() {
		if (!editingBlock || saving) return;
		const id = editingBlock.id,
			day = date,
			serial = generation;
		saving = true;
		error = '';
		try {
			const result = await changePlan(day, (list) => list.filter((b) => b.id !== id));
			if (serial === generation) {
				blocks = result;
				notice = '시간 배치를 해제했어요';
				dialog.close();
			}
		} catch (e) {
			placementError = e instanceof Error ? e.message : '배치를 해제하지 못했어요.';
		} finally {
			saving = false;
		}
	}
	function drag(event: DragEvent, item: Item, block?: TimeBlock) {
		dragKey = item.key;
		dragBlock = block?.id || '';
		event.dataTransfer?.setData('text/netaq-task', item.key);
		if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
	}
	function endDrag() {
		dragKey = '';
		dragBlock = '';
		hoverMinute = null;
	}
	async function drop(event: DragEvent, minute: number) {
		event.preventDefault();
		const key = dragKey || event.dataTransfer?.getData('text/netaq-task');
		const item = items.find((i) => i.key === key);
		const existing =
			blocks.find((b) => b.id === dragBlock) || blocks.find((b) => b.taskKey === key) || null;
		endDrag();
		if (item) await place(item, minute, existing?.duration || 60, existing);
	}
	async function complete(item: Item) {
		if (item.event) {
			oncomplete(item.event);
			return;
		}
		if (!item.capture || completing.includes(item.key)) return;
		completing = [...completing, item.key];
		try {
			captures = await updateCapture(item.capture.id, { done: !item.done });
		} catch (e) {
			error = e instanceof Error ? e.message : '완료 상태를 바꾸지 못했어요.';
		} finally {
			completing = completing.filter((k) => k !== item.key);
		}
	}

	const paperEvents = $derived<CalendarEvent[]>([
		...events.filter((e) => e.status === 'passive'),
		...blocks.map((block, i) => ({
			id: -i - 1,
			title: taskOf(block)?.title || block.title,
			description: '',
			startTime: new Date(dayStart + block.start * 60000).toISOString(),
			endTime: new Date(dayStart + (block.start + block.duration) * 60000).toISOString(),
			isAllDay: false,
			status: taskOf(block)?.done ? ('done' as const) : ('passive' as const),
			type: 'netaq-plan',
			groupName: null,
			categoryName: '계획',
			recurrenceGroupId: null,
			recurrenceIndex: null
		}))
	]);
	async function paperClick(minute: number) {
		const task = items.find((i) => i.key === activeTask);
		if (task) {
			await place(task, minute, 60, blocks.find((b) => b.taskKey === task.key) || null);
			activeTask = '';
		} else {
			quickMinute = minute;
			await tick();
			eventInput?.focus();
		}
	}
	function paperDrop(event: DragEvent) {
		const paper = (event.currentTarget as HTMLElement).querySelector('.paper');
		if (!paper) return;
		const r = paper.getBoundingClientRect();
		const minute = Math.max(
			480,
			Math.min(
				1545,
				480 + Math.round(((((event.clientY - r.top) / r.height) * 760 - 22) / 40) * 4) * 15
			)
		);
		void drop(event, minute);
	}
	async function quickAdd(event: SubmitEvent, task: boolean) {
		event.preventDefault();
		const title = (task ? taskTitle : eventTitle).trim();
		if (!title || quickBusy) return;
		quickBusy = true;
		error = '';
		try {
			const account = await verifiedPrivateOwner();
			const result = await request<CalendarEvent>('/calendar/events', {
				method: 'POST',
				body: {
					title,
					description: '',
					start_time: new Date(dayStart + (task ? 540 : quickMinute) * 60000).toISOString(),
					end_time: task ? null : new Date(dayStart + (quickMinute + 30) * 60000).toISOString(),
					is_all_day: false,
					task_unplanned: task,
					status: task ? 'todo' : 'passive',
					type: 'personal'
				}
			});
			if (!(await samePrivateOwner(account))) return;
			if (task && taskTitle.trim() === title) taskTitle = '';
			if (!task && eventTitle.trim() === title) eventTitle = '';
			notice = task ? '할 일을 추가했어요' : '일정을 추가했어요';
			onrefresh();
			return result;
		} catch (e) {
			error = e instanceof Error ? e.message : '추가하지 못했어요. 입력한 내용은 유지돼요.';
		} finally {
			quickBusy = false;
		}
	}
</script>

<svelte:window ondragend={endDrag} />
<div class="mobile-planning-tabs" role="tablist" aria-label="하루 계획 보기">
 {#each [['schedule','시간표'],['tasks','할 일'],['memo','메모']] as [key,label]}
  <button role="tab" aria-selected={mobileTab===key} onclick={()=>mobileTab=key as typeof mobileTab}>{label}{key==='tasks' ? ` ${available.filter(i=>!i.done).length}` : ''}</button>
 {/each}
</div>
<div class="day-planner" aria-label="하루 계획" aria-busy={loading} class:mobile-schedule={mobileTab==='schedule'} class:mobile-tasks={mobileTab==='tasks'} class:mobile-memo={mobileTab==='memo'}>
	<aside class="dp-tasks" aria-label="배치할 할 일">
		<header>
			<h2>할 일</h2>
			<span>{available.filter((i) => !i.done).length}개</span>
		</header>
		<form class="dp-quick-task" onsubmit={(e) => void quickAdd(e, true)}>
			<input
				aria-label="할 일 바로 추가"
				placeholder="할 일 추가 · Enter"
				bind:value={taskTitle}
				maxlength="120"
				disabled={quickBusy}
			/><button aria-label="할 일 추가" disabled={quickBusy || !taskTitle.trim()}>＋</button>
		</form>
		<div class="dp-task-list">
			{#each available as item (item.key)}
				<article class:done={item.done} class:selected={activeTask === item.key}>
					<label class="dp-check"
						><input
							type="checkbox"
							checked={item.done}
							disabled={saving ||
								completing.includes(item.key) ||
								(item.event &&
									(pendingTasks.includes(item.event.id) ||
										item.event.canEdit === false ||
										item.event.completionSource === 'external' ||
										taskWaiting(item.event)))}
							aria-label={`${item.title} 완료`}
							onchange={() => void complete(item)}
						/></label
					>
					<button
						class="dp-task-title"
						title={item.title}
						aria-pressed={activeTask === item.key}
						draggable={!item.done && !saving}
						ondragstart={(e) => drag(e, item)}
						ondragend={endDrag}
						onclick={() => (activeTask = activeTask === item.key ? '' : item.key)}
						ondblclick={() => item.event && onedit(item.event)}
						><strong>{item.title}</strong><small>{item.detail}</small></button
					>
				</article>
			{:else}<p class="dp-empty">
					{loading ? '불러오는 중…' : '할 일을 적고 Enter를 누르세요.'}
				</p>{/each}
		</div>
		<p class="dp-hint">끌어서 배치 · 선택 후 시간표 누르기</p>
		{#if activeTask}<button
				class="dp-edit-selected"
				onclick={() => {
					const item = items.find((i) => i.key === activeTask);
					if (item?.event) onedit(item.event);
					else if (item) void choose(item);
				}}>선택한 할 일 수정</button
			>{/if}
		<label class="dp-show-done"
			><input type="checkbox" bind:checked={showDone} />완료한 일 보기</label
		>
	</aside>
	<section
		class="dp-schedule"
		aria-label="하루 시간표"
		ondragover={(e) => {
			if (dragKey) e.preventDefault();
		}}
		ondrop={paperDrop}
	>
		<form class="dp-quick-event" onsubmit={(e) => void quickAdd(e, false)}>
			<button type="button" title="자세한 일정 입력" onclick={() => oncreate(quickMinute)}
				>{clockLabel(quickMinute)}</button
			><input
				bind:this={eventInput}
				aria-label="일정 바로 추가"
				placeholder="일정 이름 · Enter"
				bind:value={eventTitle}
				maxlength="120"
				disabled={quickBusy}
			/><button aria-label="일정 바로 저장" disabled={quickBusy || !eventTitle.trim()}>＋</button>
		</form>
		{#key date}<DailyNotebook
				events={paperEvents}
				{date}
				onempty={(minute) => void paperClick(minute)}
				onevent={(event) => {
					if (event.type === 'netaq-plan') {
						const block = blocks[-event.id - 1];
						if (block)
							void choose(
								taskOf(block) || {
									key: block.taskKey,
									title: block.title,
									done: false,
									detail: ''
								},
								block
							);
					} else onedit(event);
				}}
				oneventdrag={(event, e) => {
					const block = blocks[-event.id - 1];
					const task = block && taskOf(block);
					if (task) drag(e, task, block);
				}}
			/>{/key}
		<div class="dp-feedback" aria-live="polite">
			{#if error}<p role="alert">{error}</p>{:else}<p role="status">
					{saving ? '계획 저장 중…' : notice}
				</p>{/if}
		</div>
	</section>
	<aside class="dp-memo" aria-label="오늘 메모">
		{#if memoBridge?.render && !memoBridge.modalOpen}{@render memoBridge.render(true)}{/if}
	</aside>
</div>
<dialog
	class="dp-dialog"
	bind:this={dialog}
	aria-labelledby="placement-title"
	oncancel={(e) => {
		if (saving) e.preventDefault();
	}}
>
	<form onsubmit={savePlacement}>
		<header>
			<h2 id="placement-title">시간 배치</h2>
			<button
				type="button"
				aria-label="시간 배치 닫기"
				disabled={saving}
				onclick={() => dialog.close()}>×</button
			>
		</header>
		<p class="dp-selected-title">{selected?.title}</p>
		<div class="dp-fields">
			<label
				>시작 시간<select bind:value={start} disabled={saving}
					>{#each Array.from({ length: 72 }, (_, i) => 480 + i * 15) as minute}<option
							value={minute}>{clockLabel(minute)}</option
						>{/each}</select
				></label
			><label
				>소요 시간<input
					aria-label="소요 시간(분)"
					type="number"
					min="15"
					max={1560 - Number(start)}
					step="15"
					bind:value={duration}
					disabled={saving}
					required
				/>분</label
			>
		</div>
		<p class="dp-preview">
			{clockLabel(Number(start))}–{clockLabel(Number(start) + Number(duration || 0))}
		</p>
		<div class="dp-placement-feedback">
			{#if placementError}<p role="alert">{placementError}</p>{/if}
		</div>
		<footer>
			{#if editingBlock}<button
					type="button"
					class="dp-remove"
					disabled={saving}
					onclick={() => void removePlacement()}>배치 해제</button
				>{/if}<button class="dp-save" disabled={saving || loading}
				>{saving ? '저장 중…' : '배치하기'}</button
			>
		</footer>
	</form>
</dialog>

<style>
	.day-planner {
		display: grid;
		grid-template-columns: minmax(180px, 240px) minmax(300px, 420px) minmax(220px, 1fr);
		gap: 24px;
		align-items: start;
		max-width: 1280px;
		min-width: 0;
	}
	.dp-tasks {
		min-width: 0;
		display: grid;
		gap: 12px;
	}
	.dp-tasks header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		min-height: 36px;
	}
	.dp-tasks h2 {
		font-size: 18px;
		margin: 0;
	}
	.dp-tasks header span {
		font-size: 12px;
		color: var(--ondo-muted);
	}
	button,
	input,
	select {
		font: inherit;
	}
	button {
		cursor: pointer;
	}
	button:disabled {
		opacity: 0.5;
		cursor: default;
	}
	.dp-quick-task,
	.dp-quick-event {
		display: flex;
		align-items: center;
		gap: 4px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		min-height: 40px;
		background: white;
	}
	.dp-quick-task input,
	.dp-quick-event input {
		min-width: 0;
		flex: 1;
		border: 0;
		border-radius: 8px;
		font-size: 14px;
		padding: 10px;
		background: white;
		box-sizing: border-box;
		color: var(--ondo-ink);
	}
	.dp-quick-task input:focus,
	.dp-quick-event input:focus {
		box-shadow: none;
		outline: 0;
	}
	.dp-quick-task button,
	.dp-quick-event button {
		background: white;
		border: 0;
		min-width: 32px;
		min-height: 36px;
		color: var(--ondo-muted);
		font-size: 18px;
		border-radius: 8px;
	}
	.dp-quick-event button:first-child {
		font-size: 12px;
		padding: 6px;
		color: var(--ondo-accent);
	}
	.dp-task-list {
		max-height: calc(100dvh - 280px);
		overflow: auto;
		scrollbar-width: thin;
	}
	.dp-task-list article {
		display: flex;
		align-items: center;
		gap: 8px;
		border-bottom: 1px solid var(--ondo-line);
		min-height: 56px;
		padding: 4px 0;
	}
	.dp-task-list article.selected {
		background: #faeee9;
		border-radius: 6px;
	}
	.dp-check {
		width: 28px;
		min-height: 44px;
		display: grid;
		place-items: center;
		flex-shrink: 0;
	}
	.dp-check input {
		width: 18px;
		height: 18px;
		accent-color: var(--ondo-accent);
	}
	.dp-task-title {
		display: grid;
		gap: 4px;
		align-content: center;
		flex: 1;
		min-width: 0;
		min-height: 44px;
		border: 0;
		background: none;
		text-align: left;
		padding: 4px 0;
	}
	.dp-task-title strong {
		font-size: 14px;
		font-weight: 500;
		line-height: 1.5;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	.dp-task-title small {
		font-size: 11px;
		color: var(--ondo-muted);
		line-height: 1.4;
		overflow: hidden;
		white-space: nowrap;
		text-overflow: ellipsis;
	}
	.done .dp-task-title strong {
		text-decoration: line-through;
	}
	.dp-hint,
	.dp-empty,
	.dp-show-done {
		font-size: 12px;
		line-height: 1.6;
		color: var(--ondo-muted);
		margin: 0;
	}
	.dp-show-done {
		display: flex;
		gap: 8px;
		align-items: center;
		min-height: 32px;
	}
	.dp-edit-selected {
		justify-self: start;
		background: white;
		border: 0;
		border-bottom: 1px solid var(--ondo-line);
		color: var(--ondo-accent);
		font-size: 12px;
		min-height: 32px;
	}
	.dp-schedule {
		min-width: 0;
		max-width: 420px;
		width: 100%;
		display: grid;
		gap: 8px;
	}
	.dp-memo {
		border-left: 1px solid var(--ondo-line);
		padding-left: 20px;
		min-width: 0;
		height: calc(100dvh - 180px);
		min-height: 500px;
	}
	.dp-feedback {
		min-height: 24px;
		font-size: 12px;
		line-height: 1.5;
	}
	.dp-feedback p {
		margin: 0;
	}
	.dp-feedback [role='alert'] {
		color: #b33625;
	}
	.dp-dialog {
		position: fixed;
		inset: 0;
		margin: auto;
		box-sizing: border-box;
		width: min(420px, calc(100vw - 32px));
		max-height: calc(100dvh - 32px);
		overflow: auto;
		padding: 24px;
		border: 1px solid var(--ondo-line);
		border-radius: 12px;
		color: var(--ondo-ink);
		background: white;
	}
	.dp-dialog::backdrop {
		background: #14151959;
	}
	.dp-dialog form {
		display: grid;
		gap: 16px;
	}
	.dp-dialog header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}
	.dp-dialog h2 {
		font-size: 22px;
		margin: 0;
	}
	.dp-dialog header button {
		min-height: 40px;
		min-width: 40px;
		border: 0;
		background: white;
		font-size: 24px;
	}
	.dp-selected-title {
		font-size: 16px;
		margin: 0;
	}
	.dp-fields {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}
	.dp-fields label {
		display: grid;
		gap: 8px;
		font-size: 13px;
	}
	.dp-fields select,
	.dp-fields input {
		width: 100%;
		min-width: 0;
		box-sizing: border-box;
		min-height: 40px;
		border: 1px solid var(--ondo-line);
		border-radius: 8px;
		background: white;
		padding: 8px;
		font-size: 16px;
	}
	.dp-preview {
		font-size: 14px;
		margin: 0;
	}
	.dp-placement-feedback {
		min-height: 20px;
		font-size: 13px;
		color: #b33625;
	}
	.dp-dialog footer {
		display: flex;
		gap: 12px;
	}
	.dp-save {
		flex: 1;
		min-height: 44px;
		border: 0;
		border-radius: 8px;
		background: var(--ondo-accent);
		color: white;
		font-weight: 600;
	}
	.dp-remove {
		min-height: 44px;
		padding: 8px;
		border: 0;
		background: white;
		color: #b33625;
	}
	.mobile-planning-tabs{display:none}
 @media (max-width: 1100px) {
		.day-planner {
			grid-template-columns: minmax(180px, 240px) minmax(0, 420px);
		}
		.dp-memo {
			grid-column: 1/-1;
			min-height: 320px;
			height: 360px;
			border-left: 0;
			border-top: 1px solid var(--ondo-line);
			padding-left: 0;
			padding-top: 20px;
		}
	}
	@media (max-width: 760px) {
        .mobile-planning-tabs{display:flex;gap:4px;padding:4px;background:#f2f3f5;border-radius:10px;margin-bottom:16px}
        .mobile-planning-tabs button{flex:1;border:0;border-radius:7px;background:transparent;min-height:40px;color:#696b73}
        .mobile-planning-tabs button[aria-selected="true"]{background:white;color:#c4412c;font-weight:700}
        .mobile-schedule .dp-tasks,.mobile-schedule .dp-memo,.mobile-tasks .dp-schedule,.mobile-tasks .dp-memo,.mobile-memo .dp-tasks,.mobile-memo .dp-schedule{display:none}

		.day-planner {
			grid-template-columns: 1fr;
			gap: 20px;
		}
		.dp-tasks {
			gap: 8px;
		}
		.dp-tasks h2 {
			font-size: 16px;
		}
		.dp-task-list {
			max-height: min(65vh, 680px);
		}
		.dp-task-list article {
			min-height: 40px;
			padding: 0;
		}
		.dp-task-title small {
			display: none;
		}
		.dp-task-title strong {
			font-size: 14px;
			font-weight: 400;
		}
		.dp-check {
			min-height: 40px;
		}
		.dp-hint {
			font-size: 11px;
		}
		.dp-show-done {
			display: none;
		}
		.dp-schedule {
			justify-self: center;
		}
		.dp-memo {
			grid-column: 1;
			min-height: 360px;
			height: 420px;
		}
	}
</style>
