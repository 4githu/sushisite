<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { PersonalApiError, personalApi } from '$lib/personal-project/shared/api';
	import type { AttendanceStatus, AuraSession } from '$lib/personal-project/shared/types';
	import AuraReportEditor from '$lib/personal-project/aura/components/AuraReportEditor.svelte';
	import { createDocument, createTextBlock, normalizeDocument } from '$lib/textediter/model';
	import type { EditorDocument } from '$lib/textediter/types';

	let session = $state<AuraSession | null>(null);
	let error = $state('');
	let saving = $state(false);
	let sourceNotes = $state('');
	let reportDocument = $state<EditorDocument>(createDocument());
	let editorInitialDocument = $state<EditorDocument>(createDocument());
	let editor = $state<AuraReportEditor>();
	let startTime = $state('');
	let endTime = $state('');
	let hourlyRate = $state(30000);

	const attendanceOptions: { value: AttendanceStatus; label: string }[] = [
		{ value: 'scheduled', label: '예정' },
		{ value: 'completed', label: '진행 완료' },
		{ value: 'cancelled', label: '취소' },
		{ value: 'absent', label: '불참' }
	];

	function localInput(value: string | null) {
		if (!value) return '';
		const date = new Date(value);
		const offset = date.getTimezoneOffset() * 60_000;
		return new Date(date.getTime() - offset).toISOString().slice(0, 16);
	}

	function reportTemplate(studentName: string): EditorDocument {
		const document = createDocument();
		document.blocks = [
			{ ...createTextBlock('heading', `${studentName} 클리닉 리포트`), level: 1 },
			{ ...createTextBlock('heading', '학습 내용'), level: 2 },
			createTextBlock('paragraph', ''),
			{ ...createTextBlock('heading', '잘한 점'), level: 2 },
			createTextBlock('paragraph', ''),
			{ ...createTextBlock('heading', '보완할 점'), level: 2 },
			createTextBlock('paragraph', ''),
			{ ...createTextBlock('heading', '다음 목표'), level: 2 },
			createTextBlock('paragraph', '')
		];
		return document;
	}

	async function load() {
		try {
			session = await personalApi.session(Number(page.params.id));
			sourceNotes = session.report?.sourceNotes ?? '';
			startTime = localInput(session.startTime);
			endTime = localInput(session.endTime);
			hourlyRate = session.hourlyRate;
			const loadedDocument = session.report
				? normalizeDocument(session.report.contentJson)
				: reportTemplate(session.studentName);
			editorInitialDocument = loadedDocument;
			reportDocument = loadedDocument;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '클리닉을 불러오지 못했습니다.';
		}
	}

	async function updateSchedule(allowOverlap = false) {
		if (!session || !startTime) return;
		saving = true;
		try {
			session = await personalApi.updateSession(session.id, {
				start_time: new Date(startTime).toISOString(),
				end_time: endTime ? new Date(endTime).toISOString() : null,
				hourly_rate: hourlyRate,
				allow_overlap: allowOverlap
			});
		} catch (cause) {
			if (
				cause instanceof PersonalApiError &&
				cause.code === 'schedule_conflict' &&
				!allowOverlap &&
				confirm(`${cause.message}\n그래도 이 시간으로 변경할까요?`)
			) {
				await updateSchedule(true);
				return;
			}
			error = cause instanceof Error ? cause.message : '클리닉 시간을 수정하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	async function removeSession() {
		if (!session || !confirm('이 클리닉 일정과 리포트를 삭제할까요?')) return;
		try {
			await personalApi.deleteSession(session.id);
			goto('/personal-project/aura');
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '클리닉을 삭제하지 못했습니다.';
		}
	}

	async function changeAttendance(value: AttendanceStatus) {
		if (!session) return;
		saving = true;
		try {
			session = await personalApi.updateSession(session.id, { attendance_status: value });
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '상태를 변경하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	async function ensureReport() {
		if (!session) return null;
		if (session.report) return session.report.id;
		const document = editor?.getJSON() ?? reportDocument;
		const created = await personalApi.createReport(session.id, document, sourceNotes);
		await load();
		return created.id;
	}

	async function saveReport(submit = false) {
		if (!session) return;
		saving = true;
		error = '';
		try {
			reportDocument = editor?.getJSON() ?? reportDocument;
			const reportId = await ensureReport();
			if (!reportId) return;
			await personalApi.updateReport(reportId, {
				source_notes: sourceNotes,
				content_json: reportDocument,
				status: 'ready'
			});
			if (submit) await personalApi.submitReport(reportId);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '리포트를 저장하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Clinic detail</p>
		<h1>{session?.studentName ?? '클리닉 상세'}</h1>
		<p>
			{session
				? new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long', timeStyle: 'short' }).format(
						new Date(session.startTime)
					)
				: '정보를 불러오는 중입니다.'}
		</p>
	</div>
	<div class="head-actions">
		<button class="danger-button" onclick={removeSession}>일정 삭제</button>
		<a class="ghost-button back-button" href="/personal-project/aura">← 대시보드</a>
	</div>
</div>

{#if error}<div class="error-banner">{error}</div>{/if}

{#if session}
	<div class="detail-grid">
		<section class="card info-panel">
			<p class="eyebrow">Session</p>
			<h2>진행 정보</h2>
			<dl>
				<div>
					<dt>학생</dt>
					<dd>{session.studentName}</dd>
				</div>
				<div>
					<dt>학교</dt>
					<dd>{session.schoolName || '미입력'}</dd>
				</div>
				<div>
					<dt>정산 금액</dt>
					<dd>{session.amount.toLocaleString()}원</dd>
				</div>
			</dl>
			<div class="attendance">
				<label for="attendance">진행 상태</label>
				<select
					id="attendance"
					value={session.attendanceStatus}
					onchange={(event) => changeAttendance(event.currentTarget.value as AttendanceStatus)}
					disabled={saving}
				>
					{#each attendanceOptions as option}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</div>
			<div class="schedule-edit">
				<label for="detail-start">클리닉 시간</label>
				<input id="detail-start" type="datetime-local" bind:value={startTime} />
				<input aria-label="클리닉 종료 시간" type="datetime-local" bind:value={endTime} />
				<label for="detail-rate">시급</label>
				<input id="detail-rate" type="number" min="0" step="1000" bind:value={hourlyRate} />
				<button class="ghost-button" onclick={() => updateSchedule()} disabled={saving}
					>시간 수정</button
				>
			</div>
			{#if session.description}
				<div class="session-note">
					<span>일정 메모</span>
					<p>{session.description}</p>
				</div>
			{/if}
		</section>

		<section class="card report-panel">
			<header>
				<div>
					<p class="eyebrow">Report</p>
					<h2>클리닉 리포트</h2>
				</div>
				<span class={`status-pill ${session.report?.status ?? ''}`}>
					{session.report?.status === 'submitted'
						? '제출 완료'
						: session.report
							? '작성 중'
							: '미작성'}
				</span>
			</header>
			<div class="report-fields">
				<div class="field">
					<label for="source-notes">관찰 메모</label>
					<textarea
						id="source-notes"
						bind:value={sourceNotes}
						placeholder="수업에서 관찰한 내용과 보완할 점을 자유롭게 적어주세요"
					></textarea>
				</div>
				<div class="editor-field">
					<div class="editor-label">
						<strong>리포트 본문</strong>
						<span>Tab 들여쓰기 · 선택 후 Ctrl/Cmd+Alt+H 형광펜</span>
					</div>
					<AuraReportEditor
						bind:this={editor}
						initialValue={editorInitialDocument}
						readonly={session.report?.status === 'submitted'}
						placeholder="학생과 보호자에게 전달할 리포트를 작성하세요"
						onchange={(value) => (reportDocument = value)}
					/>
				</div>
			</div>
			<footer>
				<span
					>{session.report?.submittedAt
						? `제출: ${new Date(session.report.submittedAt).toLocaleString('ko-KR')}`
						: '저장 후 검토하여 제출할 수 있습니다.'}</span
				>
				<div>
					<button class="ghost-button" onclick={() => saveReport(false)} disabled={saving}
						>임시 저장</button
					>
					<button
						class="primary-button"
						onclick={() => saveReport(true)}
						disabled={saving || session.report?.status === 'submitted'}
					>
						{session.report?.status === 'submitted' ? '제출 완료' : '리포트 제출'}
					</button>
				</div>
			</footer>
		</section>
	</div>
{/if}

<style>
	.back-button {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}

	.head-actions {
		display: flex;
		gap: 8px;
	}

	.detail-grid {
		display: grid;
		grid-template-columns: minmax(240px, 0.65fr) minmax(0, 1.7fr);
		gap: 18px;
		align-items: start;
	}

	.info-panel,
	.report-panel {
		padding: 25px;
	}

	h2 {
		margin: 0;
		font-family: Georgia, 'Noto Sans KR', serif;
		font-size: 19px;
		font-weight: 500;
	}

	dl {
		margin: 24px 0;
	}

	dl div {
		padding: 12px 0;
		display: flex;
		justify-content: space-between;
		border-bottom: 1px solid var(--pp-line);
	}

	dt {
		color: var(--pp-muted);
		font-size: 10px;
	}

	dd {
		margin: 0;
		font-size: 11px;
		font-weight: 700;
	}

	.attendance {
		display: grid;
		gap: 7px;
	}

	.attendance label {
		font-size: 10px;
		font-weight: 700;
	}

	.attendance select {
		height: 40px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		font-size: 12px;
	}

	.schedule-edit {
		margin-top: 18px;
		display: grid;
		gap: 7px;
	}

	.schedule-edit label {
		font-size: 10px;
		font-weight: 700;
	}

	.schedule-edit input {
		height: 38px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		font-size: 11px;
	}

	.session-note {
		margin-top: 20px;
		padding: 15px;
		border-radius: 9px;
		background: #f4f2ec;
	}

	.session-note span {
		color: var(--pp-muted);
		font-size: 9px;
		font-weight: 700;
	}

	.session-note p {
		margin: 7px 0 0;
		font-size: 11px;
		line-height: 1.6;
	}

	.report-panel {
		padding: 0;
		overflow: hidden;
	}

	.report-panel header {
		padding: 22px 25px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		border-bottom: 1px solid var(--pp-line);
	}

	.report-fields {
		padding: 24px 25px;
		display: grid;
		gap: 18px;
	}

	.editor-field {
		display: grid;
		gap: 8px;
	}

	.editor-label {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 12px;
	}

	.editor-label strong {
		font-size: 11px;
		font-weight: 700;
	}

	.editor-label span {
		color: var(--pp-muted);
		font-size: 9px;
	}

	.report-panel :global(.text-editor-card) {
		border-color: var(--pp-line);
		border-radius: 10px;
		box-shadow: none;
	}

	.report-panel :global(.text-editor-toolbar) {
		background: #f6f4ee;
		border-color: var(--pp-line);
	}

	.report-panel :global(.text-editor-surface) {
		min-height: 320px;
	}

	.report-panel footer {
		padding: 17px 25px;
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 16px;
		border-top: 1px solid var(--pp-line);
		background: #faf9f5;
	}

	.report-panel footer > span {
		color: var(--pp-muted);
		font-size: 9px;
	}

	.report-panel footer div {
		display: flex;
		gap: 8px;
	}

	@media (max-width: 850px) {
		.detail-grid {
			grid-template-columns: 1fr;
		}

		.report-panel footer {
			align-items: stretch;
			flex-direction: column;
		}
	}
</style>
