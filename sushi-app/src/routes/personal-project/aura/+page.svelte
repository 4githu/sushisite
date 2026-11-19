<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import AuraWeekScheduler from '$lib/personal-project/aura/components/AuraWeekScheduler.svelte';
	import {
		normalizeProgressStage,
		progressStageLabels,
		progressStages,
		type ProgressStage
	} from '$lib/personal-project/aura/stages';
	import { PersonalApiError, personalApi } from '$lib/personal-project/shared/api';
	import type { ClinicRound, RoundModality, School } from '$lib/personal-project/shared/types';
	import { buildRoomRequestPreview } from '$lib/personal-project/aura/room-request';

	let schools = $state<School[]>([]);
	let rounds = $state<ClinicRound[]>([]);
	let loading = $state(true);
	let error = $state('');
	let showModal = $state(false);
	let saving = $state(false);
	let selectedRound = $state<ClinicRound | null>(null);
	let schoolId = $state('');
	let progressStage = $state<ProgressStage>('accepted');
	let roundNumbers = $state('1');
	let studentNames = $state('');
	let targetEdits = $state<{ id?: number; student_name: string }[]>([]);
	let startTime = $state('');
	let endTime = $state('');
	let description = $state('');
	let isRecurring = $state(false);
	let repeatCount = $state(2);
	let intervalWeeks = $state(1);
	let occurrenceRounds = $state<string[]>(['1', '2']);
	let editScope = $state<'this' | 'following' | 'all'>('this');
	let roomRequestDate = $state<Date | null>(null);
	let roomRequestNotice = $state('');
	let roomRequestTrigger: HTMLElement | null = null;
	let roomRequestRounds = $state<ClinicRound[]>([]);
	let roomRequestLoading = $state(false);
	let roomRequestCopied = $state(false);
	let roomRequestLoadError = $state(false);
	let roomRequestTextarea = $state<HTMLTextAreaElement | undefined>();
	let roomRequestVersion = 0;
	let modality = $state<RoundModality>('in_person');

	const roomPreview = $derived(roomRequestDate && !roomRequestLoading ? buildRoomRequestPreview(roomRequestDate, roomRequestRounds) : null);


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

	function localWeekStart(date: Date) {
		const monday = new Date(date);
		const daysSinceMonday = (monday.getDay() + 6) % 7;
		monday.setDate(monday.getDate() - daysSinceMonday);
		monday.setHours(0, 0, 0, 0);
		return monday.getTime();
	}

	function isSameLocalWeek(value: string, date: Date) {
		return localWeekStart(new Date(value)) === localWeekStart(date);
	}

	function mostRecentlyRegisteredRound(candidates: ClinicRound[]) {
		return candidates
			.filter((round) => round.attendanceStatus !== 'cancelled')
			.reduce<ClinicRound | null>(
				(latest, round) => (!latest || round.id > latest.id ? round : latest),
				null
			);
	}

	function mostRecentRoundForSchool(schoolId: number, date: Date) {
		const schoolRounds = rounds.filter((round) => round.schoolId === schoolId);
		const sameWeekRound = mostRecentlyRegisteredRound(
			schoolRounds.filter((round) => isSameLocalWeek(round.startTime, date))
		);
		return sameWeekRound ?? mostRecentlyRegisteredRound(schoolRounds);
	}

	function nextRoundNumber(selectedSchoolId: number, selectedStage: ProgressStage) {
		return (
			Math.max(
				0,
				...rounds
					.filter(
						(round) =>
							round.schoolId === selectedSchoolId &&
							normalizeProgressStage(round.progressStage) === normalizeProgressStage(selectedStage)
					)
					.flatMap((round) => [round.roundNumber, ...round.roundNumbers])
			) + 1
		);
	}

	async function openRoomRequest(date: Date) {
		if (!roomRequestDate) roomRequestTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
		const version = ++roomRequestVersion;
		roomRequestLoadError = false;
		roomRequestCopied = false;
		roomRequestDate = date;
		roomRequestNotice = '';
		roomRequestRounds = [];
		roomRequestLoading = true;
		await tick();
		document.getElementById('room-request-title')?.focus();
		try {
			const latest = await personalApi.rounds();
			if (version === roomRequestVersion) roomRequestRounds = latest;
		} catch (cause) {
			if (version === roomRequestVersion) { roomRequestLoadError = true; roomRequestNotice = cause instanceof Error ? cause.message : '일정을 불러오지 못했습니다.'; }
		} finally {
			if (version === roomRequestVersion) roomRequestLoading = false;
		}
	}

	function closeRoomRequest() {
		roomRequestVersion++;
		roomRequestLoading = false;
		roomRequestDate = null;
		roomRequestTrigger?.focus();
		roomRequestTrigger = null;
	}

	async function copyRoomRequest() {
        if (!roomPreview?.text || roomRequestLoading) return;
        const version = roomRequestVersion;
        const text = roomPreview.text;
        let copied = false;
        try {
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(text);
                copied = true;
            }
        } catch { /* Use selection-based copy when the browser denies Clipboard API access. */ }
        if (version !== roomRequestVersion) return;
        if (!copied && roomRequestTextarea) {
            roomRequestTextarea.focus();
            roomRequestTextarea.select();
            try { copied = document.execCommand('copy'); } catch { copied = false; }
        }
        roomRequestCopied = copied;
        roomRequestNotice = copied ? '복사했습니다.' : '문구를 선택했습니다. 복사 단축키로 복사해주세요.';
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
		const selectedStart = start ?? new Date(Date.now() + 24 * 60 * 60_000);
		if (!start) selectedStart.setHours(16, 0, 0, 0);
		const latestOverallRound = mostRecentlyRegisteredRound(rounds);
		const selectedSchool =
			(latestOverallRound && schools.find((school) => school.id === latestOverallRound.schoolId)) ||
			schools.reduce((latest, school) => (school.id > latest.id ? school : latest));
		const latestRound = mostRecentRoundForSchool(selectedSchool.id, selectedStart);
		schoolId = String(selectedSchool.id);
		progressStage = latestRound
			? normalizeProgressStage(latestRound.progressStage)
			: selectedSchool.currentStage;
		const nextRound = nextRoundNumber(selectedSchool.id, progressStage);
		roundNumbers = String(nextRound);
		const selectedEnd = end ?? new Date(selectedStart.getTime() + 60 * 60_000);
		startTime = localInput(selectedStart);
		endTime = localInput(selectedEnd);
		studentNames = '';
		targetEdits = [];
		description = '';
		modality = 'in_person';
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
		progressStage = round.progressStage;
		roundNumbers = round.roundNumbers.join(',');
		studentNames = round.targets.map((target) => target.studentName).join('\n');
		targetEdits = round.targets.map((target) => ({ id: target.id, student_name: target.studentName }));
		startTime = localInput(new Date(round.startTime));
		endTime = localInput(new Date(round.endTime));
		description = round.description;
		modality = round.modality ?? 'unverified';
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
		const selectedStart = startTime ? new Date(startTime) : new Date();
		const latestSchoolRound = mostRecentRoundForSchool(school.id, selectedStart);
		progressStage = latestSchoolRound
			? normalizeProgressStage(latestSchoolRound.progressStage)
			: school.currentStage;
		setNextRound(school.id);
	}

	function setNextRound(selectedSchoolId = Number(schoolId)) {
		const nextRound = nextRoundNumber(selectedSchoolId, progressStage);
		roundNumbers = String(nextRound);
		occurrenceRounds = Array.from({ length: repeatCount }, (_, index) => String(nextRound + index));
	}

	function moveTarget(index: number, direction: number) {
		const next = [...targetEdits];
		[next[index], next[index + direction]] = [next[index + direction], next[index]];
		targetEdits = next;
	}

	const scheduleTimeSummary = $derived.by(() => {
        if (!startTime || !endTime) return '';
        const start = new Date(startTime), end = new Date(endTime);
        if (!Number.isFinite(+start) || !Number.isFinite(+end)) return '';
        const label = (date: Date) => new Intl.DateTimeFormat('ko-KR', {
            month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true
        }).format(date);
        const minutes = Math.round((+end - +start) / 60000);
        const duration = minutes > 0 ? `총 ${Math.floor(minutes / 60)}시간${minutes % 60 ? ` ${minutes % 60}분` : ''}` : '종료 시각이 시작보다 빠릅니다';
        return `${label(start)} → ${label(end)} · ${duration}`;
    });

	function modalityLabel(value: RoundModality) {
		return value === 'in_person' ? '대면' : value === 'remote' ? '비대면' : '확인 필요';
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
				const editingRound = selectedRound;
				const editedTargets = targetEdits.map((target) => ({
					...target, student_name: target.student_name.trim()
				}));
				if (!editedTargets.length || editedTargets.some((target) => !target.student_name))
					throw new Error('학생 이름을 한 명 이상 입력해주세요.');
				const removed = editingRound.targets.filter(
					(target) => !editedTargets.some((entry) => entry.id === target.id)
				);
				if (removed.some((target) => target.report))
					throw new Error('리포트가 있는 학생은 제거할 수 없습니다. 리포트 소유권을 보존해주세요.');
				if (
					removed.length &&
					!confirm(`${removed.map((target) => target.studentName).join(', ')} 학생 항목을 삭제할까요? 이 항목은 복구할 수 없습니다.`)
				) return;
				const renamed = editedTargets.filter((entry) =>
					editingRound.targets.some((target) =>
						target.id === entry.id && target.studentName !== entry.student_name
					)
				);
				if (
					renamed.length &&
					!confirm('학생 이름을 변경합니다. 동일 학생의 개명·오타 수정이 맞나요? 리포트와 첨부, AI/PDF 대상은 기존 학생 ID로 유지됩니다.')
				) return;
				const targetsChanged =
					editedTargets.length !== editingRound.targets.length ||
					editedTargets.some((entry, index) =>
						entry.id !== editingRound.targets[index]?.id ||
						entry.student_name !== editingRound.targets[index]?.studentName
					);
				if (targetsChanged && editScope !== 'this')
					throw new Error('학생 목록은 이 회차만 수정할 수 있습니다. 반복 일정은 회차별로 수정해주세요.');
				const numbersChanged =
					numbers.length !== editingRound.roundNumbers.length ||
					numbers.some((number, index) => number !== editingRound.roundNumbers[index]);
				const modalityPreview = editScope !== 'this'
					? await personalApi.roundModalityPreview(editingRound.id, editScope) : null;
				if (modalityPreview && (!modalityPreview.roundState || !modalityPreview.rounds.length))
					throw new Error('반복 일정을 불러오지 못했습니다. 입력 내용은 유지됩니다. 다시 저장해주세요.');
				const updatedRound = await personalApi.updateRound(editingRound.id, {
					// Omit unchanged identity fields: the backend regenerates reports when they are present.
					// A school move must carry the selected stage to prevent the backend's default-stage override.
					...(Number(schoolId) !== editingRound.schoolId ? { school_id: Number(schoolId) } : {}),
					...(progressStage !== editingRound.progressStage || Number(schoolId) !== editingRound.schoolId
						? { progress_stage: progressStage }
						: {}),
					...(numbersChanged ? { round_number: numbers[0], round_numbers: numbers } : {}),
					...(targetsChanged ? {
						targets: editedTargets,
						confirm_target_removal: removed.length > 0,
						confirm_identity_rename: renamed.length > 0
					} : {}),
					modality,
					...(editScope !== 'this' && modalityPreview ? {
						expected_round_ids: modalityPreview.rounds.map(round => round.id),
						expected_round_state: modalityPreview.roundState
					} : {}),
					...(+new Date(startTime) !== +new Date(editingRound.startTime)
						? { start_time: new Date(startTime).toISOString() } : {}),
					...(+new Date(endTime) !== +new Date(editingRound.endTime)
						? { end_time: new Date(endTime).toISOString() } : {}),
					description,
					allow_overlap: true,
					scope: editScope
				});
				const savedRound = await personalApi.round(editingRound.id);
				await load();
				const expectedIds = editScope !== 'this' ? modalityPreview?.rounds.map(round => round.id) : [editingRound.id];
				const affectedIds = 'affectedRoundIds' in updatedRound ? updatedRound.affectedRoundIds : expectedIds;
				if (expectedIds && Array.isArray(affectedIds) && JSON.stringify(affectedIds) === JSON.stringify(expectedIds) &&
					savedRound.modality === modality && expectedIds.every(id => rounds.some(round => round.id === id && round.modality === modality))) {
					showModal = false;
				} else {
					throw new Error('저장 후 회차 상태를 확인하지 못했습니다. 다시 조회해주세요.');
				}
				return;
			}
			const body = {
				school_id: Number(schoolId),
				progress_stage: progressStage,
				round_number: roundsByOccurrence[0][0],
				student_names: names,
				start_time: new Date(startTime).toISOString(),
				end_time: new Date(endTime).toISOString(),
				description,
				modality,
				allow_overlap: true
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

			error = cause instanceof Error ? cause.message : '회차를 등록하지 못했습니다.';
		}
	}

	async function createRound(event: SubmitEvent) {
		event.preventDefault();
		if (saving) return;
		error = '';
		saving = true;
		await submitRound();
		saving = false;
	}

	async function removeRound(round: ClinicRound) {
        const scope = showModal && selectedRound?.id === round.id ? editScope : 'this';
        const range = scope === 'all' ? '반복 일정 전체' : scope === 'following' ? '이 일정 및 이후 일정' : '이 일정';
        if (!confirm(`${round.schoolName} ${round.roundLabel} · ${range}을 삭제할까요?`)) return;
        try {
            await personalApi.deleteRound(round.id, scope);
            showModal = false;
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
		<h1>아우라 클리닉</h1>
	</div>
	<button class="primary-button" onclick={() => openCreate()}>＋ 새 회차</button>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}

<section class="stat-grid" aria-busy={loading}>
	<article class="card stat-card sage">
		<span>관리 학교</span><strong>{schools.length}<small>곳</small></strong><a
			href="/personal-project/aura/schools">학교별 보기 →</a
		>
	</article>
	<article class="card stat-card peach">
		<span>전체 회차</span><strong>{rounds.length}<small>회</small></strong>
	</article>
	<article class="card stat-card lilac">
		<span>미완료 리포트</span><strong>{pendingCount}<small>건</small></strong>
	</article>
	<article class="card stat-card yellow">
		<span>이번 달 정산</span><strong>{monthTotal.toLocaleString()}<small>원</small></strong><a
			href="/personal-project/aura/settlements">정산 보기 →</a
		>
	</article>
</section>

<AuraWeekScheduler
	sessions={rounds}
	onselect={openCreate}
	onedit={openEdit}
	ondate={openRoomRequest}
/>

<section class="card round-panel">
	<header>
		<div>
			<p class="eyebrow">Recent clinics</p>
			<h2>최근 클리닉 일정</h2>
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
							><strong>{round.schoolName} · {progressStageLabels[round.progressStage]}</strong
							><small>{formatDate(round.startTime)} · 학생 {round.targets.length}명</small></span
						>
						<span class="status-pill">{modalityLabel(round.modality)}</span>
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
			<a class="primary-button" href="/personal-project/aura/schools">학교 등록</a>
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
			<div class="form-grid" inert={saving}>
				<div class="field">
					<label for="round-school">학교</label>
					<select id="round-school" bind:value={schoolId} onchange={schoolChanged}>
						{#each schools as school}
							<option value={String(school.id)}>{school.name}</option>
						{/each}
					</select>
				</div>
				<div class="field">
					<label for="round-stage">진행 단계</label>
					<select
						id="round-stage"
						bind:value={progressStage}
						onchange={() => !selectedRound && setNextRound()}
					>
						{#each progressStages as stage}
							<option value={stage}>{progressStageLabels[stage]}</option>
						{/each}
						{#if selectedRound && !progressStages.includes(selectedRound.progressStage as (typeof progressStages)[number])}
							<option value={selectedRound.progressStage}>{progressStageLabels[selectedRound.progressStage]}</option>
						{/if}
					</select>
					<small>지난 단계의 클리닉도 선택해서 등록할 수 있습니다.</small>
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
					{#if selectedRound}
						<p class="target-edit-heading">참여 학생</p>
						{#each targetEdits as target, index (target.id ?? `new-${index}`)}
							<div class="target-edit-row">
								<input aria-label={`학생 ${index + 1} 이름`} bind:value={target.student_name} required maxlength="80" />
								<button type="button" aria-label="위로 이동" disabled={index === 0} onclick={() => moveTarget(index, -1)}>↑</button>
								<button type="button" aria-label="아래로 이동" disabled={index === targetEdits.length - 1} onclick={() => moveTarget(index, 1)}>↓</button>
								<button type="button" aria-label="학생 제거" disabled={targetEdits.length === 1 || !!selectedRound.targets.find((item) => item.id === target.id)?.report} onclick={() => targetEdits = targetEdits.filter((_, position) => position !== index)}>제거</button>
							</div>
						{/each}
						<button type="button" onclick={() => targetEdits = [...targetEdits, { student_name: '' }]}>＋ 학생 추가</button>
						<small>작성한 리포트는 학생별로 유지됩니다.</small>
					{:else}
						<label for="round-students">학생 이름</label>
						<textarea
							id="round-students"
							bind:value={studentNames}
							placeholder="한 줄에 한 명씩 입력하세요&#10;김대호&#10;이민지"
							required
						></textarea>
					{/if}
				</div>
				<div class="field">
					<label for="round-start">시작</label><input
						id="round-start"
						type="datetime-local"
						step="60"
						bind:value={startTime}
						required
					/>
				</div>
				<div class="field">
					<label for="round-end">종료</label><input
						id="round-end"
						type="datetime-local"
						step="60"
						bind:value={endTime}
						required
					/>
				</div>
				{#if scheduleTimeSummary}<p class="full" role="status">{scheduleTimeSummary}</p>{/if}
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
							<option value="following">이 일정 및 이후 일정</option>
							<option value="all">반복 일정 전체</option>
						</select>
					</div>
				{/if}
				<div class="field full">
					<label for="round-modality">진행 방식</label>
					<select id="round-modality" bind:value={modality}>
						{#if modality === 'unverified'}<option value="unverified">미지정</option>{/if}
						<option value="in_person">대면</option>
						<option value="remote">비대면</option>
					</select>
				</div>

				<div class="field full">
					<label for="round-description">메모</label><textarea
						id="round-description"
						bind:value={description}
					></textarea>
				</div>
			</div>
			{#if error}<p class="error-banner" role="alert">{error}</p>{/if}
			<div class="modal-actions">
				{#if selectedRound}<button
						type="button"
						class="danger-button"
						onclick={() => selectedRound && removeRound(selectedRound)}>{editScope === 'all' ? '반복 일정 전체 삭제' : editScope === 'following' ? '이후 일정 삭제' : '일정 삭제'}</button
					>{/if}
				<button type="button" class="ghost-button" onclick={() => (showModal = false)}>취소</button
				><button class="primary-button" disabled={saving}
					>{saving ? '저장 중…' : selectedRound ? '일정 수정' : '회차 등록'}</button
				>
			</div>
		</form>
	</div>
{/if}

{#if roomRequestDate}
	<div
		class="modal-backdrop request-backdrop"
		role="presentation"
		onclick={(event) => event.target === event.currentTarget && closeRoomRequest()}
	>
        <div class="modal room-request" role="dialog" aria-modal="true" aria-labelledby="room-request-title" onkeydown={(event) => { if (event.key === 'Escape') closeRoomRequest(); }} tabindex="-1">
            <header class="request-header">
                <h2 id="room-request-title" tabindex="-1">강의실 배정 요청문</h2>
                <p>{new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', weekday: 'long' }).format(roomRequestDate)}</p>
            </header>
            {#if roomRequestLoading}
                <p class="request-empty" role="status">일정을 불러오는 중…</p>
            {:else if roomRequestLoadError}
                <p class="request-empty" role="alert">{roomRequestNotice}</p>
            {:else if roomPreview?.text}
                <textarea bind:this={roomRequestTextarea} readonly value={roomPreview.text} aria-label="강의실 배정 요청문" spellcheck="false"></textarea>
            {:else if roomPreview?.reason === 'no_in_person'}
                <p class="request-empty">이날은 강의실이 필요한 대면 수업이 없습니다.</p>
            {:else if roomPreview?.reason === 'unverified'}
                <p class="request-empty">진행 방식이 지정되지 않은 수업이 있습니다. 해당 수업에서 대면·비대면을 선택해주세요.</p>
            {:else if roomPreview?.reason === 'invalid_round'}
                <p class="request-empty">수업 시간이나 학생 정보가 누락된 일정이 있습니다.</p>
            {/if}
            {#if roomRequestNotice && !roomRequestLoadError}<p class="copy-notice" role="status">{roomRequestNotice}</p>{/if}
            <div class="modal-actions">
                {#if roomRequestNotice && !roomPreview?.text}<button class="ghost-button" onclick={() => roomRequestDate && openRoomRequest(roomRequestDate)}>다시 불러오기</button>{/if}
                <button class="ghost-button" onclick={closeRoomRequest}>닫기</button>
                <button class="primary-button" onclick={copyRoomRequest} disabled={!roomPreview?.text || roomRequestLoading}>{roomRequestCopied ? '복사됨' : '복사하기'}</button>
            </div>
        </div>
	</div>
{/if}

<style>
	.modal {
		width: min(680px, calc(100vw - 32px));
	}

    .request-backdrop { backdrop-filter: none; background: rgba(15, 23, 42, 0.32); }
    .room-request { width: min(560px, calc(100vw - 32px)); padding: 24px; border-radius: 12px; }
    .request-header { margin-bottom: 18px; }
    .room-request h2 { margin: 0; font: inherit; font-size: 18px; font-weight: 700; }
    .room-request h2:focus { outline: none; }
    .request-header p { margin: 6px 0 0; color: var(--pp-muted); font-size: 13px; }
    .room-request textarea { display: block; width: 100%; min-height: 250px; max-height: 48vh; box-sizing: border-box; padding: 16px; border: 1px solid var(--pp-line); border-radius: 8px; background: white; color: inherit; font: 14px/1.8 'Noto Sans KR', sans-serif; resize: vertical; }
    .request-empty { padding: 32px 0; margin: 0; color: var(--pp-muted); font-size: 14px; line-height: 1.6; }
    .copy-notice { margin: 10px 0 0; color: var(--pp-sage-dark); font-size: 12px; }
    .room-request .modal-actions { margin-top: 18px; }

	.quick-report-links {
		margin: 0 0 16px;
		padding: 13px;
		display: grid;
		grid-template-columns: 145px 1fr;
		gap: 12px;
		border: 1px solid #dedbd3;
		border-radius: 10px;
		background: #f7f6f2;
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
	.quick-report-students a span {
		color: var(--pp-sage-dark);
		font-size: 8px;
		white-space: nowrap;
	}
	.quick-report-students .pdf-link {
		align-items: center;
		justify-content: center;
		background: #f1f0eb;
		color: var(--pp-sage-dark);
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
	.target-edit-heading { margin: 0; font-weight: 700; }
	.target-edit-row { display: flex; align-items: center; gap: 6px; }
	.target-edit-row input { flex: 1; min-width: 0; }
	.target-edit-row button { flex: none; padding: 7px; }
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
		border-top: 1px solid var(--pp-line);
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
		border-color: var(--pp-line);
	}
	.peach {
		border-color: var(--pp-line);
	}
	.lilac {
		border-color: var(--pp-line);
	}
	.yellow {
		border-color: var(--pp-line);
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
		background: #e8e7e1;
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
