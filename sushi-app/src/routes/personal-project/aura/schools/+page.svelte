<script lang="ts">
	import { onMount } from 'svelte';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { School } from '$lib/personal-project/shared/types';

	let schools = $state<School[]>([]);
	let showModal = $state(false);
	let saving = $state(false);
	let error = $state('');
	let name = $state('');
	let defaultHourlyRate = $state(30000);
	let memo = $state('');

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
				name: name.trim(),
				default_hourly_rate: defaultHourlyRate,
				memo
			});
			showModal = false;
			name = '';
			memo = '';
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교를 등록하지 못했습니다.';
		} finally {
			saving = false;
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

	async function moveSchool(school: School, direction: 'up' | 'down') {
		try {
			await personalApi.moveSchool(school.id, direction);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교 순서를 변경하지 못했습니다.';
		}
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
		<p>학생을 별도로 관리하지 않고 학교와 회차 아래에 이름만 정리합니다.</p>
	</div>
	<button class="primary-button" onclick={() => (showModal = true)}>＋ 학교 등록</button>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}

<section class="school-grid">
	{#each schools as school (school.id)}
		<article class:ended={school.termStatus === 'ended'} class="school-card card">
			<a href={`/personal-project/aura/schools/${school.id}`} class="school-main">
				<span class="school-mark">{school.name.slice(0, 1)}</span>
				<span
					><strong>{school.name}</strong><small
						>{school.termStatus === 'ended' ? '종료된 학교' : `우선순위 ${school.priority}`} · 회차
						{school.roundCount}개</small
					>{#if school.memo}<p>{school.memo}</p>{/if}</span
				>
				<i>›</i>
			</a>
			<div class="school-actions">
				<button onclick={() => moveSchool(school, 'up')}>위로</button>
				<button onclick={() => moveSchool(school, 'down')}>아래로</button>
				<button
					onclick={() =>
						updateSchool(school, {
							term_status: school.termStatus === 'ended' ? 'active' : 'ended'
						})}>{school.termStatus === 'ended' ? '다시 진행' : '학기 종료'}</button
				>
				<a href={personalApi.schoolExportUrl(school.id)}>전체 기록 내보내기</a>
				<button class="delete-school" onclick={() => removeSchool(school)}>완전 삭제</button>
			</div>
		</article>
	{:else}
		<div class="empty card">
			<strong>학교를 먼저 등록해주세요.</strong>
			<p>학교 안에 회차와 학생 이름이 정리됩니다.</p>
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
					<label for="school-name">학교 이름</label><input
						id="school-name"
						bind:value={name}
						required
					/>
				</div>
				<div class="field full">
					<label for="school-rate">기본 시급</label><input
						id="school-rate"
						type="number"
						min="0"
						step="1000"
						bind:value={defaultHourlyRate}
					/>
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
	.school-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 15px;
	}
	.school-card {
		overflow: hidden;
		color: inherit;
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
	.school-card strong {
		font-size: 14px;
	}
	.school-card small {
		margin-top: 5px;
		color: var(--pp-muted);
		font-size: 9px;
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
	.school-actions a {
		padding: 6px 9px;
		border: 1px solid var(--pp-line);
		border-radius: 6px;
		background: white;
		color: var(--pp-sage-dark);
		font-size: 8px;
		font-weight: 700;
		text-decoration: none;
		cursor: pointer;
	}
	.school-actions .delete-school {
		margin-left: auto;
		color: #a74b36;
	}
	.empty {
		grid-column: 1 / -1;
		padding: 70px;
		text-align: center;
	}
	.empty p {
		margin: 7px 0 18px;
		color: var(--pp-muted);
		font-size: 11px;
	}
	@media (max-width: 700px) {
		.school-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
