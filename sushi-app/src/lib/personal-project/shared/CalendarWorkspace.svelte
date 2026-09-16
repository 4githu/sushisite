<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi, request } from './api';
	import type { CalendarEvent } from './types';
	import CalendarConnections from './CalendarConnections.svelte';
	import './calendar-workspace.css';
	type View = 'month' | 'week' | 'tasks';
	type Project = { id: number; name: string };
	let {
		initialView = 'month',
		aura = false,
		refreshKey = '',
		onAuraEdit,
		onCreate,
		onChanged,
		onDate
	}: {
		initialView?: View;
		aura?: boolean;
		refreshKey?: string;
		onAuraEdit?: (id: number) => void;
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
	let weekScroll = $state<HTMLDivElement>();
	let title = $state(''),
		description = $state(''),
		start = $state(''),
		end = $state(''),
		allDay = $state(false),
		task = $state(false),
		category = $state(''),
		locationText = $state(''),
		webUrl = $state(''),
		project = $state(''),
		repeat = $state(1),
		intervalWeeks = $state(1),
		repeatUntil = $state(''),
		scope = $state<'this' | 'following'>('this');
	let exportTargets = $state<{ id: number; calendarId: string; label: string }[]>([]),
		exportTarget = $state(''),
		exportOpen = $state(false);
	let loadVersion = 0;
	const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
	function dayKey(d: Date) {
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}
	function inputDate(d: Date) {
		return `${dayKey(d)}T${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
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
		const c = ['#356cbd', '#8e63b6', '#b66d32', '#29836b', '#bd536a', '#68784c'];
		return c[Array.from(categoryOf(e)).reduce((s, c) => s + c.charCodeAt(0), 0) % c.length];
	}
	const days = $derived(
		Array.from({ length: view === 'week' ? 7 : 42 }, (_, i) =>
			addDays(firstDay(cursor, view !== 'week'), i)
		)
	);
	const categories = $derived([...new Set([...events, ...tasks].map(categoryOf))].sort());
	const visible = $derived(
		events.filter(
			(e) =>
				!hidden.includes(categoryOf(e)) &&
				(projectFilter === 'all' || String(e.projectId || '') === projectFilter) &&
				`${e.title} ${e.description} ${e.location || ''}`
					.toLowerCase()
					.includes(query.toLowerCase())
		)
	);
	const visibleTasks = $derived(
		tasks.filter(
			(e) =>
				(showCompleted || e.status !== 'done') &&
				!hidden.includes(categoryOf(e)) &&
				(projectFilter === 'all' || String(e.projectId || '') === projectFilter) &&
				e.title.toLowerCase().includes(query.toLowerCase())
		)
	);
	const heading = $derived(
		view === 'tasks'
			? '해야 할 일'
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
		return e.isAllDay
			? '종일'
			: new Date(e.startTime).toLocaleTimeString('ko-KR', {
					hour: '2-digit',
					minute: '2-digit',
					hour12: false
				});
	}
	function toggleCategory(c: string) {
		hidden = hidden.includes(c) ? hidden.filter((x) => x !== c) : [...hidden, c];
		localStorage.setItem('ondo.hidden', JSON.stringify(hidden));
	}
	function timedEvents(day: Date) {
		const items = visible
			.filter((e) => !e.isAllDay && onDay(e, day))
			.map((event) => ({
				event,
				from: Math.max(+new Date(event.startTime), +day),
				until: Math.min(
					event.endTime ? +new Date(event.endTime) : +new Date(event.startTime) + 3600000,
					+addDays(day, 1)
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
		if (view === 'week') d.setDate(d.getDate() + n * 7);
		else {
			d.setDate(1);
			d.setMonth(d.getMonth() + n);
		}
		cursor = d;
		void load();
	}
	function create(date = new Date(), hour = 9, minutes = 0) {
		const d = new Date(date);
		d.setHours(hour, minutes, 0, 0);
		if (aura && onCreate) {
			onCreate(d, new Date(+d + 3600000));
			return;
		}
		selected = null;
		title = '';
		description = '';
		start = inputDate(d);
		end = inputDate(new Date(+d + 3600000));
		allDay = false;
		task = view === 'tasks';
		category = '';
		locationText = '';
		webUrl = '';
		project = projectFilter === 'all' ? '' : projectFilter;
		repeat = 1;
		intervalWeeks = 1;
		repeatUntil = '';
		scope = 'this';
		editorError = '';
		exportOpen = false;
		showEditor = true;
	}
	function edit(e: CalendarEvent) {
		selected = e;
		title = e.title;
		description = e.description;
		start = inputDate(new Date(e.startTime));
		end = e.endTime
			? inputDate(new Date(e.endTime))
			: inputDate(new Date(+new Date(e.startTime) + 3600000));
		allDay = e.isAllDay;
		task = e.status !== 'passive';
		category = e.categoryName || '';
		locationText = e.location || '';
		webUrl = e.webUrl || '';
		project = e.projectId ? String(e.projectId) : '';
		scope = 'this';
		repeat = 1;
		editorError = '';
		exportOpen = false;
		showEditor = true;
	}
	async function save(e: SubmitEvent) {
		e.preventDefault();
		saving = true;
		editorError = '';
		try {
			let a = new Date(start),
				b = new Date(end);
			if (allDay) {
				a.setHours(0, 0, 0, 0);
				b.setHours(0, 0, 0, 0);
				if (b <= a) b = addDays(a, 1);
			}
			if (!title.trim() || isNaN(+a) || isNaN(+b) || b <= a)
				throw new Error('제목과 시작·종료 시간을 확인해주세요.');
			const body = {
				title: title.trim(),
				description,
				start_time: allDay ? inputDate(a) + ':00' : a.toISOString(),
				end_time: allDay ? inputDate(b) + ':00' : b.toISOString(),
				is_all_day: allDay,
				status: task ? (selected?.status === 'done' ? 'done' : 'todo') : 'passive',
				type: 'personal',
				category_name: category.trim() || null,
				location: locationText,
				web_url: webUrl.trim(),
				project_id: project ? Number(project) : null
			};
			if (selected) await personalApi.updateEventScope(selected.id, { ...body, scope });
			else if (repeat > 1)
				await personalApi.createEventSeries({
					...body,
					repeat_count: repeat,
					interval_weeks: intervalWeeks,
					...(repeatUntil
						? { repeat_until: new Date(repeatUntil + 'T23:59:59').toISOString() }
						: {})
				});
			else await request('/calendar/events', { method: 'POST', body });
			showEditor = false;
			await load();
			onChanged?.();
		} catch (e) {
			editorError = e instanceof Error ? e.message : '저장하지 못했습니다.';
		} finally {
			saving = false;
		}
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
		try {
			await personalApi.updateEvent(e.id, { status: e.status === 'done' ? 'todo' : 'done' });
			await load();
		} catch (e) {
			error = e instanceof Error ? e.message : '완료 상태를 저장하지 못했습니다.';
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
			notice = 'Google 캘린더와 연결했습니다. 이후 수정 사항도 동기화됩니다.';
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
		if (view === 'week' && weekScroll) weekScroll.scrollTop = 7 * 64;
	});
	onMount(() => {
		view = initialView;
		mounted = true;
		try {
			hidden = JSON.parse(localStorage.getItem('ondo.hidden') || '[]');
		} catch {
			hidden = [];
		}
		const params = new URL(location.href).searchParams;
		if (params.has('google') || params.has('google_error')) showConnections = true;
		const invite = params.get('invite');
		if (invite)
			void (async () => {
				try {
					await request('/calendar/invites/accept', { method: 'POST', body: { token: invite } });
					notice = '공유 프로젝트에 참여했습니다.';
					const u = new URL(location.href);
					u.searchParams.delete('invite');
					history.replaceState(history.state, '', u);
					await load();
				} catch (e) {
					error = e instanceof Error ? e.message : '초대를 수락하지 못했습니다.';
				}
			})();
		void load().then(async () => {
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
		return () => window.clearInterval(timer);
	});
</script>

<section class="cw" aria-label={aura ? '아우라 캘린더' : '내 캘린더'}>
	<header class="cw-toolbar">
		<div class="cw-date">
			<h1>{heading}</h1>
			{#if view !== 'tasks'}<button aria-label="이전 기간" onclick={() => move(-1)}>‹</button
				><button aria-label="다음 기간" onclick={() => move(1)}>›</button><button
					onclick={() => {
						cursor = new Date();
						void load();
					}}>오늘</button
				>{/if}
		</div>
		<div class="cw-tools">
			<div class="cw-switch">
				{#each [{ id: 'month', label: '월' }, { id: 'week', label: '주' }, { id: 'tasks', label: '할 일' }] as item}<button
						class:active={view === item.id}
						onclick={() => {
							view = item.id as View;
							showConnections = false;
						}}>{item.label}</button
					>{/each}
			</div>
			<button class:active={showConnections} onclick={() => (showConnections = !showConnections)}
				>연결·공유</button
			><button class="cw-primary" onclick={() => create()}>＋ {aura ? '새 회차' : '만들기'}</button>
		</div>
	</header>
	{#if error}<p role="alert" class="cw-feedback cw-error">
			{error}<button onclick={() => load()}>다시 시도</button>
		</p>{/if}
	{#if notice}<p role="status" class="cw-feedback">
			{notice}<button aria-label="알림 닫기" onclick={() => (notice = '')}>×</button>
		</p>{/if}
	{#if showConnections}<CalendarConnections onchange={() => void load()} />{:else}
		<div class="cw-filters-bar">
			<input aria-label="일정 검색" placeholder="일정 검색" bind:value={query} /><select
				aria-label="프로젝트 필터"
				bind:value={projectFilter}
				><option value="all">모든 프로젝트</option><option value="">내 일정</option
				>{#each projects as p}<option value={String(p.id)}>{p.name}</option>{/each}</select
			><button onclick={() => (filtersOpen = !filtersOpen)}
				>표시할 캘린더 {hidden.length ? `(${hidden.length}개 숨김)` : ''}</button
			><span role="status"
				>{loading
					? '불러오는 중…'
					: `${view === 'tasks' ? visibleTasks.length : visible.length}개 일정`}</span
			>
		</div>
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
			<div class="cw-month" aria-busy={loading}>
				{#each weekdays as day}<div class="cw-weekday">
						{day}
					</div>{/each}{#each days as day}{@const dayEvents = visible.filter((e) => onDay(e, day))}
					<div
						class="cw-day"
						class:outside={day.getMonth() !== cursor.getMonth()}
						class:today={dayKey(day) === dayKey(new Date())}
					>
						<button
							class="cw-number"
							aria-label={`${dayKey(day)} 일정 추가`}
							onclick={() => create(day)}>{day.getDate()}</button
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
							onclick={() => create(day)}>＋</button
						>
					</div>{/each}
			</div>
		{:else if view === 'week'}
			<div class="cw-week-scroll" bind:this={weekScroll} aria-busy={loading}>
				<div class="cw-week">
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
							>{#if onDate}<button class="cw-room" onclick={() => onDate?.(day)}>강의실 요청</button
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
						{#each Array.from({ length: 24 }, (_, i) => i) as hour}<span
								style={`top:${hour * 64}px`}>{String(hour).padStart(2, '0')}:00</span
							>{/each}
					</div>
					{#each days as day}<div class="cw-column">
							{#each Array.from({ length: 48 }, (_, i) => i) as slot}<button
									class="cw-slot"
									aria-label={`${dayKey(day)} ${Math.floor(slot / 2)}시 ${slot % 2 ? '30분' : '정각'} 일정 추가`}
									onclick={() => create(day, Math.floor(slot / 2), (slot % 2) * 30)}

								></button>{/each}{#each timedEvents(day) as positioned (positioned.event.id)}{@const e =
									positioned.event}{@const from = positioned.from}{@const until =
									positioned.until}<button
									class="cw-timed"
									style={`--event-color:${colorOf(e)};top:${((from - +day) / 3600000) * 64}px;height:${Math.max(26, ((until - from) / 3600000) * 64)}px;left:calc(${(positioned.lane / positioned.columns) * 100}% + 3px);width:calc(${100 / positioned.columns}% - 6px)`}
									onclick={() => edit(e)}
									><strong>{e.title}</strong><small
										>{time(e)}{e.location ? ` · ${e.location}` : ''}</small
									></button
								>{/each}
						</div>{/each}
				</div>
			</div>
		{:else}<div class="cw-tasks">
				<header>
					<p>공유 할 일도 내 완료 여부만 바뀝니다.</p>
					<label><input type="checkbox" bind:checked={showCompleted} />완료한 할 일</label>
				</header>
				{#each visibleTasks as e (e.id)}<div class="cw-task" class:done={e.status === 'done'}>
						<input
							type="checkbox"
							aria-label={`${e.title} 완료`}
							checked={e.status === 'done'}
							onchange={() => complete(e)}
						/><button onclick={() => edit(e)}
							><strong>{e.title}</strong><small
								>{new Date(e.startTime).toLocaleDateString('ko-KR')} · {categoryOf(e)}{e.projectId
									? ` · ${projects.find((p) => p.id === e.projectId)?.name || '공유 프로젝트'}`
									: ''}</small
							></button
						>
					</div>{:else}<div class="cw-no-tasks">
						<strong>남은 할 일이 없습니다.</strong>
						<p>새 할 일을 만들거나 표시 필터를 바꿔보세요.</p>
					</div>{/each}
			</div>{/if}{/if}
</section>

<dialog
	class="cw-dialog"
	bind:this={dialog}
	onclose={() => (showEditor = false)}
	oncancel={() => (showEditor = false)}
	aria-labelledby="event-dialog-title"
>
	<form onsubmit={save}>
		<header>
			<h2 id="event-dialog-title">{selected ? '일정 상세' : '새 일정'}</h2>
			<button type="button" aria-label="닫기" onclick={() => (showEditor = false)}>×</button>
		</header>
		{#if selected?.googleAccount}<p class="cw-source">
				{selected.googleAccount} · {selected.googleCalendar}
			</p>{/if}{#if selected?.type === 'aura'}<p class="cw-source">
				시간 변경은 아우라 클리닉에도 반영됩니다.
			</p>{/if}{#if editorError}<p role="alert" class="cw-feedback cw-error">{editorError}</p>{/if}
		<fieldset disabled={saving || selected?.canEdit === false}>
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
					<label><input type="checkbox" bind:checked={task} />할 일로 등록</label><label
						><input type="checkbox" bind:checked={allDay} />종일</label
					>
				</div>{/if}
			<div class="cw-fields">
				<label>시작<input type="datetime-local" bind:value={start} required /></label><label
					>종료<input type="datetime-local" bind:value={end} required /></label
				>
			</div>
			{#if allDay}<p class="cw-source">종료 날짜는 일정이 끝난 다음 날입니다.</p>{/if}
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
						placeholder="예: 수업, 개인, 동아리"
						maxlength="80"
					/><datalist id="event-categories"
						>{#each categories as c}<option value={c}></option>{/each}</datalist
					></label
				>
			</div>
			<label
				>장소<input
					bind:value={locationText}
					placeholder="강의실, 건물 또는 주소"
					maxlength="500"
				/></label
			><label
				>웹페이지<input
					type="url"
					bind:value={webUrl}
					placeholder="https://"
					maxlength="2000"
				/></label
			>{#if selected?.webUrl && /^https?:\/\//.test(selected.webUrl)}<a
					href={selected.webUrl}
					target="_blank"
					rel="noopener noreferrer">웹페이지 열기 ↗</a
				>{/if}<label
				>메모<textarea
					bind:value={description}
					rows="3"
					placeholder="일정에 필요한 내용을 적어두세요"
				></textarea></label
			>{#if !selected}<label
					>반복<select bind:value={repeat}
						><option value={1}>반복 안 함</option>{#each [2, 4, 8, 12, 16, 24, 52] as n}<option
								value={n}>{n}회</option
							>{/each}</select
					></label
				>{#if repeat > 1}<div class="cw-fields">
						<label
							>반복 간격 (주)<input
								type="number"
								min="1"
								max="52"
								bind:value={intervalWeeks}
								required
							/></label
						><label>반복 종료일 (선택)<input type="date" bind:value={repeatUntil} /></label>
					</div>{/if}{/if}{#if selected?.recurrenceGroupId}<label
					>수정·삭제 범위<select bind:value={scope}
						><option value="this">이 일정만</option><option value="following"
							>이 일정과 이후 반복 일정</option
						></select
					></label
				>{/if}
		</fieldset>
		{#if selected?.canEdit === false}<p class="cw-source">
				읽기 전용 캘린더입니다. 원본 Google 캘린더에서 수정해주세요.
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
			{#if selected?.type === 'aura' && onAuraEdit}<button
					type="button"
					onclick={() => {
						if (selected) {
							showEditor = false;
							onAuraEdit?.(selected.id);
						}
					}}>클리닉 상세 수정</button
				>{/if}
			{#if selected}<button
					class="cw-danger"
					type="button"
					disabled={saving || selected.canEdit === false}
					onclick={remove}>삭제</button
				><button type="button" disabled={saving} onclick={loadExports}>구글로 보내기</button
				>{/if}<span></span><button type="button" onclick={() => (showEditor = false)}>닫기</button
			>{#if selected?.canEdit !== false}<button class="cw-primary" disabled={saving}
					>{saving ? '저장 중…' : '저장'}</button
				>{/if}
		</footer>
	</form>
</dialog>
