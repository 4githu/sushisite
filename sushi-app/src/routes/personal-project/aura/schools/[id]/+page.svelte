<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { personalApi } from '$lib/personal-project/shared/api';
	import type { ClinicRound, School } from '$lib/personal-project/shared/types';

	let school = $state<School | null>(null);
	let error = $state('');
	let addingRoundId = $state<number | null>(null);
	let newStudentName = $state('');

	function groupByRoundNumber(rounds: ClinicRound[]) {
		const groups = new Map<string, ClinicRound[]>();
		for (const round of rounds) {
			const key = [...round.roundNumbers].sort((a, b) => a - b).join(',');
			groups.set(key, [...(groups.get(key) ?? []), round]);
		}
		return [...groups.entries()]
			.map(([key, items]) => ({
				key,
				label: `${key}회차`,
				rounds: items,
				targets: items.flatMap((round) =>
					round.targets.map((target) => ({ ...target, clinicRound: round }))
				)
			}))
			.sort((a, b) => Number(a.key.split(',')[0]) - Number(b.key.split(',')[0]));
	}

	const roundGroups = $derived(groupByRoundNumber(school?.rounds ?? []));

	async function load() {
		try {
			school = await personalApi.school(Number(page.params.id));
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학교 정보를 불러오지 못했습니다.';
		}
	}

	async function addTarget(round: ClinicRound) {
		if (!newStudentName.trim()) return;
		try {
			await personalApi.addRoundTarget(round.id, newStudentName.trim());
			newStudentName = '';
			addingRoundId = null;
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학생 이름을 추가하지 못했습니다.';
		}
	}

	async function removeTarget(id: number, name: string) {
		if (!confirm(`${name} 항목과 작성된 리포트를 삭제할까요?`)) return;
		try {
			await personalApi.deleteRoundTarget(id);
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : '학생 항목을 삭제하지 못했습니다.';
		}
	}

	async function removeRound(round: ClinicRound) {
		if (
			!confirm(`${school?.name ?? ''} ${round.roundLabel} 일정과 학생 리포트를 완전히 삭제할까요?`)
		)
			return;
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
		<p class="eyebrow">School report</p>
		<h1>{school?.name ?? '학교 불러오는 중'}</h1>
		<p>회차별 기본 양식과 학생 리포트 상태를 확인합니다.</p>
	</div>
	<a class="ghost-button back" href="/personal-project/aura/schools">← 학교 목록</a>
</div>
{#if error}<div class="error-banner">{error}</div>{/if}

{#if school}
	<section class="round-stack">
		{#each roundGroups as group (group.key)}
			<article class="round-card card">
				<header>
					<span class="round-badge">{group.label}</span>
					<div>
						<h2>{group.label} 클리닉</h2>
						<p>
							일정 {group.rounds.length}건 · 학생 {group.targets.length}명
						</p>
					</div>
					<span class="status-pill"
						>{group.targets.filter((target) => target.report?.status === 'submitted').length}/{group
							.targets.length} 제출</span
					>
				</header>
				<div class="target-list">
					<div class="schedule-list" aria-label={`${group.label} 일정`}>
						{#each group.rounds as round (round.id)}
							<span>
								{new Date(round.startTime).toLocaleString('ko-KR')}
								<button
									onclick={() => removeRound(round)}
									aria-label={`${round.roundLabel} 일정 삭제`}>×</button
								>
							</span>
						{/each}
					</div>
					<p class="target-heading">{group.label} 학생</p>
					{#each group.targets as target (target.id)}
						<div class="target-row">
							<a href={`/personal-project/aura/reports/${target.id}`}>
								<span class="target-avatar">{target.studentName.slice(0, 1)}</span>
								<strong>{target.studentName}</strong>
								<small
									>{new Date(target.clinicRound.startTime).toLocaleTimeString('ko-KR', {
										hour: '2-digit',
										minute: '2-digit'
									})}</small
								>
								<span class={`status-pill ${target.report?.status ?? ''}`}
									>{target.report?.status === 'submitted'
										? '제출 완료'
										: target.report
											? '작성 중'
											: '미작성'}</span
								>
								<i>리포트 열기 →</i>
							</a>
							<button
								onclick={() => removeTarget(target.id, target.studentName)}
								aria-label={`${target.studentName} 삭제`}>×</button
							>
						</div>
					{/each}
					{#if addingRoundId === group.rounds[0]?.id}
						<form
							class="add-target"
							onsubmit={(event) => {
								event.preventDefault();
								if (group.rounds[0]) addTarget(group.rounds[0]);
							}}
						>
							<input bind:value={newStudentName} placeholder="학생 이름" />
							<button class="primary-button">추가</button>
							<button type="button" class="ghost-button" onclick={() => (addingRoundId = null)}
								>취소</button
							>
						</form>
					{:else}
						<button class="add-button" onclick={() => (addingRoundId = group.rounds[0]?.id ?? null)}
							>＋ 학생 이름 추가</button
						>
					{/if}
				</div>
			</article>
		{:else}
			<div class="empty card">
				<strong>아직 회차가 없습니다.</strong>
				<p>클리닉 홈의 새 회차 버튼이나 주간 시간표에서 등록할 수 있습니다.</p>
				<a class="primary-button" href="/personal-project/aura">회차 등록하러 가기</a>
			</div>
		{/each}
	</section>
{/if}

<style>
	.back {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}
	.round-stack {
		display: grid;
		gap: 16px;
	}
	.round-card {
		overflow: hidden;
	}
	.round-card > header {
		padding: 18px 22px;
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 13px;
		background: #f7f5ef;
		border-bottom: 1px solid var(--pp-line);
	}
	.delete-round {
		padding: 7px 9px;
		border: 1px solid #e3b9ad;
		border-radius: 7px;
		background: #fff6f2;
		color: #a74b36;
		font-size: 8px;
		font-weight: 700;
		cursor: pointer;
	}
	.round-badge {
		min-width: 58px;
		height: 38px;
		padding: 0 12px;
		display: grid;
		place-items: center;
		border-radius: 999px;
		background: var(--pp-sage-dark);
		color: white;
		font:
			700 16px Georgia,
			serif;
	}
	h2 {
		margin: 0;
		font:
			500 17px Georgia,
			'Noto Sans KR',
			serif;
	}
	header p {
		margin: 4px 0 0;
		color: var(--pp-muted);
		font-size: 9px;
	}
	.target-list {
		padding: 3px 20px 12px;
	}
	.target-heading {
		margin: 11px 2px 3px;
		color: var(--pp-muted);
		font-size: 9px;
		font-weight: 700;
	}
	.schedule-list {
		padding: 9px 0 3px;
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}
	.schedule-list > span {
		padding: 5px 6px 5px 9px;
		display: inline-flex;
		align-items: center;
		gap: 5px;
		border-radius: 999px;
		background: #f3f1eb;
		color: var(--pp-muted);
		font-size: 8px;
	}
	.schedule-list button {
		width: 18px;
		height: 18px;
		padding: 0;
		border: 0;
		border-radius: 50%;
		background: #fff;
		color: #a74b36;
		cursor: pointer;
	}
	.target-row {
		display: flex;
		align-items: center;
		border-bottom: 1px solid var(--pp-line);
	}
	.target-row > a {
		min-width: 0;
		flex: 1;
		padding: 12px 2px;
		display: grid;
		grid-template-columns: auto 1fr auto auto auto;
		align-items: center;
		gap: 11px;
		color: inherit;
		text-decoration: none;
	}
	.target-avatar {
		width: 31px;
		height: 31px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #e6ebe5;
		color: var(--pp-sage-dark);
		font-size: 11px;
		font-weight: 700;
	}
	.target-row strong {
		font-size: 11px;
	}
	.target-row small {
		color: var(--pp-muted);
		font-size: 8px;
	}
	.target-row i {
		color: var(--pp-sage-dark);
		font-size: 9px;
		font-style: normal;
		font-weight: 700;
	}
	.target-row > button {
		width: 28px;
		height: 28px;
		border: 0;
		border-radius: 6px;
		background: none;
		color: #a86755;
		font-size: 17px;
		cursor: pointer;
	}
	.add-button {
		margin-top: 10px;
		padding: 9px;
		border: 0;
		background: none;
		color: var(--pp-sage-dark);
		font-size: 10px;
		font-weight: 700;
		cursor: pointer;
	}
	.add-target {
		padding: 12px 0 0;
		display: flex;
		gap: 7px;
	}
	.add-target input {
		min-width: 0;
		flex: 1;
		border: 1px solid var(--pp-line);
		border-radius: 8px;
		font-size: 11px;
	}
	.empty {
		padding: 70px;
		text-align: center;
	}
	.empty p {
		margin: 7px 0 18px;
		color: var(--pp-muted);
		font-size: 10px;
	}
	.empty a {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}
	@media (max-width: 650px) {
		.target-row > a {
			grid-template-columns: auto 1fr auto;
		}
		.target-row i {
			display: none;
		}
	}
</style>
