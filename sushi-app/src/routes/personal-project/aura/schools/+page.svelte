<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi } from '$lib/personal-project/shared/api';
	import { progressStageLabels, progressStages } from '$lib/personal-project/aura/stages';
	import type { School } from '$lib/personal-project/shared/types';

	let schools = $state<School[]>([]);
	let showModal = $state(false);
	let saving = $state(false);
	let advancing = $state(false);
	let error = $state('');
	let admissionYear = $state(new Date().getFullYear());
	let schoolName = $state('');
	let memo = $state('');
	let freeForThreePlus = $state(false);
	let draggedSchoolId = $state<number | null>(null);
	let dragTargetId = $state<number | null>(null);
	let dragSaving = $state(false);
	let orderMessage = $state('');

	async function load() {
		try {
			schools = await personalApi.schools();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교 목록을 불러오지 못했습니다.';
		}
	}

	async function createSchool(event: SubmitEvent) {
		event.preventDefault();
		saving = true;
		try {
			await personalApi.createSchool({
				admission_year: admissionYear,
				school_name: schoolName.trim(),
				memo,
				free_for_three_plus: freeForThreePlus
			});
			showModal = false;
			schoolName = '';
			memo = '';
			freeForThreePlus = false;
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교를 등록하지 못했습니다.';
		} finally {
			saving = false;
		}
	}

	async function advanceStages() {
		if (!confirm('진행 중인 모든 학교를 다음 학기·시즌으로 한 단계 이동할까요?')) return;
		advancing = true;
		error = '';
		try {
			schools = await personalApi.advanceSchoolStages();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학기를 변경하지 못했습니다.';
		} finally {
			advancing = false;
		}
	}

	async function updateSchool(school: School, body: Record<string, unknown>) {
		error = '';
		try {
			await personalApi.updateSchool(school.id, body);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교 설정을 변경하지 못했습니다.';
		}
	}

	function startSchoolDrag(event: DragEvent, school: School) {
		draggedSchoolId = school.id;
		dragTargetId = null;
		if (event.dataTransfer) {
			event.dataTransfer.effectAllowed = 'move';
			event.dataTransfer.setData('text/plain', String(school.id));
		}
	}

	async function reorderSchool(sourceId: number, targetId: number) {
		if (dragSaving) return;
		const from = schools.findIndex((item) => item.id === sourceId);
		const to = schools.findIndex((item) => item.id === targetId);
		if (from < 0 || to < 0) return;
		const source = schools[from];
		if (from === to || source.termStatus !== schools[to].termStatus) return;
		error = '';
		orderMessage = '';
		const reordered = [...schools];
		reordered.splice(from, 1);
		reordered.splice(to, 0, source);
		schools = reordered;
		dragSaving = true;
		try {
			schools = await personalApi.reorderSchools(reordered.map((item) => item.id));
			orderMessage = `${source.name} 순서를 저장했습니다.`;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교 순서를 변경하지 못했습니다.';
			await load();
		} finally {
			dragSaving = false;
		}
	}

	function moveSchool(school: School, direction: -1 | 1) {
		const index = schools.findIndex((item) => item.id === school.id);
		const neighbor = schools[index + direction];
		if (neighbor) void reorderSchool(school.id, neighbor.id);
	}

	function canMoveSchool(school: School, direction: -1 | 1) {
		const index = schools.findIndex((item) => item.id === school.id);
		return !dragSaving && index >= 0 && schools[index + direction]?.termStatus === school.termStatus;
	}

	function dropSchool(event: DragEvent, target: School) {
		event.preventDefault();
		const sourceId = draggedSchoolId || Number(event.dataTransfer?.getData('text/plain'));
		draggedSchoolId = null;
		dragTargetId = null;
		void reorderSchool(sourceId, target.id);
	}

	async function removeSchool(school: School) {
		if (
			!confirm(
				`${school.name}와 연결된 모든 일정, 학생 이름, 리포트, 기본 양식을 완전히 삭제할까요?\n이 작업은 되돌릴 수 없습니다.`
			)
		)
			return;
		try {
			await personalApi.deleteSchool(school.id);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교를 삭제하지 못했습니다.';
		}
	}

	onMount(load);
</script>

<div class="page-head">
	<div>
		<p class="eyebrow">Schools</p>
		<h1>학교별 리포트</h1>
	</div>
	<div class="page-actions">
		<button class="ghost-button" onclick={advanceStages} disabled={advancing}
			>{advancing ? '변경 중…' : '전체 학기 한 단계 변경'}</button
		>
		<button class="primary-button" onclick={() => (showModal = true)}>＋ 학교 등록</button>
	</div>
</div>
{#if error}<div class="error-banner" role="alert">{error}</div>{/if}
<p class="sr-only" role="status" aria-live="polite">{orderMessage}</p>

<section class="school-grid">
	{#each schools as school (school.id)}
		<article
			class:ended={school.termStatus === 'ended'}
			class:drop-target={dragTargetId === school.id}
			class:dragging={draggedSchoolId === school.id}
			class="school-card card"
			draggable="true"
			title="끌어서 순서 변경"
			ondragstart={(event) => startSchoolDrag(event, school)}
			ondragend={() => {
				draggedSchoolId = null;
				dragTargetId = null;
			}}
			ondragover={(event) => {
				const source = schools.find((item) => item.id === draggedSchoolId);
				if (source && source.termStatus === school.termStatus) {
					event.preventDefault();
					dragTargetId = school.id;
				}
			}}
			ondragleave={() => dragTargetId === school.id && (dragTargetId = null)}
			ondrop={(event) => void dropSchool(event, school)}
		>
			<a href={`/personal-project/aura/schools/${school.id}`} class="school-main">
				<span class="school-mark">{school.name.slice(0, 1)}</span>
				<span
					><strong>{school.name}</strong><small
						><b class="term-pill">{progressStageLabels[school.currentStage]}</b> · {school.termStatus ===
						'ended'
							? '종료'
							: '진행 중'} · 회차
						{school.roundCount}개</small
					>{#if school.freeForThreePlus}<small class="free-rule"
							>3:1 이상 학부모 무료 · 조교 정산 유지</small
						>{/if}
					>{#if school.memo}<p>{school.memo}</p>{/if}</span
				>
				<i>›</i>
			</a>
			<div class="school-actions">
				<select
					aria-label={`${school.name} 현재 진행 단계`}
					value={school.currentStage}
					onchange={(event) => updateSchool(school, { current_stage: event.currentTarget.value })}
				>
					{#each progressStages as value}
						<option {value}>{progressStageLabels[value]}</option>
					{/each}
				</select>
				{#if school.currentStage !== school.recommendedStage}
					<span class="stage-hint"
						>현재 날짜 기준: {progressStageLabels[school.recommendedStage]}</span
					>
				{/if}
				<label class="free-toggle">
					<input
						type="checkbox"
						checked={school.freeForThreePlus}
						onchange={(event) =>
							updateSchool(school, { free_for_three_plus: event.currentTarget.checked })}
					/>
					3:1 이상 학부모 무료
				</label>
				<div class="order-actions" aria-label={`${school.name} 순서 변경`}>
					<button type="button" aria-label={`${school.name} 위로 이동`} title="위로 이동" disabled={!canMoveSchool(school, -1)} onclick={() => moveSchool(school, -1)}>↑</button>
					<button type="button" aria-label={`${school.name} 아래로 이동`} title="아래로 이동" disabled={!canMoveSchool(school, 1)} onclick={() => moveSchool(school, 1)}>↓</button>
				</div>
				<details class="school-more">
					<summary>설정</summary>
					<div>
						<button
							onclick={() =>
								updateSchool(school, {
									term_status: school.termStatus === 'ended' ? 'active' : 'ended'
								})}>{school.termStatus === 'ended' ? '다시 진행' : '학기 종료'}</button
						>
						<a href={personalApi.schoolExportUrl(school.id)}>기록 내보내기</a>
						<button class="delete-school" onclick={() => removeSchool(school)}>삭제</button>
					</div>
				</details>
			</div>
		</article>
	{:else}
		<div class="empty card">
			<strong>학교를 먼저 등록해주세요.</strong>
			<button class="primary-button" onclick={() => (showModal = true)}>첫 학교 등록</button>
		</div>
	{/each}
</section>

{#if showModal}
	<div
		class="modal-backdrop"
		role="presentation"
		onclick={(event) => event.target === event.currentTarget && (showModal = false)}
	>
		<form class="modal" onsubmit={createSchool}>
			<h2>새 학교 등록</h2>
			<div class="form-grid">
				<div class="field full">
					<label for="school-year">입학연도</label><input
						id="school-year"
						type="number"
						min="0"
						max="9999"
						bind:value={admissionYear}
						required
					/>
					<small>2026 또는 26처럼 입력할 수 있습니다.</small>
				</div>
				<div class="field full">
					<label for="school-name">학교 이름</label><input
						id="school-name"
						bind:value={schoolName}
						placeholder="예: 서울"
						required
					/>
					<small
						>목록에는 {String(admissionYear).slice(-2).padStart(2, '0')}{schoolName || '서울'}처럼
						표시됩니다.</small
					>
				</div>
				<div class="field full free-option">
					<label>
						<input type="checkbox" bind:checked={freeForThreePlus} />
						<span
							><strong>3:1 이상이면 학부모 무료</strong><small
								>학부모 청구만 0원이며 조교 정산은 그대로 기록됩니다.</small
							></span
						>
					</label>
				</div>
				<div class="field full">
					<label for="school-memo">메모</label><textarea id="school-memo" bind:value={memo}
					></textarea>
				</div>
			</div>
			<div class="modal-actions">
				<button type="button" class="ghost-button" onclick={() => (showModal = false)}>취소</button
				><button class="primary-button" disabled={saving}>{saving ? '등록 중…' : '등록'}</button>
			</div>
		</form>
	</div>
{/if}

<style>
	.page-actions {
		display: flex;
		gap: 8px;
	}
	.stage-hint {
		color: var(--pp-muted);
		font-size: 11px;
	}
	.school-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 15px;
	}
	.school-card {
		overflow: hidden;
		color: inherit;
		cursor: grab;
		transition:
			border-color 120ms ease,
			transform 120ms ease;
	}
	.school-card:active { cursor: grabbing; }
	.school-card.dragging { opacity: .48; }
	.school-card.drop-target {
		border-color: var(--pp-sage-dark);
		box-shadow: 0 0 0 2px #8d6f6330;
	}
	.school-main {
		padding: 22px;
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 15px;
		color: inherit;
		text-decoration: none;
	}
	.school-card:hover {
		border-color: #b9c8bc;
		transform: translateY(-1px);
	}
	.school-mark {
		width: 44px;
		height: 44px;
		display: grid;
		place-items: center;
		border-radius: 12px;
		background: #e2e9e2;
		color: var(--pp-sage-dark);
		font:
			700 19px Georgia,
			serif;
	}
	.school-card strong,
	.school-card small {
		display: block;
	}
	.term-pill {
		color: var(--pp-sage-dark);
		font-weight: 700;
	}
	.school-card .free-rule {
		color: #a56545;
	}
	.school-card strong {
		font-size: 14px;
	}
	.school-card small {
		margin-top: 5px;
		color: var(--pp-muted);
		font-size: 11px;
	}
	.school-card p {
		margin: 10px 0 0;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.school-card i {
		color: #aaa;
		font-size: 20px;
	}
	.school-card.ended {
		opacity: 0.68;
	}
	.school-actions {
		padding: 10px 14px;
		display: flex;
		flex-wrap: wrap;
		gap: 7px;
		border-top: 1px solid var(--pp-line);
		background: #faf9f5;
	}
	.school-actions button,
	.school-actions a,
	.school-actions select,
	.free-toggle {
		padding: 6px 9px;
		border: 1px solid var(--pp-line);
		border-radius: 6px;
		background: white;
		color: var(--pp-sage-dark);
		font-size: 11px;
		font-weight: 700;
		text-decoration: none;
		cursor: pointer;
	}
	.free-toggle {
		display: inline-flex;
		align-items: center;
		gap: 4px;
	}
	.free-toggle input {
		margin: 0;
	}
	.order-actions { display: flex; gap: 4px; }
	.order-actions button { min-width: 44px; min-height: 44px; font-size: 17px; }
	.order-actions button:disabled { opacity: .4; cursor: not-allowed; }
	.school-more {
		position: relative;
		margin-left: auto;
	}
	.school-more summary {
		padding: 7px 10px;
		border: 1px solid var(--pp-line);
		border-radius: 6px;
		background: white;
		color: var(--pp-sage-dark);
		font-size: 11px;
		font-weight: 700;
		list-style: none;
		cursor: pointer;
	}
	.school-more summary::-webkit-details-marker {
		display: none;
	}
	.school-more > div {
		position: absolute;
		right: 0;
		bottom: calc(100% + 6px);
		z-index: 4;
		display: grid;
		min-width: 120px;
		padding: 5px;
		gap: 4px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fff;
		box-shadow: 0 8px 24px #0002;
	}
	.school-more > div > * {
		text-align: left;
	}
	.free-option {
		padding: 11px;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		background: #fffaf5;
	}
	.free-option > label {
		display: flex;
		align-items: flex-start;
		gap: 9px;
		cursor: pointer;
	}
	.free-option span,
	.free-option strong,
	.free-option small {
		display: block;
	}
	.free-option small {
		margin-top: 3px;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.school-more .delete-school {
		color: #a74b36;
	}
	.empty {
		grid-column: 1 / -1;
		padding: 70px;
		text-align: center;
	}
	@media (max-width: 700px) {
		.school-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
