<script lang="ts">
	import {occurrence,repeatCount,type RepeatUnit} from './recurrence';
	import { onMount, getContext } from 'svelte';
	import {beforeNavigate,replaceState} from '$app/navigation';
	import PdfEditor from '../pdf/PdfEditor.svelte';
	import DailyPlan from './DailyPlan.svelte';
	import DayPlanner from './DayPlanner.svelte';
	import CalendarIcon from './CalendarIcon.svelte';
	import {
		readTaskMode,
		saveTaskMode,
		inProject,
		taskGroups,
		type CalendarProject,
		categoryPaths,
		eventCategories,
		categoryHidden,
		safeEventUrl,
		taskTiming,
		taskWaiting,
		taskDeadline
	} from './planner';
	import { personalApi, request } from './api';
	import type { CalendarEvent } from './types';
	import CalendarConnections from './CalendarConnections.svelte';
	import './calendar-workspace.css';
	const calendarNavigation = getContext<{ setView: (value: string) => void } | undefined>(
		'calendar-navigation'
	);
	$effect(() => {
		calendarNavigation?.setView(view);
	});
	type View = 'month' | 'week' | 'day' | 'tasks';
	type Project = CalendarProject;
	let taskMode = $state<'time' | 'theme'>('time');
	onMount(() => {
		taskMode = readTaskMode();
	});
	let {
		initialView = 'month',
		aura = false,
		refreshKey = '',
		onCreate,
		onChanged,
		onDate
	}: {
		initialView?: View;
		aura?: boolean;
		refreshKey?: string;
		onCreate?: (start: Date, end: Date) => void;
		onChanged?: () => void;
		onDate?: (date: Date) => void;
	} = $props();
	let view = $state<View>('month'),
		cursor = $state(new Date()),
		events = $state<CalendarEvent[]>([]),
		tasks = $state<CalendarEvent[]>([]),
		projects = $state<Project[]>([]);
	let hidden = $state<string[]>([]),
		query = $state(''),
		projectFilter = $state('all'),
		showCompleted = $state(false),
		showConnections = $state(false),
		filtersOpen = $state(false);
	let error = $state(''),
		notice = $state(''),
		loading = $state(false),
		mounted = $state(false),
		selected = $state<CalendarEvent | null>(null),
		showEditor = $state(false),
		saving = $state(false),
		editorError = $state('');
	let dialog: HTMLDialogElement;
	let zoomMode = $state(false);
	let weekScroll = $state<HTMLDivElement>();
	let dragStart = $state<{ day: Date; slot: number } | null>(null);
	let dragEnd = $state<{ day: Date; slot: number } | null>(null);
	let title = $state(''),
		description = $state(''),
		start = $state(''),
		end = $state(''),
		allDayStart = $state(''),
		allDayEnd = $state(''),
		allDay = $state(false),
		task = $state(false),
		taskUnplanned = $state(false),
		taskDone = $state(false),
		category = $state(''),
		locationText = $state(''),
		webUrl = $state(''),
		project = $state(''),
		repeat = $state(1),
		intervalWeeks = $state(1),
		repeatUntil = $state(''),
		scope = $state<'this' | 'following' | 'all'>('this');
	let timeUnspecified=$state(false),repeatMode=$state<'none'|RepeatUnit>('none'),repeatEnd=$state<'count'|'date'>('count');
	let selectingDates=$state(false),selectedDates=$state<string[]>([]),editorDates=$state<string[]>([]);
	function chooseDate(day:Date){if(!selectingDates){editorDates=[];create(day);return;}const value=dayKey(day);selectedDates=selectedDates.includes(value)?selectedDates.filter(d=>d!==value):[...selectedDates,value].sort();}
	function createSelected(){if(!selectedDates.length)return;create(new Date(selectedDates[0]+'T12:00:00'));editorDates=[...selectedDates];editorBaseline=editorSignature();}
	function changeRepeat(){repeat=repeatMode==='none'?1:Math.max(2,repeat);repeatEndFromCount();}
	let editorBaseline=$state('');
	function editorSignature(){return JSON.stringify({title,description,start,end,allDayStart,allDayEnd,allDay,timeUnspecified,task,taskUnplanned,taskDone,category,locationText,webUrl,project,repeat,intervalWeeks,repeatUntil,repeatMode,repeatEnd,availableFrom,dueAt,editorDates});}
	const editorDirty=$derived(showEditor && editorBaseline!==editorSignature());
	function closeEditor(){if(saving)return;if(editorDirty && !confirm('입력 중인 일정을 버릴까요?'))return;showEditor=false;}
	beforeNavigate(({cancel})=>{if(planningBusy || saving || (editorDirty && !confirm('입력 중인 일정을 두고 이동할까요?')))cancel();});
	let exportTargets = $state<{ id: number; calendarId: string; label: string }[]>([]),
		exportTarget = $state(''),
		exportOpen = $state(false);
	let loadVersion = 0;
	let pendingTasks = $state<number[]>([]);
	let quickTitle = $state(''),
		quickDate = $state(dayKey(new Date())),
		quickUnplanned = $state(false),
		addingTask = $state(false);
	let taskFilter = $state<'all' | 'today' | 'overdue' | 'upcoming'>('all');
	let undoTask = $state<CalendarEvent | null>(null);
	function matchesTaskDate(e: CalendarEvent) {
		const deadline = taskDeadline(e);
		if (!deadline) return taskFilter === 'all';
		const date = dayKey(new Date(deadline)),
			today = dayKey(new Date());
		return (
			taskFilter === 'all' ||
			(taskFilter === 'today'
				? date === today
				: taskFilter === 'overdue'
					? date < today
					: date > today)
		);
	}
	function replaceTask(e: CalendarEvent) {
		tasks = tasks.map((item) => (item.id === e.id ? e : item));
		events = events.map((item) => (item.id === e.id ? e : item));
	}
	async function addQuickTask(event: SubmitEvent) {
		event.preventDefault();
		if (addingTask || !quickTitle.trim() || (!quickUnplanned && !quickDate)) return;
		addingTask = true;
		error = '';
		++loadVersion;
		loading = false;
		try {
			const created = await request<CalendarEvent>('/calendar/events', {
				method: 'POST',
				body: {
					title: quickTitle.trim(),
					start_time: quickUnplanned ? new Date().toISOString() : `${quickDate}T00:00:00`,
					end_time: quickUnplanned ? null : `${quickDate}T23:59:59`,
					is_all_day: !quickUnplanned,
					task_unplanned: quickUnplanned,
					status: 'todo',
					type: 'personal',
					project_id: Number(projectFilter) > 0 ? Number(projectFilter) : null
				}
			});
			tasks = [...tasks, created];
			events = [...events, created];
			quickTitle = '';
			quickUnplanned = false;
			undoTask = null;
			notice = '할 일을 추가했습니다.';
			taskFilter = 'all';
			query = '';
			onChanged?.();
		} catch (e) {
			error = e instanceof Error ? e.message : '할 일을 추가하지 못했습니다.';
		} finally {
			addingTask = false;
		}
	}
	let noteDirty = $state(false);
	let planningBusy=$state(false),planningFilters=$state(false);
	function addPlanningTask(){create(cursor);toggleTask(true);editorBaseline=editorSignature();}
	let mobilePane = $state<'plan' | 'schedule'>('plan');
	let availableFrom = $state(''),
		dueAt = $state('');
	const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
	function dayKey(d: Date) {
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}
	function inputDate(d: Date) {
		return `${dayKey(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
	}
	function toggleAllDay(checked: boolean) {
		if (checked) {
			allDayStart = start.slice(0, 10) || dayKey(new Date());
			const candidate = end.slice(0, 10);
			allDayEnd = candidate && candidate >= allDayStart ? candidate : allDayStart;
		} else {
			const day = allDayStart || dayKey(new Date());
			start = `${day}T09:00`;
			end = `${allDayEnd || day}T10:00`;
		}
		allDay = checked;
	}
	function toggleTaskUnplanned(checked: boolean) {
		taskUnplanned = checked;
		if (checked) allDay = false;
	}
	function toggleTask(checked: boolean) {
		task = checked;
		if (!checked) taskUnplanned = false;
		else if(!selected && editorDates.length<2){taskUnplanned=true;timeUnspecified=false;allDay=false;repeat=1;repeatMode='none';}
	}
	function firstDay(d: Date, month = false) {
		const n = new Date(d);
		if (month) n.setDate(1);
		n.setDate(n.getDate() - n.getDay());
		n.setHours(0, 0, 0, 0);
		return n;
	}
	function addDays(d: Date, n: number) {
		const x = new Date(d);
		x.setDate(x.getDate() + n);
		return x;
	}
	function categoryOf(e: CalendarEvent) {
		return (
			e.categoryName || (e.type === 'aura' ? '아우라' : e.type === 'google' ? 'Google' : '개인')
		);
	}
	function colorOf(e: CalendarEvent) {
		const c = ['#387d78', '#80669a', '#a57838', '#527da5', '#a35e70', '#687557'];
		return c[Array.from(categoryOf(e)).reduce((s, c) => s + c.charCodeAt(0), 0) % c.length];
	}
	const days = $derived(
		view === 'day'
			? [new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate())]
			: Array.from(
					{
						length:
							view === 'week'
								? 7
								: Math.ceil(
										(new Date(cursor.getFullYear(), cursor.getMonth(), 1).getDay() +
											new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0).getDate()) /
											7
									) * 7
					},
					(_, i) => addDays(firstDay(cursor, view !== 'week'), i)
				)
	);
	const categories = $derived(
		[
			...new Set(
		[...events, ...tasks]
					.flatMap(eventCategories)
					.flatMap((path) =>
						path.split(' > ').map((_, i, parts) => parts.slice(0, i + 1).join(' > '))
					)
			)
		].sort()
	);
	const visible = $derived(
		events.filter(
			(e) =>
				!e.taskUnplanned &&
				(view !== 'month' || !e.hideInMonth) &&
				!categoryHidden(e, hidden) &&
				inProject(e, projectFilter, projects) &&
				`${e.title} ${e.description} ${e.location || ''}`
					.toLowerCase()
					.includes(query.toLowerCase())
		)
	);
	const allVisibleTasks = $derived(
		tasks.filter(
			(e) =>
				!categoryHidden(e, hidden) &&
				inProject(e, projectFilter, projects) &&
				e.title.toLowerCase().includes(query.toLowerCase())
		)
	);
	const visibleTasks=$derived(allVisibleTasks.filter(e=>showCompleted||e.status!=='done'));
	const filteredTasks = $derived(visibleTasks.filter(matchesTaskDate));
	const heading = $derived(
		view === 'tasks'
			? '해야 할 일'
			: view === 'day'
				? `${cursor.getMonth() + 1}월 ${cursor.getDate()}일 ${weekdays[cursor.getDay()]}요일`
				: view === 'week'
					? `${days[0].getMonth() + 1}월 ${days[0].getDate()}일 – ${days[6].getMonth() + 1}월 ${days[6].getDate()}일`
					: `${cursor.getFullYear()}년 ${cursor.getMonth() + 1}월`
	);
	function onDay(e: CalendarEvent, d: Date) {
		const hi = addDays(d, 1),
			st = new Date(e.startTime),
			en = e.endTime ? new Date(e.endTime) : st;
		return st < hi && (en > d || +st === +d);
	}
	function time(e: CalendarEvent) {
		return e.timeUnspecified?'시간 미정':e.isAllDay
			? '종일'
			: new Date(e.startTime).toLocaleTimeString('ko-KR', {
					hour: '2-digit',
					minute: '2-digit',
					hour12: false
				});
	}
	function timeRange(e:CalendarEvent){return time(e)+(e.endTime && !e.isAllDay && !e.timeUnspecified?'–'+new Date(e.endTime).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}):'');}
	function toggleCategory(c: string) {
		hidden = hidden.includes(c) ? hidden.filter((x) => x !== c) : [...hidden, c];
		localStorage.setItem('ondo.hidden', JSON.stringify(hidden));
	}
	function timedEvents(day: Date) {
		const windowStart = +day + 8 * 3600000;
		const windowEnd = +day + 26 * 3600000;
		const items = visible
			.filter(
				(e) =>
					!e.isAllDay &&
					+new Date(e.startTime) < windowEnd &&
					+(e.endTime ? new Date(e.endTime) : new Date(+new Date(e.startTime) + 3600000)) >
						windowStart
			)
			.map((event) => ({
				event,
				from: Math.max(+new Date(event.startTime), windowStart),
				until: Math.min(
					event.endTime ? +new Date(event.endTime) : +new Date(event.startTime) + 3600000,
					windowEnd
				),
				lane: 0,
				columns: 1
			}))
			.sort((a, b) => a.from - b.from || b.until - a.until);
		let group: typeof items = [];
		let lanes: number[] = [];
		let groupEnd = 0;
		const finish = () => {
			for (const item of group) item.columns = lanes.length;
		};
		for (const item of items) {
			if (item.from >= groupEnd) {
				finish();
				group = [];
				lanes = [];
				groupEnd = 0;
			}
			let lane = lanes.findIndex((end) => end <= item.from);
			if (lane < 0) lane = lanes.length;
			item.lane = lane;
			const visualEnd = Math.max(item.until, item.from + (26 / 64) * 3600000);
			lanes[lane] = visualEnd;
			groupEnd = Math.max(groupEnd, visualEnd);
			group.push(item);
		}
		finish();
		return items;
	}
	async function load() {
		if (pendingTasks.length || addingTask) return;
		const version = ++loadVersion;
		loading = true;
		error = '';
		try {
			const from = firstDay(cursor, true),
				to = addDays(from, 43);
			const result = await Promise.all([
				personalApi.events(from.toISOString(), to.toISOString()),
				request<CalendarEvent[]>('/calendar/tasks'),
				request<Project[]>('/calendar/projects')
			]);
			if (version !== loadVersion) return;
			[events, tasks, projects] = result;
		} catch (e) {
			if (version === loadVersion)
				error = e instanceof Error ? e.message : '일정을 불러오지 못했습니다.';
		} finally {
			if (version === loadVersion) loading = false;
		}
	}
	function move(n: number) {
		const d = new Date(cursor);
		if(planningBusy)return;
		if (noteDirty && !confirm('저장하지 않은 메모가 있습니다. 이동할까요?')) return;
		if (view === 'day') d.setDate(d.getDate() + n);
		else if (view === 'week') d.setDate(d.getDate() + n * 7);
		else {
			d.setDate(1);
			d.setMonth(d.getMonth() + n);
		}
		cursor = d;
		void load();
	}
	function isZoomLink(value: string) {
		try {
			const u = new URL(value);
			return (
				u.protocol === 'https:' &&
				!u.username &&
				!u.password &&
				/(^|\.)zoom\.(us|com)$/.test(u.hostname)
			);
		} catch {
			return false;
		}
	}

	function create(date = new Date(), hour = 9, minutes = 0, durationMinutes = 60) {
		const d = new Date(date);
		d.setHours(hour, minutes, 0, 0);
		if (aura && onCreate) {
			onCreate(d, new Date(+d + durationMinutes * 60000));
			return;
		}
		selected = null;
		timeUnspecified=false;repeatMode='none';repeatEnd='count';editorDates=[];
		availableFrom = dueAt = '';
		title = '';
		description = '';
		start = inputDate(d);
		end = inputDate(new Date(+d + durationMinutes * 60000));
		allDayStart = allDayEnd = dayKey(d);
		allDay = false;
		task = view === 'tasks';
		taskUnplanned = task;
		taskDone = false;
		category = '';
		locationText = '';
		webUrl = '';
		zoomMode = false;
		project = projectFilter === 'all' ? '' : projectFilter;
		repeat = 1;
		intervalWeeks = 1;
		repeatUntil = '';
		scope = 'this';
		editorError = '';
		exportOpen = false;
		editorBaseline=editorSignature();
		showEditor = true;
	}
	function beginSlot(day: Date, slot: number) {
		dragStart = { day, slot };
		dragEnd = { day, slot };
	}
	function extendSlot(day: Date, slot: number) {
		if (dragStart?.day !== day) return;
		dragEnd = { day, slot };
	}
	function finishSlot() {
		if (!dragStart || !dragEnd) return;
		const first = Math.min(dragStart.slot, dragEnd.slot);
		const last = Math.max(dragStart.slot, dragEnd.slot);
		const date = dragStart.day;
		dragStart = null;
		dragEnd = null;
		create(date, 8 + Math.floor(first / 2), (first % 2) * 30, (last - first + 1) * 30);
	}
	function slotSelected(day: Date, slot: number) {
		if (!dragStart || !dragEnd || dragStart.day !== day) return false;
		return (
			slot >= Math.min(dragStart.slot, dragEnd.slot) &&
			slot <= Math.max(dragStart.slot, dragEnd.slot)
		);
	}
	function edit(e: CalendarEvent) {
		selected = e;
		timeUnspecified=!!e.timeUnspecified;editorDates=[];
		availableFrom = e.taskAvailableFrom ? inputDate(new Date(e.taskAvailableFrom)) : '';
		dueAt = e.taskDueAt ? inputDate(new Date(e.taskDueAt)) : '';
		title = e.title;
		description = e.description;
		start = inputDate(new Date(e.startTime));
		const startDate = new Date(e.startTime);
		const endDate = e.endTime ? new Date(e.endTime) : new Date(+startDate + 3600000);
		allDay = e.isAllDay;
		taskUnplanned = Boolean(e.taskUnplanned);
		allDayStart = dayKey(startDate);
		const legacyExclusiveEnd = e.isAllDay && endDate.getHours() === 0 && endDate.getMinutes() === 0 && endDate > startDate;
		allDayEnd = dayKey(legacyExclusiveEnd ? addDays(endDate, -1) : endDate);
		end = inputDate(endDate);
		taskDone = e.status === 'done';
		task = e.status !== 'passive';
		category = e.categoryName || '';
		locationText = e.location || '';
		webUrl = e.webUrl || '';
		zoomMode = isZoomLink(webUrl);
		project = e.projectId ? String(e.projectId) : '';
		scope = 'this';
		repeat = 1;
		editorError = '';
		exportOpen = false;
		editorBaseline=editorSignature();
		showEditor = true;
	}
	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		editorError = '';
		try {
			let a: Date, b: Date | null;
			if (task && taskUnplanned) {
				a = new Date();
				b = null;
			} else if (allDay || timeUnspecified) {
				if (!allDayStart || !allDayEnd || allDayEnd < allDayStart)
					throw new Error('종일 일정의 시작일과 종료일을 확인해주세요.');
				a = new Date(`${allDayStart}T00:00:00`);
				b = new Date(`${allDayEnd}T23:59:59`);
			} else {
				a = new Date(start);
				b = new Date(end);
			}
			if (zoomMode && !isZoomLink(webUrl.trim()))
				throw new Error('https://로 시작하는 Zoom 회의 링크를 입력해주세요.');
			if (webUrl.trim() && !safeEventUrl(webUrl.trim()))
				throw new Error('웹페이지는 https:// 주소 또는 /로 시작하는 앱 경로를 입력해주세요.');
			if (!title.trim() || isNaN(+a) || (!(task && taskUnplanned) && (!b || isNaN(+b) || b <= a)))
				throw new Error('제목과 시작·종료 시간을 확인해주세요.');
			const body:Record<string,unknown> = {
				task_available_from: task && !taskUnplanned && availableFrom ? new Date(availableFrom).toISOString() : null,
				task_due_at: task && !taskUnplanned && dueAt ? new Date(dueAt).toISOString() : null,
				title: title.trim(),
				description,
				start_time: task && taskUnplanned ? a.toISOString() : (allDay || timeUnspecified) ? `${allDayStart}T00:00:00` : a.toISOString(),
				end_time: task && taskUnplanned ? null : (allDay || timeUnspecified) ? `${allDayEnd}T23:59:59` : b!.toISOString(),
				is_all_day: (allDay || timeUnspecified) && !(task && taskUnplanned),
				time_unspecified: timeUnspecified && !(task && taskUnplanned),
				task_unplanned: task && taskUnplanned,
				status: task ? (taskDone ? 'done' : 'todo') : 'passive',
				type: 'personal',
				category_name: categoryPaths(category).join(', ') || null,
				location: locationText,
				web_url: webUrl.trim(),
				project_id: project ? Number(project) : null
			};
			if(selected){
				if(body.status===selected.status)delete body.status;
				for(const [key,old] of [['task_available_from',selected.taskAvailableFrom],['task_due_at',selected.taskDueAt]] as const){
					const next=body[key];if((old?Date.parse(old):null)===(next?Date.parse(String(next)):null))delete body[key];
				}
				await personalApi.updateEventScope(selected.id,{...body,scope});
			}
			else if (repeat > 1 || editorDates.length>1)
				await personalApi.createEventSeries({
					...body,
					repeat_count: editorDates.length>1?editorDates.length:repeat,
					repeat_unit: repeatMode==='none'?'week':repeatMode,
					repeat_interval: intervalWeeks,
					...(editorDates.length>1?{selected_dates:editorDates}:{}),
					interval_weeks: intervalWeeks,
					...(repeatEnd==='date' && repeatUntil && editorDates.length<2
						? { repeat_until: new Date(repeatUntil + 'T23:59:59').toISOString() }
						: {})
				});
			else await request('/calendar/events', { method: 'POST', body });
			showEditor = false;selectedDates=[];selectingDates=false;
			await load();
			onChanged?.();
		} catch (e) {
			editorError = e instanceof Error ? e.message : '저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}
	function repeatEndFromCount(){
		const value=(allDay || timeUnspecified)?allDayStart:start;
		if(!value || !Number.isFinite(repeat) || !Number.isFinite(intervalWeeks))return;
		repeatUntil=dayKey(occurrence(new Date(value),Math.max(1,repeat)-1,Math.max(1,intervalWeeks),repeatMode==='none'?'week':repeatMode));
	}
	function repeatCountFromEnd(){
		const value=(allDay || timeUnspecified)?allDayStart:start;
		if(!value || !repeatUntil)return;
		repeat=Math.max(2,repeatCount(new Date(value),new Date(repeatUntil+'T23:59:59'),Math.max(1,intervalWeeks),repeatMode==='none'?'week':repeatMode));
	}
	async function remove() {
		if (
			!selected ||
			!confirm(
				selected.type === 'aura'
					? '클리닉 일정과 연결된 리포트도 삭제됩니다. 삭제할까요?'
					: '이 일정을 삭제할까요?'
			)
		)
			return;
		saving = true;
		editorError = '';
		try {
			await personalApi.deleteEventScope(selected.id, scope);
			showEditor = false;
			await load();
			onChanged?.();
		} catch (e) {
			editorError = e instanceof Error ? e.message : '삭제하지 못했습니다.';
		} finally {
			saving = false;
		}
	}
	async function complete(e: CalendarEvent) {
		if (
			pendingTasks.includes(e.id) ||
			e.completionSource === 'external' ||
			e.canEdit === false ||
			taskWaiting(e)
		)
			return;
		++loadVersion;
		loading = false;
		error = '';
		pendingTasks = [...pendingTasks, e.id];
		replaceTask({ ...e, status: e.status === 'done' ? 'todo' : 'done' });
		try {
			const updated = await personalApi.updateEvent(e.id, {
				status: e.status === 'done' ? 'todo' : 'done'
			});
			replaceTask(updated);
			undoTask = updated.status === 'done' ? updated : null;
			notice = updated.status === 'done' ? `${e.title} 완료` : `${e.title} 완료를 취소했습니다.`;
			onChanged?.();
		} catch (reason) {
			replaceTask(e);
			error = reason instanceof Error ? reason.message : '완료 상태를 저장하지 못했습니다.';
		} finally {
			pendingTasks = pendingTasks.filter((id) => id !== e.id);
		}
	}

	async function loadExports() {
		saving = true;
		editorError = '';
		try {
			const accounts = await request<{ id: number; email: string }[]>('/google/accounts');
			exportTargets = [];
			for (const account of accounts) {
				const cals = await request<{ calendar_id: string; name: string; writable: number }[]>(
					`/google/accounts/${account.id}/calendars`
				);
				exportTargets = [
					...exportTargets,
					...cals
						.filter((c) => c.writable)
						.map((c) => ({
							id: account.id,
							calendarId: c.calendar_id,
							label: `${account.email} · ${c.name}`
						}))
				];
			}
			exportTarget = '';
			exportOpen = true;
		} catch (e) {
			editorError = e instanceof Error ? e.message : '캘린더를 불러오지 못했습니다.';
		} finally {
			saving = false;
		}
	}
	async function sendGoogle() {
		const target = exportTargets[Number(exportTarget)];
		if (!selected || !target) return;
		saving = true;
		try {
			await request(`/google/accounts/${target.id}/export`, {
				method: 'POST',
				body: { event_id: selected.id, calendar_id: target.calendarId }
			});
			notice = 'Google 캘린더와 연결했습니다. 수정 사항은 내보내기에서 다시 반영할 수 있습니다.';
			showEditor = false;
			await load();
		} catch (e) {
			editorError = e instanceof Error ? e.message : '보내지 못했습니다.';
		} finally {
			saving = false;
		}
	}
	$effect(() => {
		if (dialog) {
			if (showEditor && !dialog.open) dialog.showModal();
			else if (!showEditor && dialog.open) dialog.close();
		}
	});
	$effect(() => {
		if (mounted && refreshKey) void load();
	});
	$effect(() => {
		void cursor;
		if (view === 'week' && weekScroll) weekScroll.scrollTop = 0;
	});
	$effect(()=>{const day=dayKey(cursor);if(mounted&&view==='day'&&!aura){const url=new URL(location.href);if(url.searchParams.get('date')!==day){url.searchParams.set('date',day);replaceState(url,{});}}});
	onMount(() => {
		view = initialView;
		mounted = true;
		try {
			hidden = JSON.parse(localStorage.getItem('ondo.hidden') || '[]');
		} catch {
			hidden = [];
		}
		const params = new URL(location.href).searchParams;
		const requestedDate = params.get('date');
		if (
			requestedDate &&
			/^\d{4}-\d{2}-\d{2}$/.test(requestedDate) &&
			!Number.isNaN(+new Date(requestedDate + 'T12:00:00'))
		)
			cursor = new Date(requestedDate + 'T12:00:00');
		if (params.has('google') || params.has('google_error')) showConnections = true;
		const invite = params.get('invite');
		if (invite)
			void (async () => {
				try {
					await request('/calendar/invites/accept', { method: 'POST', body: { token: invite } });
					notice = '공유 프로젝트에 참여했습니다.';
					const u = new URL(location.href);
					u.searchParams.delete('invite');
					replaceState(u,{});
					await load();
				} catch (e) {
					error = e instanceof Error ? e.message : '초대를 수락하지 못했습니다.';
				}
			})();
		void load().then(async () => {
			if(params.get('create')==='1')create(cursor);
			const id = params.get('event');
			if (id) {
				try {
					edit(await personalApi.event(Number(id)));
				} catch (e) {
					error = e instanceof Error ? e.message : '일정을 찾지 못했습니다.';
				}
			}
		});
		const timer = window.setInterval(() => {
			if (!document.hidden && !showEditor) void load();
		}, 60000);
		const refresh = () => {
			if (!document.hidden && !showEditor) void load();
		};
		window.addEventListener('focus', refresh);
		document.addEventListener('visibilitychange', refresh);
		return () => {
			window.clearInterval(timer);
			window.removeEventListener('focus', refresh);
			document.removeEventListener('visibilitychange', refresh);
		};
	});
</script>

<section class="cw" class:planning={view==='day'&&!aura} class:has-plan-filters={!!query||!!hidden.length||projectFilter!=='all'} aria-label={aura ? '아우라 캘린더' : '내 캘린더'}>
	<header class="cw-toolbar">
		<div class="cw-date">
			<h1>{heading}</h1>
			{#if view !== 'tasks'}<button aria-label="이전 기간" disabled={planningBusy} onclick={() => move(-1)}
					><CalendarIcon name="chevron-left" size={17} /></button
				><button aria-label="다음 기간" disabled={planningBusy} onclick={() => move(1)}
					><CalendarIcon name="chevron-right" size={17} /></button
				><button
					onclick={() => {
						if(planningBusy)return;
		if (noteDirty && !confirm('저장하지 않은 메모가 있습니다. 이동할까요?')) return;
						cursor = new Date();
						void load();
					}}>오늘</button
				>{/if}
		</div>
		<div class="cw-tools">
			<div class="cw-switch">
				{#each (view==='day'&&!aura?[{id:'day',label:'일'},{id:'week',label:'주'},{id:'month',label:'월'}]:[{ id: 'day', label: '일' }, { id: 'month', label: '월' }, { id: 'week', label: '주' }, { id: 'tasks', label: '할 일' }]) as item}<button
						class:active={view === item.id}
						aria-pressed={view === item.id}
						onclick={() => {
							if(planningBusy)return;
		if (noteDirty && !confirm('저장하지 않은 메모가 있습니다. 이동할까요?')) return;
							view = item.id as View;
							showConnections = false;
						}}>{item.label}</button
					>{/each}
			</div>
			{#if view==='day'&&!aura}<button aria-expanded={planningFilters} onclick={()=>planningFilters=!planningFilters}>필터{query||hidden.length||projectFilter!=='all'?' · 적용 중':''}</button>{:else}<button
				class:active={showConnections}
				onclick={() => {
					if(planningBusy)return;
		if (noteDirty && !confirm('저장하지 않은 메모가 있습니다. 이동할까요?')) return;
					showConnections = !showConnections;
				}}>연결·공유</button
			>{/if}{#if view==='month' && !aura}<button aria-pressed={selectingDates} onclick={()=>{selectingDates=!selectingDates;selectedDates=[];}}>여러 날짜 선택</button>{/if}{#if view !== 'day'||!aura}<button disabled={planningBusy} class="cw-primary" onclick={() => create(cursor)}
					><CalendarIcon name="plus" size={16} />{aura ? '새 회차' : '일정 만들기'}</button
				>{/if}
		</div>
	</header>
	{#if error}<p role="alert" class="cw-feedback cw-error">
			{error}<button onclick={() => load()}>다시 시도</button>
		</p>{/if}
	{#if notice}<p role="status" class="cw-feedback">
			{notice}{#if undoTask}<button
					disabled={pendingTasks.includes(undoTask.id)}
					onclick={() => undoTask && complete(undoTask)}>완료 취소</button
				>{/if}<button
				aria-label="알림 닫기"
				onclick={() => {
					notice = '';
					undoTask = null;
				}}>×</button
			>
		</p>{/if}
	{#if showConnections}<CalendarConnections onchange={() => void load()} />{:else}
		{#if view!=='day'||aura||planningFilters}<div class="cw-filters-bar">
			<label class="cw-search"
				><CalendarIcon name="search" size={17} /><input
					aria-label="일정 검색"
					placeholder="일정 검색"
					bind:value={query}
				/></label
			><select aria-label="프로젝트 필터" bind:value={projectFilter}
				><option value="all">모든 프로젝트</option><option value="">내 일정</option
				>{#each projects as p}<option value={String(p.id)}>{p.name}</option>{/each}</select
			><button aria-expanded={filtersOpen} onclick={() => (filtersOpen = !filtersOpen)}
				>표시할 캘린더 {hidden.length ? `(${hidden.length}개 숨김)` : ''}</button
			><span role="status"
				>{loading
					? '불러오는 중…'
					: `${view === 'tasks' ? visibleTasks.length : visible.length}개 일정`}</span
			>
		</div>
		{/if}
		{#if view === 'day'&&aura}<label class="cw-completed-filter"
				><input type="checkbox" bind:checked={showCompleted} />완료한 할 일 표시</label
			>{/if}
		{#if filtersOpen}<div class="cw-filters">
				{#each categories as c}<label
						><input
							type="checkbox"
							checked={!hidden.includes(c)}
							onchange={() => toggleCategory(c)}
						/>{c}</label
					>{/each}<button
					onclick={() => {
						hidden = [];
						localStorage.removeItem('ondo.hidden');
					}}>모두 표시</button
				>
			</div>{/if}
		{#if view === 'month'}
			{#if selectingDates}<div class="cw-selection-bar" role="status"><span>{selectedDates.length?`${selectedDates.length}개 날짜 선택`:'일정을 만들 날짜를 눌러주세요'}</span><button disabled={!selectedDates.length} onclick={createSelected}>선택한 날짜에 일정 만들기</button><button onclick={()=>{selectingDates=false;selectedDates=[];}}>선택 취소</button></div>{/if}
			<div class="cw-month" aria-busy={loading}>
				{#each weekdays as day}<div class="cw-weekday">
						{day}
					</div>{/each}{#each days as day}{@const dayEvents = visible.filter((e) => onDay(e, day))}
					<div
						class="cw-day"
						class:chosen={selectingDates && selectedDates.includes(dayKey(day))}
						class:outside={day.getMonth() !== cursor.getMonth()}
						class:today={dayKey(day) === dayKey(new Date())}
					>
						<button
							class="cw-number"
							aria-label={`${dayKey(day)} ${selectingDates?'선택':'일정 추가'}`}
							aria-pressed={selectingDates?selectedDates.includes(dayKey(day)):undefined}
							onclick={() => chooseDate(day)}>{day.getDate()}</button
						>
						<div class="cw-events">
							{#each dayEvents.slice(0, 4) as e (e.id)}<button
									class="cw-event"
									class:done={e.status === 'done'}
									style={`--event-color:${colorOf(e)}`}
									onclick={() => edit(e)}
									><small>{e.status !== 'passive' ? '□' : time(e)}</small><span>{e.title}</span
									></button
								>{/each}
						</div>
						{#if dayEvents.length > 4}<button
								class="cw-more"
								onclick={() => {
									cursor = day;
									view = 'week';
								}}>{dayEvents.length - 4}개 더 보기</button
							>{/if}<button
							class="cw-empty-day"
							aria-label={`${dayKey(day)}에 새 일정`}
							onclick={() => chooseDate(day)}>＋</button
						>
					</div>{/each}
			</div>
		{:else if view==='day'&&!aura}
			<DayPlanner date={dayKey(cursor)} events={visible} tasks={allVisibleTasks} {pendingTasks} onedit={edit} oncomplete={complete} onbusy={value=>planningBusy=value} onrefresh={()=>void load()} onaddtask={addPlanningTask} oncreate={minute=>create(cursor,Math.floor(minute/60),minute%60,30)} />
		{:else if view === 'week' || view === 'day'}
			<div class:daily-workspace={view === 'day'} class:mobile-schedule={mobilePane === 'schedule'}>
				{#if view === 'day'}<DailyPlan
						date={dayKey(cursor)}
						tasks={visibleTasks}
						{pendingTasks}
						{projects}
						onedit={edit}
						oncomplete={complete}
						ondirty={(value) => (noteDirty = value)}
					/>{/if}
				{#if view === 'day'}<section class="day-agenda">
						{#key dayKey(cursor)}<PdfEditor
								daily={true}
								events={visible}
								date={dayKey(cursor)}
								onevent={edit}
								resourceId={`day-ink:${dayKey(cursor)}`}
								url=""
								name="하루 일정 필기"
							/>{/key}
					</section>{:else}<div class="cw-week-scroll" bind:this={weekScroll} aria-busy={loading}>
						<div
							class="cw-week"
							role="grid"
							tabindex="0"
							aria-label="08시부터 익일 02시까지 일정 시간표"
							onmouseup={finishSlot}
							onmouseleave={finishSlot}
						>
							<div class="cw-corner"></div>
							{#each days as day}<div
									class="cw-week-heading"
									class:today={dayKey(day) === dayKey(new Date())}
								>
									<button
										class="cw-date-add"
										aria-label={`${dayKey(day)} 일정 추가`}
										onclick={() => create(day)}
										><span>{weekdays[day.getDay()]}</span><strong>{day.getDate()}</strong></button
									>{#if onDate}<button class="cw-room" onclick={() => onDate?.(day)}
											>강의실 요청</button
										>{/if}
								</div>{/each}
							<div class="cw-all-day-label">종일</div>
							{#each days as day}<div class="cw-all-day">
									{#each visible.filter((e) => e.isAllDay && onDay(e, day)) as e}<button
											class="cw-event"
											style={`--event-color:${colorOf(e)}`}
											onclick={() => edit(e)}>{e.title}</button
										>{/each}
								</div>{/each}
							<div class="cw-axis">
								{#each Array.from({ length: 18 }, (_, i) => i) as hour}<span
										style={`top:${hour * 64}px`}
										>{hour >= 16 ? '익일 ' : ''}{String((hour + 8) % 24).padStart(2, '0')}:00</span
									>{/each}
							</div>
							{#each days as day}<div class="cw-column">
									{#each Array.from({ length: 36 }, (_, i) => i) as slot}<button
											class="cw-slot"
											class:selected-slot={slotSelected(day, slot)}
											aria-label={`${dayKey(day)} ${Math.floor(slot / 2) + 8}시 ${slot % 2 ? '30분' : '정각'} 일정 추가`}
											onmousedown={(event) => {
												event.preventDefault();
												beginSlot(day, slot);
											}}
											onmouseenter={() => extendSlot(day, slot)}
											onclick={(event) => {
												if (event.detail === 0)
													create(day, 8 + Math.floor(slot / 2), (slot % 2) * 30, 30);
											}}

										></button>{/each}{#each timedEvents(day) as positioned (positioned.event.id)}{@const e =
											positioned.event}{@const from = positioned.from}{@const until =
											positioned.until}<button
											class="cw-timed"
											class:done={e.status === 'done'}
											style={`--event-color:${colorOf(e)};top:${((from - +day) / 3600000 - 8) * 64}px;height:${Math.max(26, ((until - from) / 3600000) * 64)}px;left:calc(${(positioned.lane / positioned.columns) * 100}% + 3px);width:calc(${100 / positioned.columns}% - 6px)`}
											onclick={() => edit(e)}
											><strong>{e.title}</strong><small
												>{timeRange(e)}{e.location ? ` · ${e.location}` : ''}</small
											></button
										>{/each}
								</div>{/each}
						</div>
					</div>{/if}
			</div>
		{:else}<div class="cw-tasks">
				{#if !aura}<form class="cw-quick-task" onsubmit={addQuickTask}>
						<input
							aria-label="새 할 일"
							placeholder="할 일을 입력하고 Enter"
							maxlength="120"
							required
							bind:value={quickTitle}
							disabled={addingTask}
						/>
						<input
							type="date"
							aria-label="할 일 날짜"
							required
							bind:value={quickDate}
							disabled={addingTask || quickUnplanned}
						/>
						<label class="cw-undated-option"><input type="checkbox" bind:checked={quickUnplanned} disabled={addingTask} />날짜 미정</label>
						<button type="submit" disabled={addingTask || !quickTitle.trim()}
							>{addingTask ? '추가 중…' : '+ 추가'}</button
						>
					</form>{/if}
				<nav class="cw-task-filters" aria-label="할 일 날짜 필터">
					{#each [{ id: 'all', label: '전체' }, { id: 'today', label: '오늘' }, { id: 'overdue', label: '지난 할 일' }, { id: 'upcoming', label: '예정' }] as filter}
						<button
							aria-pressed={taskFilter === filter.id}
							onclick={() => (taskFilter = filter.id as typeof taskFilter)}>{filter.label}</button
						>
					{/each}
				</nav>
				<header>
					<p>
						{filteredTasks.filter((e) => e.status !== 'done').length}개 남음 · 공유 할 일도 내 완료
						여부만 바뀝니다.
					</p>
					<label><input type="checkbox" bind:checked={showCompleted} />완료한 할 일</label>
				</header>
				<label
					>보기 <select
						aria-label="할 일 보기 방식"
						bind:value={taskMode}
						onchange={() => saveTaskMode(taskMode)}
						><option value="time">시간순</option><option value="theme">테마별</option></select
					></label
				>
				{#each taskGroups(filteredTasks, projects, taskMode) as group}
					{#if group.isolated}<details>
							<summary>{group.name} · {group.tasks.length}</summary>{@render groupedTasks(
								group.tasks
							)}
						</details>
					{:else}<section aria-label={group.name}>
							<h3>{group.name}</h3>
							{@render groupedTasks(group.tasks)}
						</section>{/if}
				{:else}<p>남은 할 일이 없습니다.</p>{/each}
				{#snippet groupedTasks(items: CalendarEvent[])}
					{#each items as e (e.id)}<div class="cw-task" class:done={e.status === 'done'}>
							<input
								type="checkbox"
								aria-label={`${e.title} 완료`}
								checked={e.status === 'done'}
								disabled={pendingTasks.includes(e.id) ||
									e.completionSource === 'external' ||
									e.canEdit === false ||
									taskWaiting(e)}
								onchange={() => complete(e)}
							/><button onclick={() => edit(e)}
								><strong>{e.title}</strong><small
									>{taskWaiting(e) ? '시작 전 · ' : ''}{taskTiming(e)} · {categoryOf(e)}{e.projectId
										? ` · ${projects.find((p) => p.id === e.projectId)?.name || '공유 프로젝트'}`
										: ''}</small
								></button
							>
						</div>{:else}<div class="cw-no-tasks">
							<strong>남은 할 일이 없습니다.</strong>
							<p>새 할 일을 만들거나 표시 필터를 바꿔보세요.</p>
						</div>{/each}{/snippet}
			</div>{/if}{/if}
</section>

<svelte:window onbeforeunload={(event)=>{if(editorDirty || saving)event.preventDefault();}} />
<dialog
	class="cw-dialog"
	bind:this={dialog}
	onclose={() => (showEditor = false)}
	oncancel={(event)=>{event.preventDefault();closeEditor();}}
	aria-labelledby="event-dialog-title"
>
	<form onsubmit={save}>
		<header>
			<h2 id="event-dialog-title">{selected ? '일정 수정' : task?'새 할 일':'새 일정'}</h2>
			{#if selected}<button class="cw-danger" type="button" disabled={saving || selected.canEdit===false} onclick={remove}>삭제</button>{/if}
			<button type="button" aria-label="닫기" onclick={closeEditor}>×</button>
		</header>
		{#if selected?.googleAccount}<p class="cw-source">
				{selected.googleAccount} · {selected.googleCalendar}
		</p>{/if}{#if safeEventUrl(selected?.webUrl)}<a
				class="cw-service-link"
				href={safeEventUrl(selected?.webUrl) || '#'}
				>{isZoomLink(selected?.webUrl || '') ? 'Zoom 회의 참가 ↗' : '연결된 페이지 열기 ↗'}</a
			>{/if}{#if editorError}<p role="alert" class="cw-feedback cw-error">{editorError}</p>{/if}
		<div class="cw-editor-body"><fieldset disabled={saving || selected?.canEdit === false}>
			{#if !selected || selected.type==='personal'}<div class="cw-kind-switch" aria-label="등록 종류"><button type="button" class:active={!task} onclick={()=>toggleTask(false)}>일정</button><button type="button" class:active={task} onclick={()=>toggleTask(true)}>할 일</button></div>{/if}
			{#if editorDates.length>1}<p class="cw-selected-dates">{editorDates.join(' · ')}<br>선택한 날짜마다 같은 일정이 생겨요.</p>{/if}
			<label
				>제목<input
					class="cw-title"
					bind:value={title}
					maxlength="120"
					required
					placeholder="일정 제목"
					readonly={selected?.type === 'aura'}
				/></label
			>{#if selected?.type !== 'aura'}<div class="cw-options">
			{#if task}<label><input type="checkbox" bind:checked={taskDone} />완료</label><label><input type="checkbox" checked={taskUnplanned} onchange={(event)=>{toggleTaskUnplanned(event.currentTarget.checked);if(event.currentTarget.checked){repeatMode='none';repeat=1;timeUnspecified=false;}}} />날짜 미정</label>{/if}
			</div>{#if !(task && taskUnplanned)}<div class="cw-time-switch" aria-label="시간 지정"><button type="button" class:active={!allDay && !timeUnspecified} onclick={()=>{toggleAllDay(false);timeUnspecified=false;}}>시간 지정</button><button type="button" class:active={timeUnspecified} onclick={()=>{toggleAllDay(true);timeUnspecified=true;}}>시간 미정</button><button type="button" class:active={allDay && !timeUnspecified} onclick={()=>{toggleAllDay(true);timeUnspecified=false;}}>종일</button></div>{/if}{/if}
			{#if !(task && taskUnplanned)}<div class="cw-fields">
				{#if allDay || timeUnspecified}<label>시작일<input type="date" bind:value={allDayStart} onchange={repeatEndFromCount} required /></label><label>종료일<input type="date" bind:value={allDayEnd} min={allDayStart} required /></label>
				{:else}<label>시작<input type="datetime-local" bind:value={start} onchange={repeatEndFromCount} required /></label><label>종료<input type="datetime-local" bind:value={end} required /></label>{/if}
			</div>{/if}
			{#if task && !taskUnplanned}<div class="cw-fields">
					<label
						>시작 가능일<input
							type="datetime-local"
							bind:value={availableFrom}
							disabled={selected?.completionSource === 'external'}
						/></label
					>
					<label
						>할 일 마감<input
							type="datetime-local"
							bind:value={dueAt}
							disabled={selected?.completionSource === 'external'}
						/></label
					>
				</div>
				{#if selected?.completionSource === 'external'}<p class="cw-source">
						완료 상태와 기한은 연결된 서비스에서 동기화됩니다. 현재 {selected.status === 'done'
							? '완료'
							: '미완료'}입니다.
					</p>{/if}{/if}
			<div class="cw-fields">
				<label
					>프로젝트<select bind:value={project} disabled={Boolean(selected)}
						><option value="">내 일정</option>{#each projects as p}<option value={String(p.id)}
								>{p.name}</option
							>{/each}</select
					></label
				><label
					>카테고리<input
						list="event-categories"
						bind:value={category}
						placeholder="업무 > 프로젝트, 개인 > 공부"
						maxlength="80"
					/><datalist id="event-categories"
						>{#each categories as c}<option value={c}></option>{/each}</datalist
					></label
				>
			</div>
			<p class="cw-source">쉼표로 카테고리를 나누고, &gt; 기호로 상·하위를 구분합니다.</p>
			<label
				>장소<input
					bind:value={locationText}
					placeholder="강의실, 건물 또는 주소"
					maxlength="500"
				/></label
			><label
				>{zoomMode ? 'Zoom 회의 링크' : '웹페이지'}<input
					type="text"
					bind:value={webUrl}
					required={zoomMode}
					placeholder="https://"
					maxlength="2000"
				/></label
			>{#if zoomMode}<p class="cw-source">
					기존 Zoom 회의 링크를 일정에 저장합니다. 회의를 자동으로 생성하지는 않습니다.
				</p>{/if}{#if safeEventUrl(selected?.webUrl)}<a
					href={safeEventUrl(selected?.webUrl) || '#'}
					target="_blank"
					rel="noopener noreferrer">웹페이지 열기 ↗</a
				>{/if}<label
				>메모<textarea
					bind:value={description}
					rows="3"
					placeholder="일정에 필요한 내용을 적어두세요"
				></textarea></label
			>
			{#if !selected && !taskUnplanned && editorDates.length<2}<section class="cw-repeat-editor"><label>반복<select bind:value={repeatMode} onchange={changeRepeat}><option value="none">반복 안 함</option><option value="day">매일</option><option value="week">매주</option><option value="month">매월</option></select></label>
			{#if repeatMode!=='none'}<div class="cw-fields"><label>간격<input type="number" min="1" max="365" bind:value={intervalWeeks} oninput={repeatEndFromCount} required />{repeatMode==='day'?'일':repeatMode==='week'?'주':'개월'}마다</label><label>반복 종료<select bind:value={repeatEnd}><option value="count">횟수로 정하기</option><option value="date">날짜로 정하기</option></select></label></div>{#if repeatEnd==='count'}<label>반복 횟수<input type="number" min="2" max="365" bind:value={repeat} oninput={repeatEndFromCount} required /></label>{:else}<label>종료일<input type="date" min={(allDay?allDayStart:start).slice(0,10)} bind:value={repeatUntil} oninput={repeatCountFromEnd} required /></label>{/if}{/if}</section>{/if}{#if selected?.recurrenceGroupId}<label
					>수정·삭제 범위<select bind:value={scope}
						><option value="this">이 일정만</option>{#if selected.type==='personal'}<option value="all">전체 반복 일정</option>{/if}<option value="following"
							>이 일정과 이후 반복 일정</option
						></select
					></label
				>{/if}
		</fieldset></div>
		{#if selected?.canEdit === false}<p class="cw-source">
				읽기 전용 일정입니다. 연결된 원본 서비스에서 수정해주세요.
			</p>{/if}{#if exportOpen}<div class="cw-export">
				<select aria-label="보낼 구글 캘린더" bind:value={exportTarget}
					><option value="">보낼 캘린더 선택</option>{#each exportTargets as t, i}<option
							value={String(i)}>{t.label}</option
						>{/each}</select
				><button type="button" disabled={saving || exportTarget === ''} onclick={sendGoogle}
					>저장된 일정 보내기</button
				>{#if !exportTargets.length}<p>연결·공유에서 Google 계정을 먼저 추가해주세요.</p>{/if}
		</div>{/if}
		<footer>
			{#if selected}<button type="button" disabled={saving} onclick={loadExports}>구글로 보내기</button>{/if}<span></span><button type="button" onclick={closeEditor}>닫기</button
			>{#if selected?.canEdit !== false}<button class="cw-primary" disabled={saving}
					>{saving ? '저장 중…' : '저장'}</button
				>{/if}
		</footer>
	</form>
</dialog>
