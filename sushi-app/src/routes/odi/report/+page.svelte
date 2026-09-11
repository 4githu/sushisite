<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { session, type OdiSession } from '$lib/odi/stores';
	import { scoreGrade } from '$lib/odi/components/report/reportUtils';
	import {
		figmaChevronDown,
		figmaClose,
		figmaGroup,
		figmaLeaderboard,
		figmaModeHeat,
		figmaSchedule,
		figmaSearch,
		figmaTemplateInterview,
		figmaTemplatePresentation,
		figmaTemplateSeminar
	} from '$lib/odi/icons';

	const PAGE_SIZE = 5;
	let sessions = $state<OdiSession[]>([]),
		loading = $state(true),
		errorMessage = $state(''),
		query = $state('');
	let sortOrder = $state<'recent' | 'score'>('recent'),
		deletingId = $state<string | null>(null),
		currentPage = $state(1);
	const completedSessions = $derived.by(() => {
		const q = query.trim().toLowerCase();
		return sessions
			.filter((item) => item.state === 'completed' && item.feedback)
			.filter((item) => !q || titleFor(item).toLowerCase().includes(q))
			.toSorted((a, b) =>
				sortOrder === 'score'
					? scoreFor(b) - scoreFor(a) || dateFor(b).localeCompare(dateFor(a))
					: dateFor(b).localeCompare(dateFor(a))
			);
	});
	const pageCount = $derived(Math.max(1, Math.ceil(completedSessions.length / PAGE_SIZE)));
	const pagedSessions = $derived(
		completedSessions.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
	);
	const summary = $derived.by(() => {
		const scores = completedSessions.map(scoreFor).filter((v) => v > 0),
			totalSeconds = completedSessions.reduce((sum, item) => sum + durationFor(item), 0);
		return {
			average: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0,
			best: scores.length ? Math.max(...scores) : 0,
			totalSeconds
		};
	});
	$effect(() => {
		query;
		sortOrder;
		currentPage = 1;
	});
	function env(item: OdiSession) {
		return item.template?.environment ?? {};
	}
	function titleFor(item: OdiSession) {
		const e = env(item);
		return item.template?.type === 'interview'
			? e.position || e.company_name || '면접 연습'
			: e.title || '제목 없는 발표';
	}
	function scoreFor(item: OdiSession) {
		return Number((item.feedback as any)?.score?.overall_score ?? 0);
	}
	function durationFor(item: OdiSession) {
		const d = (item.feedback as any)?.duration ?? {};
		return Number(d.actual_seconds ?? 0) + Number(d.qa_seconds ?? 0);
	}
	function dateFor(item: OdiSession) {
		return item.ended_at ?? item.created_at ?? '';
	}
	function dateText(value: string) {
		const d = new Date(value);
		if (Number.isNaN(d.getTime())) return '-';
		return `${d.getFullYear()}.${d.getMonth() + 1}.${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
	}
	function durationText(seconds: number) {
		const minutes = Math.max(0, Math.round(seconds / 60));
		return minutes < 60 ? `${minutes}분` : `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
	}
	function detailsFor(item: OdiSession) {
		const e = env(item);
		return item.template?.type === 'interview'
			? `면접 ${e.duration_minutes ?? 0}분`
			: `발표 ${e.duration_minutes ?? 0}분 · Q&A ${e.question_count ?? 0}개`;
	}
	function audienceFor(item: OdiSession) {
		return item.template?.type === 'interview'
			? `면접관 ${env(item).interviewer_count ?? 0}인`
			: `청중 ${item.template?.audience?.audience_count ?? 0}인`;
	}
	function iconFor(item: OdiSession) {
		if (item.template?.type === 'interview') return figmaTemplateInterview;
		const place = String(env(item).place ?? '');
		return place.includes('세미나') || place.includes('강의')
			? figmaTemplateSeminar
			: figmaTemplatePresentation;
	}
	function feedbackSummary(item: OdiSession) {
		return String(
			(item.feedback as any)?.ai_insight?.description ?? '세부 피드백을 확인해 보세요.'
		);
	}
	async function load() {
		loading = true;
		errorMessage = '';
		try {
			sessions = await session.listMySessions(200);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '세션 리포트를 불러오지 못했습니다.';
		} finally {
			loading = false;
		}
	}
	async function deleteReport(item: OdiSession) {
		if (!confirm(`“${titleFor(item)}” 리포트를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;
		deletingId = item.session_id;
		try {
			await session.deleteSession(item.session_id);
			sessions = sessions.filter((row) => row.session_id !== item.session_id);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : '리포트 삭제에 실패했습니다.';
		} finally {
			deletingId = null;
		}
	}
	onMount(load);
</script>

<main class="report-list-page">
	<header>
		<p class="eyebrow">Report</p>
		<h1>세션 리포트</h1>
	</header>
	<section class="summary-grid" aria-label="리포트 통계">
		<article class="stat-card score">
			<div class="stat-label">
				<span class="stat-icon"><img src={figmaLeaderboard} alt="" /></span>
				<div><strong>나의 평균 점수</strong><small>최고 점수 {summary.best}점</small></div>
			</div>
			<div class="stat-value"><b>{summary.average}</b><span>점</span></div>
		</article>
		<article class="stat-card time">
			<div class="stat-label">
				<span class="stat-icon"><img src={figmaModeHeat} alt="" /></span>
				<div><strong>총 연습 시간</strong><small>연속 기록 갱신 중!</small></div>
			</div>
			<div class="time-value">{durationText(summary.totalSeconds)}</div>
		</article>
	</section>
	<section class="report-list">
		<div class="toolbar">
			<label class="sort-box"
				><span class="sr-only">정렬</span><select bind:value={sortOrder}
					><option value="recent">최신순</option><option value="score">점수 높은 순</option></select
				><span class="icon-24"><img src={figmaChevronDown} alt="" /></span></label
			><label class="search-box"
				><span class="sr-only">세션 이름 검색</span><input
					bind:value={query}
					placeholder="세션 이름 검색"
				/><span class="icon-24"><img src={figmaSearch} alt="" /></span></label
			>
		</div>
		<div class="table-head">
			<span>유형</span><span>세션 정보</span><span>소요 시간</span><span>점수</span><span
				>피드백 요약</span
			><span>날짜</span><span></span>
		</div>
		{#if loading}<div class="state">리포트를 불러오는 중입니다.</div>{:else if errorMessage}<div
				class="state error"
			>
				{errorMessage}<button type="button" onclick={load}>다시 시도</button>
			</div>{:else if completedSessions.length === 0}<div class="state">
				아직 완료된 세션 리포트가 없습니다.
			</div>{:else}<div class="rows">
				{#each pagedSessions as item (item.session_id)}<article class="report-row">
						<div class="type">
							<span class="type-icon"><img src={iconFor(item)} alt="" /></span>
						</div>
						<div class="info">
							<div class="info-title">
								<span class:interview={item.template?.type === 'interview'} class="type-chip"
									>{item.template?.type === 'interview' ? '면접' : '발표'}</span
								><strong>{titleFor(item)}</strong>
							</div>
							<small
								><span
									><span class="icon-18"><img src={figmaSchedule} alt="" /></span>{detailsFor(
										item
									)}</span
								><span
									><span class="icon-18"><img src={figmaGroup} alt="" /></span>{audienceFor(
										item
									)}</span
								></small
							>
						</div>
						<div class="duration">
							<strong>{durationText(durationFor(item))}</strong><small
								>{scoreFor(item) >= 80
									? '우수한 집중'
									: scoreFor(item) >= 65
										? '안정적인 진행'
										: '집중 연습 필요'}</small
							>
						</div>
						<div class="score-value">
							<strong>{scoreFor(item)}점</strong><small
								class:good={scoreFor(item) >= 80}
								class:normal={scoreFor(item) >= 65 && scoreFor(item) < 80}
								>{scoreGrade(scoreFor(item))}</small
							>
						</div>
						<p class="feedback">{feedbackSummary(item)}</p>
						<time>{dateText(dateFor(item))}</time>
						<div class="actions">
							<button
								class="detail"
								type="button"
								onclick={() => goto(`/odi/report/${item.session_id}`)}>자세히 보기</button
							><button
								class="delete"
								type="button"
								aria-label={`${titleFor(item)} 리포트 삭제`}
								disabled={deletingId === item.session_id}
								onclick={() => void deleteReport(item)}
								><span class="icon-24"><img src={figmaClose} alt="" /></span></button
							>
						</div>
					</article>{/each}
			</div>{/if}
		{#if pageCount > 1}<nav class="pagination" aria-label="페이지 이동">
				{#each Array(pageCount) as _, index}<button
						class:active={currentPage === index + 1}
						type="button"
						onclick={() => (currentPage = index + 1)}>{index + 1}</button
					>{/each}
			</nav>{/if}
	</section>
</main>

<style>
	:global(*) {
		box-sizing: border-box;
	}
	.report-list-page {
		min-height: 100vh;
		width: 100%;
		padding: 36px 45px 40px 51px;
		background: #fff;
		color: #030812;
	}
	p,
	h1 {
		margin: 0;
	}
	.eyebrow {
		color: #03f;
		font-size: 20px;
		font-weight: 500;
		letter-spacing: -0.2px;
	}
	.report-list-page h1 {
		margin-top: 24px;
		font-size: 42px;
		font-weight: 700;
		letter-spacing: -0.42px;
		line-height: 1.2;
	}
	.summary-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 16px;
		margin-top: 24px;
	}
	.stat-card {
		display: flex;
		height: 136px;
		align-items: center;
		justify-content: space-between;
		padding: 11px 40px;
		border-radius: 8px;
		color: #fff;
		overflow: hidden;
	}
	.stat-card.score {
		background: linear-gradient(
			114.48deg,
			#807dfe 14.69%,
			#01033e 30.38%,
			#01033e 63.29%,
			#0308a4 104.39%
		);
	}
	.stat-card.time {
		background: linear-gradient(
			126.84deg,
			#0308a4 38%,
			#01033e 71.41%,
			#01033e 100.3%,
			#807dfe 115.62%
		);
	}
	.stat-label {
		display: flex;
		align-items: center;
		gap: 28px;
	}
	.stat-icon {
		display: block;
		width: 80px;
		height: 80px;
		flex: none;
	}
	.stat-icon img {
		display: block;
		width: 100%;
		height: 100%;
	}
	.stat-label strong,
	.stat-label small {
		display: block;
		line-height: 1.35;
	}
	.stat-label strong {
		font-size: 22px;
		font-weight: 500;
		letter-spacing: -0.22px;
	}
	.stat-label small {
		margin-top: 4px;
		color: #caced9;
		font-size: 18px;
	}
	.stat-value {
		display: flex;
		align-items: flex-end;
		gap: 4px;
	}
	.stat-value b {
		color: #cfff5e;
		font-family: 'Archivo Black', Pretendard, sans-serif;
		font-size: 64px;
		line-height: 1;
	}
	.stat-value span {
		padding-bottom: 7px;
		font-size: 24px;
	}
	.time-value {
		color: #cfff5e;
		font-size: 42px;
		font-weight: 700;
		letter-spacing: -0.42px;
	}
	.report-list {
		margin-top: 20px;
	}
	.toolbar {
		display: flex;
		height: 50px;
		justify-content: flex-end;
		gap: 8px;
		margin-bottom: 8px;
	}
	.sort-box,
	.search-box {
		position: relative;
		display: flex;
		height: 50px;
		align-items: center;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
	}
	.sort-box {
		width: 142px;
	}
	.search-box {
		width: 280px;
	}
	select,
	input {
		width: 100%;
		height: 100%;
		border: 0;
		outline: 0;
		background: transparent;
		color: #81838f;
		font: inherit;
		font-size: 18px;
		appearance: none;
	}
	select {
		padding: 0 48px 0 20px;
	}
	input {
		padding: 0 52px 0 20px;
	}
	.sort-box > .icon-24,
	.search-box > .icon-24 {
		position: absolute;
		right: 16px;
		pointer-events: none;
	}
	.table-head,
	.report-row {
		display: grid;
		grid-template-columns: 52px minmax(360px, 1fr) 84px 64px minmax(260px, 327px) 155px 185px;
		gap: 18px;
		align-items: center;
	}
	.table-head {
		height: 47px;
		padding: 0 30px;
		border-bottom: 1px solid #d4d6e2;
		color: #81838f;
		font-size: 14px;
		font-weight: 500;
	}
	.report-row {
		min-height: 108px;
		padding: 14px 30px;
		border-bottom: 1px solid #d4d6e2;
		font-size: 14px;
	}
	.type {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.type-icon {
		width: 48px;
		height: 48px;
		flex: none;
	}
	.type-icon img {
		display: block;
		width: 100%;
		height: 100%;
	}
	.type-chip {
		padding: 2px 8px;
		border-radius: 999px;
		background: rgba(128, 125, 254, 0.15);
		color: #4522c4;
		font-size: 14px;
	}
	.type-chip.interview {
		background: rgba(207, 255, 94, 0.28);
		color: #466700;
	}
	.info {
		min-width: 0;
		display: grid;
		gap: 8px;
	}
	.info-title {
		display: flex;
		min-width: 0;
		align-items: center;
		gap: 8px;
	}
	.info strong {
		min-width: 0;
		overflow: hidden;
		font-size: 18px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.info small {
		display: flex;
		gap: 12px;
		color: #81838f;
		font-size: 13px;
	}
	.info small > span {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.duration,
	.score-value {
		display: grid;
		gap: 5px;
	}
	.duration strong,
	.score-value strong {
		font-size: 16px;
	}
	.duration small,
	.score-value small {
		color: #81838f;
		font-size: 12px;
	}
	.score-value small {
		justify-self: start;
		padding: 3px 7px;
		border-radius: 999px;
		background: #f1f2f5;
	}
	.score-value small.good {
		background: #edffd1;
		color: #5c8500;
	}
	.score-value small.normal {
		background: #eeeeff;
		color: #4522c4;
	}
	.feedback {
		display: -webkit-box;
		overflow: hidden;
		color: #81838f;
		font-size: 14px;
		line-height: 1.45;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
	}
	time {
		color: #81838f;
		font-size: 14px;
	}
	.actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 12px;
	}
	.actions .detail {
		width: 116px;
		height: 42px;
		border: 1px solid #03f;
		border-radius: 8px;
		background: #03f;
		color: #fff;
		font: inherit;
		font-size: 16px;
		cursor: pointer;
	}
	.actions .delete {
		display: grid;
		width: 28px;
		height: 42px;
		padding: 0;
		place-items: center;
		border: 0;
		background: transparent;
		cursor: pointer;
	}
	.icon-18,
	.icon-24 {
		display: inline-grid;
		flex: 0 0 auto;
		place-items: center;
	}
	.icon-18 {
		width: 18px;
		height: 18px;
	}
	.icon-24 {
		width: 24px;
		height: 24px;
	}
	.icon-18 img,
	.icon-24 img {
		display: block;
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.pagination {
		display: flex;
		justify-content: center;
		gap: 6px;
		padding-top: 18px;
	}
	.pagination button {
		width: 30px;
		height: 30px;
		border: 0;
		border-radius: 6px;
		background: transparent;
		color: #81838f;
		font: inherit;
	}
	.pagination button.active {
		background: #03f;
		color: #fff;
	}
	.state {
		min-height: 300px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 12px;
		color: #81838f;
	}
	.state.error {
		color: #b44343;
	}
	.state button {
		height: 40px;
		padding: 0 16px;
		border: 1px solid #d4d6e2;
		border-radius: 8px;
		background: #fff;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
	}
	@media (max-width: 1200px) {
		.summary-grid {
			grid-template-columns: 1fr;
		}
		.table-head {
			display: none;
		}
		.report-row {
			grid-template-columns: 88px minmax(260px, 1fr) 100px 150px;
		}
		.duration,
		.feedback {
			display: none;
		}
		.actions {
			grid-column: 4;
		}
		.report-list {
			overflow-x: auto;
		}
	}
	@media (max-width: 720px) {
		.report-list-page {
			padding: 26px 20px 40px;
		}
		.summary-grid {
			margin-top: 20px;
		}
		.stat-card {
			height: 120px;
			padding: 16px;
		}
		.stat-icon {
			width: 64px;
			height: 64px;
		}
		.stat-label {
			gap: 14px;
		}
		.stat-label strong {
			font-size: 18px;
		}
		.stat-label small {
			font-size: 14px;
		}
		.stat-value b {
			font-size: 48px;
		}
		.time-value {
			font-size: 30px;
		}
		.toolbar {
			height: auto;
		}
		.sort-box {
			width: 120px;
		}
		.search-box {
			flex: 1;
		}
		.report-row {
			grid-template-columns: 72px minmax(220px, 1fr) 100px;
		}
		.score-value,
		time {
			display: none;
		}
		.actions {
			grid-column: 3;
		}
	}
</style>
