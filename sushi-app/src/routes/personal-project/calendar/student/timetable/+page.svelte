<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { request } from '$lib/personal-project/shared/api';
	import TimetableGrid from '$lib/personal-project/student/TimetableGrid.svelte';
	import {
		courseLessons,
		overlaps,
		times,
		days,
		termDates,
		type Course,
		type Catalog,
		type Draft,
		type Lesson
	} from '$lib/personal-project/student/catalog';
	import '$lib/personal-project/student/student.css';
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
	let searchVersion = 0;
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
	const payload = $derived({
		name: termInfo?.label || '내 시간표',
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
		error = '';
		try {
			const params = new URLSearchParams({
				term,
				q,
				department,
				classification,
				offset: String(offset)
			});
			if (day !== '') params.set('day', day);
			const result = await request<{
				courses: Course[];
				total: number;
				departments: string[];
				classifications: string[];
			}>(`/student/courses?${params}`);
			if (current !== searchVersion) return;
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
	async function loadTerm(next: string) {
		loading = true;
		initialized = false;
		preview = null;
		error = '';
		try {
			const data = await request<{ draft: Draft | null; courses: Course[] }>(
				`/student/timetable/draft?term=${encodeURIComponent(next)}`
			);
			const info = catalog!.terms.find((t) => t.id === next)!;
			term = next;
			const dates = termDates(info);
			selected = data.courses;
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
			department = '';
			classification = '';
			day = '';
			await search();
		} catch (e) {
			error = e instanceof Error ? e.message : '시간표 불러오기 실패';
		} finally {
			loading = false;
		}
	}
	onMount(async () => {
		try {
			const [data, profile] = await Promise.all([
				request<Catalog>('/student/catalog'),
				request<{ school: string }>('/student/profile')
			]);
			catalog = data;
			school = profile.school || '서울대학교';
			const available = data.terms
				.filter((t) => termDates(t).starts_on <= new Date().toISOString().slice(0, 10))
				.sort((a, b) => termDates(b).starts_on.localeCompare(termDates(a).starts_on));
			await loadTerm((available[0] || data.terms[0]).id);
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
			`/student/timetable/draft?term=${encodeURIComponent(term)}`,
			{ method: 'PUT', body: { ...JSON.parse(input), revision } }
		);
		saved = input;
		revision = result.revision;
		notice = '시간표를 저장했습니다.';
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
			await request(`/student/timetable/draft?term=${encodeURIComponent(term)}`, {
				method: 'PUT',
				body: { ...data, revision }
			});
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
			<h1>나의 시간표</h1>
			<p class="muted">강의를 검색하고, 이번 학기를 한눈에 계획하세요.</p>
		</div>
		<div class="fields">
			<a class="button" href="/personal-project/calendar/student">{school} · 학교 설정</a><label
				>학기<select
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
					>{#each catalog?.terms || [] as item}<option value={item.id}>{item.label}</option
						>{/each}</select
				></label
			>
		</div>
	</header>
	{#if error}<p class="error" role="alert">{error}</p>{/if}{#if notice}<p
			class="notice"
			role="status"
		>
			{notice}
		</p>{/if}
	{#if loading}<p role="status">
			강의 목록과 내 시간표를 불러오는 중…
		</p>{:else if !initialized}<button onclick={() => location.reload()}>다시 불러오기</button
		>{:else}
		{#if !['서울대학교', '서울대'].includes(school)}<p class="notice">
				현재 검색 데이터는 서울대학교 강의입니다. 다른 학교의 수업은 직접 입력할 수 있습니다.
			</p>{/if}
		<div class="workspace">
			<section class="panel search-panel" aria-label="강의 검색">
				<h2>강의 검색</h2>
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
								<h3>{course.name}</h3>
								<span>{course.credits}학점</span>
							</div>
							<p>{course.professor || '담당교수 미정'} · {course.department}</p>
							<p class="time">{times(course)}</p>
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
					<button class="primary" disabled={busy || !dirty} onclick={() => run(save)}
						>시간표 저장</button
					>
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
					<summary>담은 강의 {selected.length + manual.length}개</summary
					>{#each selected as course}<div class="chosen">
							<span
								><strong>{course.name}</strong><small>{times(course)} · {course.professor}</small
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
					<h2>나의 시간표 가져오기</h2>
					<p class="muted">
						담은 수업을 학기 동안 반복되는 주간·일간 일정으로 추가합니다. 월간 캘린더에는 표시하지 않습니다. 이미 가져온 동일 수업은
						중복 추가하지 않습니다. 시간표에서 빼도 가져온 일정은 유지됩니다.
					</p>
					<div class="fields">
						<label>개강<input type="date" bind:value={starts} required /></label><label
							>종강<input type="date" bind:value={ends} min={starts} required /></label
						>
					</div>
					<p class="muted">기본 1학기는 3월 1일~6월 30일, 2학기는 9월 1일~12월 31일입니다. 학교 학사일정에 맞게 날짜를 바꾸고 시간표를 저장하면 다음에도 유지됩니다.</p>
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
							<button
								class="primary"
								disabled={busy || previewKey !== JSON.stringify(payload) || !preview.events.length}
								onclick={() =>
									run(async () => {
										const reviewed = JSON.parse(previewKey);
										await save();
										const result = await request<{ created: number; alreadyImported: boolean }>(
											'/student/timetable/import',
											{ method: 'POST', body: reviewed }
										);
										notice = result.alreadyImported
											? '이미 가져온 시간표입니다.'
											: `${result.created}개 수업을 내 캘린더에 추가했습니다.`;
									})}>내 캘린더로 가져오기</button
							>{#if previewKey !== JSON.stringify(payload)}<p class="muted">
									내용이 바뀌었습니다. 미리보기를 다시 확인해주세요.
								</p>{/if}<a class="button" href="/personal-project/calendar/week"
								>주간 캘린더 보기</a
							>
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
