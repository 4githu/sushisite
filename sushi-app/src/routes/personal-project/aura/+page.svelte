<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import AuraWeekScheduler from '$lib/personal-project/aura/components/AuraWeekScheduler.svelte';
	import { PersonalApiError, personalApi } from '$lib/personal-project/shared/api';
	import type { ClinicRound, School } from '$lib/personal-project/shared/types';

	let schools = $state<School[]>([]);
	let rounds = $state<ClinicRound[]>([]);
	let loading = $state(true);
	let error = $state('');
	let showModal = $state(false);
	let saving = $state(false);
	let selectedRound = $state<ClinicRound | null>(null);
	let schoolId = $state('');
	let roundNumbers = $state('1');
	let studentNames = $state('');
	let startTime = $state('');
	let endTime = $state('');
	let hourlyRate = $state(30000);
	let description = $state('');
	let isRecurring = $state(false);
	let repeatCount = $state(2);
	let intervalWeeks = $state(1);
	let occurrenceRounds = $state<string[]>(['1', '2']);
	let editScope = $state<'this' | 'following'>('this');

	const pendingCount = $derived(
		rounds.reduce(
			(total, round) =>
				total + round.targets.filter((target) => target.report?.status !== 'submitted').length,
			0
		)
	);
	const monthTotal = $derived(
		rounds
			.filter(
				(round) =>
					round.attendanceStatus === 'completed' &&
					new Date(round.startTime).getMonth() === new Date().getMonth()
			)
			.reduce((total, round) => total + round.amount, 0)
	);

	function localInput(date: Date) {
		const offset = date.getTimezoneOffset() * 60_000;
		return new Date(date.getTime() - offset).toISOString().slice(0, 16);
	}

	function formatDate(value: string) {
		return new Intl.DateTimeFormat('ko-KR', {
			month: 'short',
			day: 'numeric',
			weekday: 'short',
			hour: '2-digit',
			minute: '2-digit'
		}).format(new Date(value));
	}

	async function load() {
		loading = true;
		error = '';
		try {
			[schools, rounds] = await Promise.all([personalApi.schools(), personalApi.rounds()]);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '아우라 데이터를 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}

	function openCreate(start?: Date, end?: Date) {
		if (!schools.length) {
			goto('/personal-project/aura/schools');
			return;
		}
		const firstSchool = schools[0];
		schoolId = String(firstSchool.id);
		const nextRound =
			Math.max(
				0,
				...rounds
					.filter((round) => round.schoolId === firstSchool.id)
					.map((round) => round.roundNumber)
			) + 1;
		roundNumbers = String(nextRound);
		const selectedStart = start ?? new Date(Date.now() + 24 * 60 * 60_000);
		if (!start) selectedStart.setHours(16, 0, 0, 0);
		const selectedEnd = end ?? new Date(selectedStart.getTime() + 60 * 60_000);
		startTime = localInput(selectedStart);
		endTime = localInput(selectedEnd);
		hourlyRate = firstSchool.defaultHourlyRate;
		studentNames = '';
		description = '';
		intervalWeeks = 1;
		isRecurring = false;
		repeatCount = 2;
		occurrenceRounds = [String(nextRound), String(nextRound + 1)];
		selectedRound = null;
		editScope = 'this';
		showModal = true;
	}

	function openEdit(round: ClinicRound) {
		selectedRound = round;
		schoolId = String(round.schoolId);
		roundNumbers = round.roundNumbers.join(',');
		studentNames = round.targets.map((target) => target.studentName).join('\n');
		startTime = localInput(new Date(round.startTime));
		endTime = localInput(new Date(round.endTime));
		hourlyRate = round.hourlyRate;
		description = round.description;
		intervalWeeks = 1;
		isRecurring = false;
		repeatCount = 2;
		occurrenceRounds = [round.roundNumbers.join(','), String(round.roundNumber + 1)];
		editScope = 'this';
		showModal = true;
	}

	function setRepeatCount(count: number) {
		const safeCount = Math.min(52, Math.max(2, Number(count) || 2));
		repeatCount = safeCount;
		occurrenceRounds = Array.from(
			{ length: safeCount },
			(_, index) => occurrenceRounds[index] ?? ''
		);
	}

	function parseRoundNumbers(value: string) {
		return value
			.split(',')
			.map((item) => Number(item.trim()))
			.filter((item) => Number.isInteger(item) && item > 0);
	}

	function schoolChanged() {
		const school = schools.find((item) => item.id === Number(schoolId));
		if (!school) return;
		if (selectedRound) return;
		hourlyRate = school.defaultHourlyRate;
		const nextRound =
			Math.max(
				0,
				...rounds.filter((round) => round.schoolId === school.id).map((round) => round.roundNumber)
			) + 1;
		roundNumbers = String(nextRound);
		occurrenceRounds = Array.from({ length: repeatCount }, (_, index) => String(nextRound + index));
	}

	async function submitRound(allowOverlap = false) {
		const numbers = parseRoundNumbers(roundNumbers);
		const roundsByOccurrence = isRecurring ? occurrenceRounds.map(parseRoundNumbers) : [numbers];
		const names = studentNames
			.split(/\n|,/)
			.map((name) => name.trim())
			.filter(Boolean);
		try {
			if (roundsByOccurrence.some((items) => !items.length))
				throw new Error('각 일정의 회차를 숫자와 쉼표 형태로 입력해주세요.');
			if (selectedRound) {
				if (
					names.length < selectedRound.targets.length &&
					!confirm(
						'학생 이름 수가 줄어들어 마지막 항목과 연결된 리포트가 삭제될 수 있습니다. 계속할까요?'
					)
				)
					return;
				await personalApi.updateRound(selectedRound.id, {
					school_id: Number(schoolId),
					round_number: numbers[0],
					round_numbers: numbers,
					student_names: names,
					start_time: new Date(startTime).toISOString(),
					end_time: new Date(endTime).toISOString(),
					hourly_rate: hourlyRate,
					description,
					allow_overlap: allowOverlap,
					scope: editScope
				});
				showModal = false;
				await load();
				return;
			}
			const body = {
				school_id: Number(schoolId),
				round_number: roundsByOccurrence[0][0],
				student_names: names,
				start_time: new Date(startTime).toISOString(),
				end_time: new Date(endTime).toISOString(),
				hourly_rate: hourlyRate,
				description,
				allow_overlap: allowOverlap
			};
			if (isRecurring || numbers.length > 1) {
				await personalApi.createRoundSeries({
					...body,
					repeat_count: roundsByOccurrence.length,
					round_numbers_by_occurrence: roundsByOccurrence,
					interval_weeks: intervalWeeks
				});
			} else {
				await personalApi.createRound(body);
			}
			showModal = false;
			await load();
		} catch (cause) {
			if (
				cause instanceof PersonalApiError &&
				cause.code === 'schedule_conflict' &&
				!allowOverlap &&
				confirm(`${cause.message}\n그래도 등록할까요?`)
			) {
				await submitRound(true);
				return;
			}
			error = cause instanceof Error ? cause.message : '회차를 등록하지 못했습니다.';
		}
	}

	async function createRound(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		await submitRound();
		saving = false;
	}

	async function removeRound(round: ClinicRound) {
		if (!confirm(`${round.schoolName} ${round.roundLabel}를 삭제할까요?`)) return;
		try {
			await personalApi.deleteRound(round.id);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '회차를 삭제하지 못했습니다.';
		}
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Aura clinic</p>
		<h1>학교별 클리닉</h1>
		<p>학교를 기준으로 회차와 학생 이름, 리포트를 한 흐름으로 관리합니다.</p>
	</div>
	<button class="primary-button" onclick={() => openCreate()}>＋ 새 회차</button>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}

<section class="stat-grid" aria-busy={loading}>
	<article class="card stat-card sage">
		<span>학교</span><strong>{schools.length}<small>곳</small></strong><a
			href="/personal-project/aura/schools">학교별 보기 →</a
		>
	</article>
	<article class="card stat-card peach">
		<span>전체 회차</span><strong>{rounds.length}<small>회</small></strong><span
			>캘린더 연결 일정</span
		>
	</article>
	<article class="card stat-card lilac">
		<span>미완료 리포트</span><strong>{pendingCount}<small>건</small></strong><span
			>학생 이름 기준</span
		>
	</article>
	<article class="card stat-card yellow">
		<span>이번 달 정산</span><strong>{monthTotal.toLocaleString()}<small>원</small></strong><a
			href="/personal-project/aura/settlements">정산 보기 →</a
		>
	</article>
</section>

<AuraWeekScheduler sessions={rounds} onselect={openCreate} onedit={openEdit} />

<section class="card round-panel">
	<header>
		<div>
			<p class="eyebrow">Schools & rounds</p>
			<h2>최근 회차</h2>
		</div>
		<a href="/personal-project/aura/schools">학교별 전체보기 →</a>
	</header>
	{#if rounds.length}
		<div class="round-list">
			{#each [...rounds].reverse().slice(0, 10) as round (round.id)}
				<div class="round-row">
					<a href={`/personal-project/aura/schools/${round.schoolId}`}>
						<span class="round-number">{round.roundNumbers.join(',')}</span>
						<span
							><strong>{round.schoolName}</strong><small
								>{formatDate(round.startTime)} · 학생 {round.targets.length}명</small
							></span
						>
						<span class="status-pill"
							>{round.targets.filter((target) => target.report?.status === 'submitted')
								.length}/{round.targets.length} 제출</span
						>
					</a>
					<button onclick={() => removeRound(round)} aria-label="회차 삭제">×</button>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty">
			<strong>등록된 회차가 없습니다.</strong>
			<p>학교를 먼저 등록한 뒤 첫 회차를 만들어보세요.</p>
		</div>
	{/if}
</section>

{#if showModal}
	<div
		class="modal-backdrop"
		role="presentation"
		onclick={(event) => event.target === event.currentTarget && (showModal = false)}
	>
		<form class="modal" onsubmit={createRound}>
			<h2>{selectedRound ? '클리닉 일정 수정' : '새 클리닉 회차'}</h2>
			{#if selectedRound}
				<section class="quick-report-links" aria-label="클리닉 리포트 바로가기">
					<div>
						<strong>바로 클리닉 작성</strong>
						<small>일정 수정 없이 학생 리포트로 이동할 수 있습니다.</small>
					</div>
					<div class="quick-report-students">
						{#each selectedRound.targets as target (target.id)}
							<div class="quick-report-student">
								<a href={`/personal-project/aura/reports/${target.id}`}>
									{target.studentName}
									<span>{target.report ? '이어쓰기' : '작성하기'} →</span>
								</a>
								{#if target.report}
									<a class="pdf-link" href={`/personal-project/aura/reports/${target.id}?pdf=1`}
										>PDF 받기</a
									>
								{/if}
							</div>
						{/each}
					</div>
				</section>
			{/if}
			<div class="form-grid">
				<div class="field">
					<label for="round-school">학교</label>
					<select id="round-school" bind:value={schoolId} onchange={schoolChanged}>
						{#each schools as school}
							<option value={String(school.id)}>{school.name}</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="round-number">회차</label>
					{#if isRecurring && !selectedRound}
						<div id="round-number" class="repeat-placeholder">아래 반복 목록에서 입력</div>
					{:else}
						<input
							id="round-number"
							type="text"
							inputmode="numeric"
							bind:value={roundNumbers}
							placeholder="예: 1 또는 1,2,3"
							required
						/>
						<small>같은 시간에 여러 회차를 진행하면 쉼표로 구분합니다.</small>
					{/if}
				</div>
				<div class="field full important-students">
					<label for="round-students">학생 이름</label>
					<textarea
						id="round-students"
						bind:value={studentNames}
						placeholder="한 줄에 한 명씩 입력하세요&#10;김대호&#10;이민지"
						required
					></textarea>
				</div>
				<div class="field">
					<label for="round-start">시작</label><input
						id="round-start"
						type="datetime-local"
						step="1800"
						bind:value={startTime}
						required
					/>
				</div>
				<div class="field">
					<label for="round-end">종료</label><input
						id="round-end"
						type="datetime-local"
						step="1800"
						bind:value={endTime}
						required
					/>
				</div>
				<div class="field">
					<label for="round-rate">시급</label><input
						id="round-rate"
						type="number"
						min="0"
						step="1000"
						bind:value={hourlyRate}
					/>
				</div>
				{#if !selectedRound}
					<label class="repeat-toggle full">
						<input type="checkbox" bind:checked={isRecurring} />
						<span
							><strong>반복 일정인가요?</strong><small
								>반복 날짜마다 진행할 회차를 따로 입력합니다.</small
							></span
						>
					</label>
					{#if isRecurring}
						<div class="field">
							<label for="round-repeat-count">반복 횟수</label>
							<input
								id="round-repeat-count"
								type="number"
								min="2"
								max="52"
								value={repeatCount}
								onchange={(event) => setRepeatCount(Number(event.currentTarget.value))}
							/>
						</div>
						<div class="field">
							<label for="round-interval">반복 간격</label>
							<select id="round-interval" bind:value={intervalWeeks}>
								<option value={1}>매주</option>
								<option value={2}>2주마다</option>
								<option value={3}>3주마다</option>
								<option value={4}>4주마다</option>
							</select>
						</div>
						<div class="occurrence-list full">
							{#each occurrenceRounds as value, index}
								<label>
									<span>{index + 1}번째 일정 회차</span>
									<input
										{value}
										oninput={(event) => {
											occurrenceRounds[index] = event.currentTarget.value;
											occurrenceRounds = [...occurrenceRounds];
										}}
										placeholder={index === 0 ? '예: 1,2' : '예: 3'}
										required
									/>
								</label>
							{/each}
						</div>
					{/if}
				{/if}
				{#if selectedRound?.seriesGroupId}
					<div class="field full">
						<label for="round-scope">반복 일정 수정 범위</label>
						<select id="round-scope" bind:value={editScope}>
							<option value="this">이 일정만 변경</option>
							<option value="following">이 일정 및 이후 일정 변경</option>
						</select>
					</div>
				{/if}
				<div class="field full">
					<label for="round-description">메모</label><textarea
						id="round-description"
						bind:value={description}
					></textarea>
				</div>
			</div>
			<div class="modal-actions">
				<button type="button" class="ghost-button" onclick={() => (showModal = false)}>취소</button
				><button class="primary-button" disabled={saving}
					>{saving ? '저장 중…' : selectedRound ? '일정 수정' : '회차 등록'}</button
				>
			</div>
		</form>
	</div>
{/if}

<style>
	.modal {
		width: min(680px, calc(100vw - 32px));
	}
	.quick-report-links {
		margin: 0 0 16px;
		padding: 13px;
		display: grid;
		grid-template-columns: 145px 1fr;
		gap: 12px;
		border: 1px solid #ccd8cf;
		border-radius: 10px;
		background: #f4f7f3;
	}
	.quick-report-links strong,
	.quick-report-links small {
		display: block;
	}
	.quick-report-links strong {
		font-size: 11px;
	}
	.quick-report-links small {
		margin-top: 4px;
		color: var(--pp-muted);
		font-size: 8px;
		line-height: 1.5;
	}
	.quick-report-students {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 6px;
	}
	.quick-report-student {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		gap: 5px;
	}
	.quick-report-students a {
		padding: 8px 9px;
		display: flex;
		justify-content: space-between;
		gap: 6px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
		background: white;
		color: var(--pp-ink);
		font-size: 10px;
		font-weight: 700;
		text-decoration: none;
	}
	.quick-report-students .pdf-link {
		align-items: center;
		justify-content: center;
		background: #eef3ef;
		color: var(--pp-sage-dark);
		white-space: nowrap;
	}
	.quick-report-students a span {
		color: var(--pp-sage-dark);
		font-size: 8px;
		white-space: nowrap;
	}
	.repeat-placeholder {
		height: 40px;
		padding: 0 11px;
		display: flex;
		align-items: center;
		border: 1px dashed var(--pp-line);
		border-radius: 8px;
		color: var(--pp-muted);
		font-size: 11px;
	}
	.repeat-toggle {
		padding: 13px;
		display: flex;
		align-items: center;
		gap: 10px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		background: #f7f7f2;
		cursor: pointer;
	}
	.repeat-toggle input {
		width: 17px;
		height: 17px;
	}
	.repeat-toggle strong,
	.repeat-toggle small {
		display: block;
	}
	.repeat-toggle strong {
		font-size: 11px;
	}
	.repeat-toggle small {
		margin-top: 3px;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.occurrence-list {
		padding: 13px;
		display: grid;
		gap: 9px;
		border: 1px solid var(--pp-line);
		border-radius: 9px;
		background: #faf9f4;
	}
	@media (max-width: 620px) {
		.quick-report-links {
			grid-template-columns: 1fr;
		}
		.quick-report-students {
			grid-template-columns: 1fr;
		}
		.occurrence-list label {
			grid-template-columns: 1fr;
		}
	}
	.occurrence-list label {
		display: grid;
		grid-template-columns: 105px 1fr;
		align-items: center;
		gap: 9px;
	}
	.occurrence-list span {
		font-size: 10px;
		font-weight: 700;
	}
	.occurrence-list input {
		height: 36px;
		padding: 0 10px;
		border: 1px solid var(--pp-line);
		border-radius: 7px;
	}
	.important-students textarea {
		min-height: 105px;
		background: #fffef8;
	}
	.important-students textarea:disabled {
		opacity: 1;
		color: var(--pp-ink);
		-webkit-text-fill-color: var(--pp-ink);
	}
	.stat-grid {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		gap: 14px;
	}
	.stat-card {
		min-height: 138px;
		padding: 21px;
		border-top: 3px solid;
	}
	.stat-card > span:first-child {
		color: var(--pp-muted);
		font-size: 10px;
		font-weight: 700;
	}
	.stat-card strong {
		display: block;
		margin: 13px 0;
		font-family: Georgia, serif;
		font-size: 29px;
		font-weight: 500;
	}
	.stat-card small {
		margin-left: 4px;
		font:
			10px 'Noto Sans KR',
			sans-serif;
	}
	.stat-card a,
	.stat-card > span:last-child {
		color: var(--pp-muted);
		font-size: 9px;
		text-decoration: none;
	}
	.sage {
		border-color: var(--pp-sage);
	}
	.peach {
		border-color: var(--pp-peach);
	}
	.lilac {
		border-color: var(--pp-lilac);
	}
	.yellow {
		border-color: var(--pp-yellow);
	}
	.round-panel {
		margin-top: 18px;
		overflow: hidden;
	}
	.round-panel > header {
		padding: 20px 23px;
		display: flex;
		justify-content: space-between;
		align-items: end;
		border-bottom: 1px solid var(--pp-line);
	}
	.round-panel h2 {
		margin: 0;
		font:
			500 18px Georgia,
			'Noto Sans KR',
			serif;
	}
	.round-panel header a {
		color: var(--pp-sage-dark);
		font-size: 10px;
		font-weight: 700;
		text-decoration: none;
	}
	.round-row {
		padding-right: 18px;
		display: flex;
		align-items: center;
		border-top: 1px solid var(--pp-line);
	}
	.round-row:first-child {
		border-top: 0;
	}
	.round-row > a {
		min-width: 0;
		flex: 1;
		padding: 14px 22px;
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 13px;
		color: inherit;
		text-decoration: none;
	}
	.round-number {
		width: 34px;
		height: 34px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #e5ebe5;
		color: var(--pp-sage-dark);
		font:
			700 14px Georgia,
			serif;
	}
	.round-row strong,
	.round-row small {
		display: block;
	}
	.round-row strong {
		font-size: 12px;
	}
	.round-row small {
		margin-top: 3px;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.round-row > button {
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: 7px;
		background: none;
		color: #a76654;
		font-size: 18px;
		cursor: pointer;
	}
	.round-row > button:hover {
		background: #f5e2dc;
	}
	.empty {
		padding: 60px;
		color: var(--pp-muted);
		font-size: 11px;
		text-align: center;
	}
	.empty p {
		margin: 7px 0;
	}
	@media (max-width: 900px) {
		.stat-grid {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (max-width: 600px) {
		.round-row > a {
			grid-template-columns: auto 1fr;
		}
		.round-row .status-pill {
			display: none;
		}
	}
</style>
