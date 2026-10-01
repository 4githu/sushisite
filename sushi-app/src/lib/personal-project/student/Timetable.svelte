<script lang="ts">
	import { onMount, onDestroy, untrack } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { request } from '$lib/personal-project/shared/api';


	import TimetableGrid from '$lib/personal-project/student/TimetableGrid.svelte';
	import {
		courseLessons,
		overlaps,
		times,
		days,
		termDates,
		academicSlot,
		type Course,
		type Catalog,
		type Draft,
		type Lesson
	} from '$lib/personal-project/student/catalog';
	import '$lib/personal-project/student/student.css';
	import CourseTrend from './CourseTrend.svelte';
	import { CourseSearch } from './search';
	let { exploration = false }: { exploration?: boolean } = $props();
	let searchMs = $state(0);
	let engine: CourseSearch;
	let admissionYear = $state<number | null>(null),
		academicOffset = $state(0);
	let creditsFilter = $state(''),
		after = $state(''),
		before = $state(''),
		emptyOnly = $state(false),
		history = $state<{ term: string; courses: Course[] }[]>([]),
		detail = $state<Course | null>(null);
	let alternatives = $state<{ slot: string; courses: number }[]>([]);
	let slot = $state('');
	const slots = Array.from({ length: 12 }, (_, i) => `${Math.floor(i / 2) + 1}-${(i % 2) + 1}`);

	let catalog = $state<Catalog | null>(null),
		term = $state(''),
		q = $state(''),
		department = $state(''),
		classification = $state(''),
		day = $state('');
	let courses = $state<Course[]>([]),
		selected = $state<Course[]>([]),
		manual = $state<Lesson[]>([]),
		departments = $state<string[]>([]),
		classifications = $state<string[]>([]),
		total = $state(0),
		offset = $state(0);
	let loading = $state(true),
		searching = $state(false),
		busy = $state(false),
		error = $state(''),
		notice = $state(''),
		saved = $state(''),
		revision = $state(0);
	let starts = $state(''),
		ends = $state(''),
		exclusions = $state(''),
		skip = $state(true),
		initialized = $state(false),
		school = $state('서울대학교');
	let manualTitle = $state(''),
		manualDay = $state(0),
		manualStart = $state('09:00'),
		manualEnd = $state('10:30'),
		manualRoom = $state('');
	let preview = $state<{
			events: { title: string; startTime: string; endTime: string }[];
			skipped: { date: string; title: string; reason: string }[];
		} | null>(null),
		previewKey = $state('');
	let searchVersion = 0,
		loadVersion = 0;
	onDestroy(() => engine?.destroy());

	$effect(() => {
		const value = snapshot;
		if (initialized && !loading && value !== saved && !busy && !error) {
			const timer = setTimeout(() => void run(save), 500);
			return () => clearTimeout(timer);
		}
	});
	$effect(() => {
		q;
		department;
		classification;
		day;
		creditsFilter;
		after;
		before;
		emptyOnly;
		if (initialized) {
			const timer = setTimeout(() => void untrack(() => search()), 100);
			return () => clearTimeout(timer);
		}
	});
	async function showDetail(course: Course) {
		detail = course;
		history = [];
		try {
			history = await request(`/student/course-history/${encodeURIComponent(course.sbjt_cd)}`);
		} catch (e) {
			error = String(e);
		}
	}
	const lessons = $derived([...selected.flatMap(courseLessons), ...manual]);
	const snapshot = $derived(
		JSON.stringify({
			course_ids: selected.map((c) => c.id),
			manual_lessons: manual,
			starts_on: starts,
			ends_on: ends,
			skip_holidays: skip,
			excluded_dates: exclusions.split(/[,\s]+/).filter(Boolean)
		})
	);
	const dirty = $derived(initialized && snapshot !== saved);
	const termInfo = $derived(catalog?.terms.find((t) => t.id === term));
	const academicLabel = $derived(
		termInfo ? academicSlot(termInfo, admissionYear, academicOffset) : ''
	);
	const payload = $derived({
		name: `${slot ? slot + ' · ' : ''}${termInfo?.label || '내 시간표'}`,
		starts_on: starts,
		ends_on: ends,
		skip_holidays: skip,
		excluded_dates: exclusions.split(/[,\s]+/).filter(Boolean),
		lessons
	});
	const missing = $derived(
		selected.filter((c) => courseLessons(c).length !== c.slots.length || !c.slots.length)
	);
	const credits = $derived(selected.reduce((sum, c) => sum + c.credits, 0));
	beforeNavigate(({ cancel }) => {
		if (dirty && !confirm('저장하지 않은 시간표가 있습니다. 이동할까요?')) cancel();
	});
	async function run(fn: () => Promise<void>) {
		if (busy) return;
		busy = true;
		error = '';
		notice = '';
		try {
			await fn();
		} catch (e) {
			error = e instanceof Error ? e.message : '요청을 완료하지 못했습니다.';
		} finally {
			busy = false;
		}
	}
	async function search(reset = true) {
		const current = ++searchVersion;
		searching = true;
		if (reset) offset = 0;
		const url = new URL(location.href);
		for (const [key, value] of Object.entries({
			q,
			department,
			classification,
			day,
			credits: creditsFilter,
			after,
			before,
			empty: emptyOnly ? '1' : ''
		})) {
			if (value) url.searchParams.set(key, value);
			else url.searchParams.delete(key);
		}
		window.history.replaceState(window.history.state, '', url);
		error = '';
		try {
			const began = performance.now();
			const result = await engine.send({
				type: 'search',
				q,
				department,
				classification,
				day,
				credits: creditsFilter,
				after,
				before,
				emptyOnly,
				lessons,
				offset
			});
			if (current !== searchVersion) return;
			searchMs = performance.now() - began;
			courses = reset ? result.courses : [...courses, ...result.courses];
			total = result.total;
			departments = result.departments;
			classifications = result.classifications;
		} catch (e) {
			if (current === searchVersion) error = e instanceof Error ? e.message : '강의 검색 실패';
		} finally {
			if (current === searchVersion) searching = false;
		}
	}
	async function loadTerm(next: string, nextSlot = slot) {
		const generation = ++loadVersion;
		loading = true;
		initialized = false;
		preview = null;
		error = '';
		try {
			const [data] = await Promise.all([
				request<{
					draft: Draft | null;
					courses: Course[];
					alternatives: { slot: string; courses: number }[];
				}>(
					`/student/timetable/draft?term=${encodeURIComponent(next)}&slot=${encodeURIComponent(nextSlot)}`
				),
				engine.load(next, catalog!.revision)
			]);
			if (generation !== loadVersion) return;
			const info = catalog!.terms.find((t) => t.id === next)!;
			term = next;
			slot = nextSlot;
			const url = new URL(location.href);
			url.searchParams.set('term', term);
			if (slot) url.searchParams.set('slot', slot);
			else url.searchParams.delete('slot');
			window.history.replaceState(window.history.state, '', url);
			const dates = termDates(info);
			selected = data.courses;
			alternatives = data.alternatives || [];
			manual = data.draft?.manual_lessons || [];
			starts = data.draft?.starts_on || dates.starts_on;
			ends = data.draft?.ends_on || dates.ends_on;
			skip = data.draft?.skip_holidays ?? true;
			exclusions = data.draft?.excluded_dates.join(', ') || '';
			revision = data.draft?.revision || 0;
			saved = JSON.stringify({
				course_ids: selected.map((c) => c.id),
				manual_lessons: manual,
				starts_on: starts,
				ends_on: ends,
				skip_holidays: skip,
				excluded_dates: exclusions.split(/[,\s]+/).filter(Boolean)
			});
			initialized = true;
			const params = new URLSearchParams(location.search);
			q = params.get('q') || '';
			department = params.get('department') || '';
			classification = params.get('classification') || '';
			day = params.get('day') || '';
			creditsFilter = params.get('credits') || '';
			after = params.get('after') || '';
			before = params.get('before') || '';
			emptyOnly = params.get('empty') === '1';
			await search();
		} catch (e) {
			error = e instanceof Error ? e.message : '시간표 불러오기 실패';
		} finally {
			if (generation === loadVersion) loading = false;
		}
	}
	onMount(async () => {
		try {
			engine = new CourseSearch();
			const [data, profile] = await Promise.all([
				request<Catalog>('/student/catalog'),
				request<{ school: string; admission_year: number | null; academic_offset: number }>(
					'/student/profile'
				)
			]);
			catalog = data;
			admissionYear = profile.admission_year;
			academicOffset = profile.academic_offset || 0;
			school = profile.school || '서울대학교';
			const available = data.terms
				.filter((t) => termDates(t).starts_on <= new Date().toISOString().slice(0, 10))
				.sort((a, b) => termDates(b).starts_on.localeCompare(termDates(a).starts_on));
			const params = new URLSearchParams(location.search),
				chosenTerm = params.get('term'),
				chosenSlot = params.get('slot') || '';

			await loadTerm(
				data.terms.some((t) => t.id === chosenTerm)
					? chosenTerm!
					: (available[0] || data.terms[0]).id,
				exploration
					? chosenSlot.startsWith('explore-') || slots.includes(chosenSlot)
						? chosenSlot
						: 'explore-1'
					: ''
			);
		} catch (e) {
			error = e instanceof Error ? e.message : '불러오기 실패';
			loading = false;
		}
	});
	function conflict(items: Lesson[]) {
		return items.some((a) => lessons.some((b) => overlaps(a, b)));
	}
	function add(course: Course) {
		notice = '';
		error = '';
		if (selected.some((c) => c.id === course.id)) return;
		if (selected.length >= 60) {
			error = '강의는 최대 60개까지 담을 수 있습니다.';
			return;
		}
		if (conflict(courseLessons(course))) {
			error = '이미 담은 수업과 시간이 겹칩니다. 기존 수업을 빼고 다시 담아주세요.';
			return;
		}
		selected = [...selected, course];
	}
	async function save() {
		const input = snapshot;
		const result = await request<{ revision: number }>(
			`/student/timetable/draft?term=${encodeURIComponent(term)}&slot=${encodeURIComponent(slot)}`,
			{ method: 'PUT', body: { ...JSON.parse(input), revision, sync_calendar: !exploration } }
		);
		saved = input;
		revision = result.revision;
		notice = exploration ? '탐색 초안을 저장했습니다.' : '저장됨 · 캘린더 자동 반영 완료';
	}
	function addManual() {
		error = '';
		const lesson = {
			title: manualTitle.trim(),
			weekday: manualDay,
			start: manualStart,
			end: manualEnd,
			location: manualRoom
		};
		if (!lesson.title || lesson.start >= lesson.end) {
			error = '수업명과 시작·종료 시간을 확인해주세요.';
			return;
		}
		if (conflict([lesson])) {
			error = '이미 담은 수업과 시간이 겹칩니다.';
			return;
		}
		manual = [...manual, lesson];
		manualTitle = manualRoom = '';
	}
	async function previewImport() {
		const key = JSON.stringify(payload);
		preview = await request('/student/timetable/preview', {
			method: 'POST',
			body: JSON.parse(key)
		});
		previewKey = key;
	}
	function exportFile() {
		const blob = new Blob(
			[JSON.stringify({ format: 'netaq-timetable-v1', term, ...JSON.parse(snapshot) }, null, 2)],
			{ type: 'application/json' }
		);
		const url = URL.createObjectURL(blob),
			a = document.createElement('a');
		a.href = url;
		a.download = `시간표-${term}.json`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(url), 1000);
	}
	async function importFile(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		await run(async () => {
			if (file.size > 200000) throw Error('200KB 이하의 시간표 파일을 선택해주세요.');
			const data = JSON.parse(await file.text());
			if (data.format !== 'netaq-timetable-v1' || data.term !== term)
				throw Error('같은 학기의 NETAQ 시간표 내보내기 파일을 선택해주세요.');
			if (dirty && !confirm('작성 중인 시간표를 파일 내용으로 바꿀까요?')) return;
			await request(
				`/student/timetable/draft?term=${encodeURIComponent(term)}&slot=${encodeURIComponent(slot)}`,
				{
					method: 'PUT',
					body: { ...data, revision, sync_calendar: !exploration }
				}
			);
			await loadTerm(term);
			notice = '파일의 시간표를 가져왔습니다.';
		});
	}
</script>

<svelte:head><title>수업 시간표 · NETAQ</title></svelte:head>
<svelte:window
	onbeforeunload={(e) => {
		if (dirty) e.preventDefault();
	}}
/>
<div class="student-page">
	<header class="page-heading">
		<div>
			<span class="eyebrow">CAMPUS / TIMETABLE</span>
			<h1>{exploration ? '강의 탐색' : '내 시간표'}</h1>
			<p class="muted">
				{exploration
					? '후보 시간표를 비교하고 내 시간표로 선택하세요.'
					: '담거나 뺀 수업은 캘린더에 자동으로 반영됩니다.'}
			</p>
		</div>
		<div class="fields">
			{#if alternatives.length}<p>
					이전 시간표를 탐색 초안으로 보존했습니다. {#each alternatives as a}<a
							href={`/personal-project/calendar/student/plan/explore?term=${encodeURIComponent(term)}&slot=${a.slot}`}
							>{a.slot.replace('explore-legacy-', '')} · {a.courses}과목</a
						>
					{/each}
				</p>{/if}
			{#if exploration}<label
					>비교할 시간표<select
						value={slot}
						disabled={busy || loading}
						onchange={async (e) => {
							if (dirty) await run(save);
							if (dirty) return;
							await loadTerm(term, e.currentTarget.value);
						}}
						>{#each [1, 2, 3] as n}<option value={`explore-${n}`}>후보 {n}</option
							>{/each}{#if slot && !/^explore-[123]$/.test(slot)}<option value={slot}
								>기존 {slot}</option
							>{/if}</select
					></label
				>{:else if academicLabel}<span>{academicLabel} · {termInfo?.label}</span>{/if}
			<a class="button" href="/personal-project/calendar/student">{school} · 학교 설정</a><label
				>{exploration ? '개설 학기' : '학년·학기'}<select
					aria-label="학기"
					value={term}
					disabled={loading || busy}
					onchange={(e) => {
						const next = e.currentTarget.value;
						if (dirty && !confirm('저장하지 않은 시간표를 두고 학기를 바꿀까요?')) {
							e.currentTarget.value = term;
							return;
						}
						void loadTerm(next);
					}}
					>{#each catalog?.terms || [] as item}<option value={item.id}
							>{academicSlot(item, admissionYear, academicOffset) || item.label} · {item.label}</option
						>{/each}</select
				></label
			>
		</div>
	</header>
	{#if !exploration && admissionYear}<nav class="semester-nav" aria-label="내 학년별 시간표">
			{#each (catalog?.terms || [])
				.filter((t) => academicSlot(t, admissionYear, academicOffset))
				.sort((a, b) => termDates(a).starts_on.localeCompare(termDates(b).starts_on)) as t}<button
					class:active={term === t.id}
					disabled={loading || busy}
					onclick={async () => {
						if (dirty) await run(save);
						if (!dirty) await loadTerm(t.id, '');
					}}>{academicSlot(t, admissionYear, academicOffset)}</button
				>{/each}
		</nav>{:else if !exploration}<p>
			학교 설정에서 입학 연도를 입력하면 1-1·1-2·계절학기로 표시됩니다.
		</p>{/if}
	{#if error}<p class="error" role="alert">{error}</p>{/if}{#if notice}<p
			class="notice"
			role="status"
		>
			{notice}
		</p>{/if}
	{#if detail}<section class="panel">
			<button onclick={() => (detail = null)}>상세 닫기</button>
			<h2>{detail.name} · {detail.sbjt_cd}</h2>
			<CourseTrend
				{term}
				code={detail.sbjt_cd}
				section={detail.lt_no}
			/>{#each history as item}<details>
					<summary>{item.term} · {item.courses.length}개 분반</summary>{#each item.courses as c}<p>
							{c.professor} · {c.lt_no} · {c.credits}학점 · {times(c)}
						</p>{/each}
				</details>{:else}<p>개설 이력을 불러오는 중…</p>{/each}
		</section>{/if}
	{#if loading}<p role="status">
			강의 목록과 내 시간표를 불러오는 중…
		</p>{:else if !initialized}<button onclick={() => location.reload()}>다시 불러오기</button
		>{:else}
		{#if !['서울대학교', '서울대'].includes(school)}<p class="notice">
				현재 검색 데이터는 서울대학교 강의입니다. 다른 학교의 수업은 직접 입력할 수 있습니다.
			</p>{/if}
		<div class="workspace">
			<section class="panel search-panel" aria-label="강의 검색">
				<h2 data-search-ms={searchMs.toFixed(2)}>강의 검색</h2>
				<form
					onsubmit={(e) => {
						e.preventDefault();
						void search();
					}}
				>
					<div class="search-field">
						<input
							aria-label="강의 검색어"
							bind:value={q}
							placeholder="강의명, 교수명, 과목번호"
							maxlength="120"
						/><button class="primary" disabled={searching}>검색</button>
					</div>
					<div class="filters">
						<select aria-label="학과 필터" bind:value={department} onchange={() => search()}
							><option value="">전체 학과</option>{#each departments as item}<option>{item}</option
								>{/each}</select
						><select
							aria-label="이수구분 필터"
							bind:value={classification}
							onchange={() => search()}
							><option value="">이수구분</option>{#each classifications as item}<option
									>{item}</option
								>{/each}</select
						><select aria-label="요일 필터" bind:value={day} onchange={() => search()}
							><option value="">모든 요일</option>{#each days as name, i}<option value={String(i)}
									>{name}요일</option
								>{/each}</select
						>
					</div>
					<div class="filters">
						<label>학점<input type="number" min="1" max="20" bind:value={creditsFilter} /></label
						><label>시작 이후<input type="time" bind:value={after} /></label><label
							>종료 이전<input type="time" bind:value={before} /></label
						><label><input type="checkbox" bind:checked={emptyOnly} />빈 시간만</label>
					</div>
				</form>
				<p class="muted" role="status">
					{searching ? '검색 중…' : `${total.toLocaleString()}개 강의`}
				</p>
				<div class="results" aria-busy={searching}>
					{#each courses as course (course.id)}{@const added = selected.some(
							(c) => c.id === course.id
						)}
						<article class="course">
							<div class="course-head">
								<h3>
									<button class="course-title" onclick={() => showDetail(course)}
										>{course.name}</button
									>
								</h3>
								<span>{course.credits}학점</span>
							</div>
							<p>{course.professor || '담당교수 미정'} · {course.department}</p>
							<p class="time">
								{times(course)}
								{#if !added && conflict(courseLessons(course))}<strong>· 시간 겹침</strong>{/if}
							</p>
							<div class="course-foot">
								<small
									>{course.classification.join(' · ')}<br />{course.sbjt_cd} ({course.lt_no}) · {course.room ||
										'강의실 미정'}</small
								><button
									disabled={added || busy || searching || course.status === '폐강'}
									onclick={() => add(course)}
									aria-label={`${course.name} ${course.lt_no} ${added ? '담음' : '담기'}`}
									>{added ? '✓ 담음' : course.status === '폐강' ? '폐강' : '+ 담기'}</button
								>
							</div>
						</article>{:else}<p class="muted">
							검색 결과가 없습니다. 검색어나 필터를 바꿔보세요.
						</p>{/each}
					{#if courses.length < total}<button
							disabled={searching}
							onclick={() => {
								offset = courses.length;
								void search(false);
							}}>강의 더 보기</button
						>{/if}
				</div>
			</section>
			<section class="schedule">
				<div class="schedule-heading">
					<div>
						<h2>{termInfo?.label} <span>{credits}학점</span></h2>
						<p class="muted">
							{selected.length}개 강의 · 직접 입력 {manual.length}개 · {dirty
								? '저장하지 않은 변경'
								: '저장됨'}
						</p>
					</div>
					{#if error && dirty}<button onclick={() => run(save)}>저장 다시 시도</button
						>{/if}{#if exploration}<button
							class="primary"
							disabled={busy}
							onclick={() =>
								run(async () => {
									const current = await request<{ draft: Draft | null }>(
										`/student/timetable/draft?term=${encodeURIComponent(term)}`
									);
									if (current.draft && !confirm('이 후보로 내 시간표를 바꿀까요?')) return;
									await request(`/student/timetable/draft?term=${encodeURIComponent(term)}`, {
										method: 'PUT',
										body: {
											...JSON.parse(snapshot),
											revision: current.draft?.revision || 0,
											sync_calendar: true
										}
									});
									notice = '내 시간표와 캘린더에 반영했습니다.';
								})}>내 시간표로 선택</button
						>{/if}
				</div>
				<TimetableGrid {lessons} />
				{#if !selected.length && !manual.length}<p class="empty">
						왼쪽에서 강의를 검색해 담아보세요.<br /><small
							>모바일에서는 위의 검색 목록에서 담을 수 있습니다.</small
						>
					</p>{/if}
				{#if missing.length}<p class="notice">
						{missing.map((c) => c.name).join(', ')}: 시간 미정 수업은 학점에만 반영됩니다. 확정 후
						직접 수업을 입력해주세요.
					</p>{/if}
				<details class="panel selected" open>
					<summary>{slot ? slot + ' · ' : ''}담은 강의 {selected.length + manual.length}개</summary
					>{#each selected as course}<div class="chosen">
							<span
								><strong>{course.name}</strong><small
									>{course.sbjt_cd} · {times(course)} · {course.professor}</small
								></span
							><button
								disabled={busy}
								aria-label={`${course.name} 빼기`}
								onclick={() => (selected = selected.filter((c) => c.id !== course.id))}>빼기</button
							>
						</div>{/each}{#each manual as lesson, i}<div class="chosen">
							<span
								><strong>{lesson.title}</strong><small
									>{days[lesson.weekday]} {lesson.start}–{lesson.end} · 직접 입력</small
								></span
							><button
								disabled={busy}
								aria-label={`${lesson.title} 빼기`}
								onclick={() => (manual = manual.filter((_, j) => j !== i))}>빼기</button
							>
						</div>{/each}
					<details>
						<summary>수업 직접 입력</summary>
						<form
							class="fields"
							onsubmit={(e) => {
								e.preventDefault();
								addManual();
							}}
						>
							<input
								aria-label="직접 입력 과목명"
								bind:value={manualTitle}
								placeholder="수업 이름"
								maxlength="120"
								required
							/><select aria-label="직접 입력 요일" bind:value={manualDay}
								>{#each days as name, i}<option value={i}>{name}</option>{/each}</select
							><input
								aria-label="직접 입력 시작"
								type="time"
								bind:value={manualStart}
								required
							/><input
								aria-label="직접 입력 종료"
								type="time"
								bind:value={manualEnd}
								required
							/><input
								aria-label="직접 입력 강의실"
								bind:value={manualRoom}
								placeholder="강의실"
								maxlength="500"
							/><button disabled={busy || manual.length >= 60}>수업 담기</button>
						</form>
					</details>
				</details>
				<section class="panel import">
					<h2>학기 일정</h2>
					<p class="muted">
						{exploration
							? '초안은 내 시간표로 선택하기 전까지 캘린더에 표시되지 않습니다.'
							: '수업 변경과 휴강일이 주간·일간 캘린더에 자동 반영됩니다.'}
					</p>
					<div class="fields">
						<label>개강<input type="date" bind:value={starts} required /></label><label
							>종강<input type="date" bind:value={ends} min={starts} required /></label
						>
					</div>
					<p class="muted">
						기본 1학기는 3월 1일~6월 30일, 2학기는 9월 1일~12월 31일입니다. 학교 학사일정에 맞게
						날짜를 바꾸고 시간표를 저장하면 다음에도 유지됩니다.
					</p>
					<label><input type="checkbox" bind:checked={skip} />공휴일 제외</label><label
						class="exclusions"
						>추가 휴강일<input
							bind:value={exclusions}
							placeholder="2026-10-02, 2026-11-16"
						/></label
					><button disabled={busy || !lessons.length} onclick={() => run(previewImport)}
						>캘린더 등록 미리보기</button
					>
					{#if preview}<div class="preview">
							<strong>수업 일정 {preview.events.length}개 · 휴강 {preview.skipped.length}개</strong>
							<details>
								<summary>등록·휴강 일정 확인</summary>
								<div class="preview-list">
									{#each preview.events as e}<p>
											{e.startTime.slice(0, 16).replace('T', ' ')} · {e.title}
										</p>{/each}{#each preview.skipped as e}<p>
											{e.date} · {e.title} · {e.reason}
										</p>{/each}
								</div>
							</details>
							<a class="button" href="/personal-project/calendar/week">주간 캘린더 보기</a>
						</div>{/if}
					<details>
						<summary>시간표 파일 가져오기·내보내기</summary>
						<p class="muted">
							NETAQ에서 내보낸 JSON 파일을 지원합니다. SNUTT·에브리타임 계정 연결 없이 사용할 수
							있습니다.
						</p>
						<button onclick={exportFile}>시간표 파일 내보내기</button><label
							>시간표 파일<input
								type="file"
								accept=".json,application/json"
								disabled={busy}
								onchange={importFile}
							/></label
						>
					</details>
				</section>
			</section>
		</div>
		<footer class="muted">
			서울대 수강편람 가공 데이터 · <a href={catalog?.source} target="_blank" rel="noreferrer"
				>Class Checker</a
			>
			· 원본 갱신 {catalog?.sourceUpdatedAt.slice(0, 10)} ·
			<a href="https://sugang.snu.ac.kr" target="_blank" rel="noreferrer">공식 수강편람 확인</a><br
			/>검색 결과는 저장된 자료이며 실시간 수강신청·정원 정보가 아닙니다.
		</footer>
	{/if}
</div>

<style>
	.semester-nav {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 12px 0;
	}
	.semester-nav .active {
		background: var(--cw-accent, #ba4329);
		color: white;
	}
	.chosen {
		flex-wrap: wrap;
	}
	.schedule {
		min-width: 0;
	}
	.workspace {
		display: grid;
		grid-template-columns: minmax(300px, 390px) minmax(0, 1fr);
		gap: 24px;
		align-items: start;
	}
	.search-panel {
		position: sticky;
		top: 20px;
	}
	.search-field {
		display: flex;
		gap: 8px;
	}
	.search-field input {
		flex: 1;
		width: 0;
	}
	.filters {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 8px;
		margin-top: 10px;
	}
	.filters label {
		display: flex;
		flex-direction: column;
		gap: 5px;
		align-items: stretch;
		min-width: 0;
		white-space: nowrap;
	}
	.filters label:has(input[type='checkbox']) {
		flex-direction: row;
		align-items: center;
	}
	.filters input[type='time'],
	.filters input[type='number'] {
		width: 100%;
		min-width: 0;
	}
	.filters select:first-child {
		grid-column: 1/-1;
	}
	.results {
		max-height: 720px;
		overflow: auto;
	}
	.course {
		padding: 18px 0;
		border-top: 1px solid #e7e8ec;
	}
	.course-head,
	.course-foot,
	.schedule-heading,
	.chosen {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		align-items: center;
	}
	.course h3 {
		font-size: 15px;
		margin: 0;
		line-height: 1.5;
	}
	.course-head span {
		font-size: 11px;
		white-space: nowrap;
		color: #696b73;
	}
	.course p {
		font-size: 12px;
		margin: 7px 0;
		color: #696b73;
	}
	.course .time {
		color: #35363c;
	}
	.course small {
		font-size: 10px;
		color: #777;
		line-height: 1.6;
	}
	.course-foot button {
		flex-shrink: 0;
	}
	.schedule-heading h2 {
		margin-bottom: 4px;
	}
	.schedule-heading h2 span {
		font-size: 13px;
		color: var(--ondo-accent);
		margin-left: 8px;
	}
	.schedule-heading {
		margin-bottom: 14px;
	}
	.selected,
	.import {
		margin-top: 18px;
	}
	.chosen {
		padding: 10px 0;
		border-top: 1px solid #ececf0;
	}
	.chosen strong {
		font-size: 13px;
	}
	.chosen small {
		display: block;
		font-size: 11px;
		margin-top: 5px;
		color: #777;
	}
	.empty {
		text-align: center;
		color: #777;
		font-size: 13px;
	}
	.empty small {
		font-size: 11px;
	}
	.exclusions {
		margin: 14px 0;
		flex-wrap: wrap;
	}
	.preview {
		border-top: 1px solid #ddd;
		margin-top: 16px;
		padding-top: 16px;
		font-size: 13px;
	}
	.preview-list {
		max-height: 220px;
		overflow: auto;
	}
	footer {
		margin-top: 24px;
		line-height: 1.8;
	}
	@media (max-width: 1050px) {
		.workspace {
			grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
			gap: 14px;
		}
	}
	@media (max-width: 850px) {
		.workspace {
			grid-template-columns: minmax(0, 1fr);
		}
		.search-panel {
			position: static;
		}
		.results {
			max-height: 360px;
		}
		.schedule-heading {
			margin-top: 10px;
		}
	}
</style>
