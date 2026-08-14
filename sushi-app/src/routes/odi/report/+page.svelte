<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";

	import { session, type OdiSession } from "$lib/odi/stores";
	import { formatDateTime, formatKoreanDuration, scoreGrade } from "$lib/odi/components/report/reportUtils";
	import { chair_alt, podium, school, voice_selection } from "$lib/odi/icons";

	let sessions = $state<OdiSession[]>([]);
	let loading = $state(true);
	let errorMessage = $state("");
	let query = $state("");
	let sortOrder = $state<"recent" | "score">("recent");
	let deletingId = $state<string | null>(null);

	const completedSessions = $derived.by(() => {
		const normalized = query.trim().toLowerCase();
		return sessions
			.filter((item) => item.state === "completed" && item.feedback)
			.filter((item) => !normalized || titleFor(item).toLowerCase().includes(normalized))
			.toSorted((left, right) => sortOrder === "score"
				? scoreFor(right) - scoreFor(left) || dateFor(right).localeCompare(dateFor(left))
				: dateFor(right).localeCompare(dateFor(left)));
	});

	const summary = $derived.by(() => {
		const scores = completedSessions.map(scoreFor).filter((score) => score > 0);
		const totalSeconds = completedSessions.reduce((sum, item) => sum + durationFor(item), 0);
		return {
			average: scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0,
			best: scores.length ? Math.max(...scores) : 0,
			totalSeconds
		};
	});

	function titleFor(item: OdiSession) {
		const environment = item.template?.environment ?? {};
		return item.template?.type === "interview"
			? environment.position || environment.company_name || "면접 연습"
			: environment.title || "제목 없는 발표";
	}

	function scoreFor(item: OdiSession) {
		return Number((item.feedback as any)?.score?.overall_score ?? 0);
	}

	function durationFor(item: OdiSession) {
		const duration = (item.feedback as any)?.duration ?? {};
		return Number(duration.actual_seconds ?? 0) + Number(duration.qa_seconds ?? 0);
	}

	function dateFor(item: OdiSession) {
		return item.ended_at ?? item.created_at ?? "";
	}

	function detailsFor(item: OdiSession) {
		const environment = item.template?.environment ?? {};
		if (item.template?.type === "interview") {
			return `면접 ${environment.duration_minutes ?? 0}분 · 면접관 ${environment.interviewer_count ?? 0}인`;
		}
		return `발표 ${environment.duration_minutes ?? 0}분 · Q&A ${environment.question_count ?? 0}개`;
	}

	function audienceFor(item: OdiSession) {
		const audience = item.template?.audience ?? {};
		return item.template?.type === "interview"
			? environmentText(item, "interview_context")
			: `청중 ${audience.audience_count ?? 0}인`;
	}

	function environmentText(item: OdiSession, key: string) {
		return String((item.template?.environment ?? {})[key] ?? "설정 없음");
	}

	function iconFor(item: OdiSession) {
		if (item.template?.type === "interview") return voice_selection;
		const place = environmentText(item, "place");
		if (place.includes("학회")) return school;
		if (place.includes("강의")) return chair_alt;
		return podium;
	}

	function feedbackSummary(item: OdiSession) {
		return String((item.feedback as any)?.ai_insight?.description ?? "세부 피드백을 확인해 보세요.");
	}

	async function load() {
		loading = true;
		errorMessage = "";
		try {
			sessions = await session.listMySessions(200);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "세션 리포트를 불러오지 못했습니다.";
		} finally {
			loading = false;
		}
	}

	async function deleteReport(item: OdiSession) {
		if (!confirm(`“${titleFor(item)}” 리포트를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`)) return;
		deletingId = item.session_id;
		try {
			await session.deleteSession(item.session_id);
			sessions = sessions.filter((sessionItem) => sessionItem.session_id !== item.session_id);
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : "리포트 삭제에 실패했습니다.";
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
		<p class="subtitle">완료한 발표와 면접 연습의 결과를 한곳에서 확인하세요.</p>
	</header>

	<section class="summary-grid" aria-label="리포트 통계">
		<article class="stat-card score"><div><span>▥</span><div><strong>나의 평균 점수</strong><small>최고 점수 {summary.best}점</small></div></div><b>{summary.average}<em>점</em></b></article>
		<article class="stat-card time"><div><span>♨</span><div><strong>총 연습 시간</strong><small>완료된 세션 기준</small></div></div><b>{formatKoreanDuration(summary.totalSeconds)}</b></article>
	</section>

	<section class="report-list">
		<div class="toolbar"><select bind:value={sortOrder} aria-label="정렬"><option value="recent">최신순</option><option value="score">점수 높은 순</option></select><label><span class="sr-only">세션 이름 검색</span><input bind:value={query} placeholder="세션 이름 검색" /></label></div>
		<div class="table-head"><span>유형</span><span>세션 정보</span><span>소요 시간</span><span>점수</span><span>피드백 요약</span><span>날짜</span><span></span></div>
		{#if loading}
			<div class="state">리포트를 불러오는 중입니다.</div>
		{:else if errorMessage}
			<div class="state error">{errorMessage}<button type="button" onclick={load}>다시 시도</button></div>
		{:else if completedSessions.length === 0}
			<div class="state">아직 완료된 세션 리포트가 없습니다.</div>
		{:else}
			<div class="rows">
				{#each completedSessions as item (item.session_id)}
					<article class="report-row">
						<div class="type"><img src={iconFor(item)} alt="" /><span>{item.template?.type === "interview" ? "면접" : "발표"}</span></div>
						<div class="info"><strong>{titleFor(item)}</strong><small>{detailsFor(item)} · {audienceFor(item)}</small></div>
						<div>{formatKoreanDuration(durationFor(item))}</div>
						<div class="score-value"><strong>{scoreFor(item)}</strong><small class:good={scoreFor(item) >= 80} class:normal={scoreFor(item) >= 65 && scoreFor(item) < 80}>{scoreGrade(scoreFor(item))}</small></div>
						<p class="feedback">{feedbackSummary(item)}</p>
						<time>{formatDateTime(dateFor(item))}</time>
						<div class="actions"><button type="button" onclick={() => goto(`/odi/report/${item.session_id}`)}>자세히 보기</button><button class="delete" type="button" disabled={deletingId === item.session_id} onclick={() => deleteReport(item)}>{deletingId === item.session_id ? "삭제 중" : "삭제"}</button></div>
					</article>
				{/each}
			</div>
		{/if}
	</section>
</main>

<style>
	.report-list-page { min-height:100vh; padding:42px 52px 64px; background:var(--surface); color:var(--text-primary); }.eyebrow{margin:0 0 20px;color:var(--primary);font-size:14px;font-weight:700;letter-spacing:.12em;text-transform:uppercase}h1{margin:0;font-size:30px}.subtitle{margin:10px 0 32px;color:var(--text-secondary)}.summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.stat-card{display:flex;align-items:end;justify-content:space-between;min-height:136px;padding:24px 28px;border-radius:14px;background:white;box-shadow:0 2px 10px #00000012}.stat-card>div{display:flex;align-items:center;gap:16px}.stat-card span{display:grid;place-items:center;width:48px;height:48px;border-radius:10px;font-size:26px}.stat-card.score span{background:#effbd7;color:#8dc600}.stat-card.time span{background:#eef1ff;color:#7185ed}.stat-card strong,.stat-card small{display:block}.stat-card small{margin-top:6px;color:var(--text-secondary)}.stat-card>b{font-size:34px}.stat-card em{margin-left:4px;font-size:17px;font-style:normal;font-weight:500}.report-list{margin-top:38px}.toolbar{display:flex;justify-content:flex-end;gap:12px;margin-bottom:16px}.toolbar select,.toolbar input{height:42px;padding:0 13px;border:1px solid var(--cool-grey-light-active);border-radius:8px;background:#fff;font:inherit}.toolbar input{width:270px}.table-head,.report-row{display:grid;grid-template-columns:86px minmax(250px,1.6fr) 100px 90px minmax(180px,1.2fr) 145px 165px;gap:18px;align-items:center}.table-head{padding:16px 14px;border-bottom:2px solid var(--cool-grey-light-active);color:var(--text-secondary);font-size:13px;font-weight:700}.report-row{padding:20px 14px;border-bottom:1px solid var(--cool-grey-light-active);font-size:14px}.type{display:flex;flex-direction:column;gap:6px;align-items:flex-start;color:#5426c7;font-weight:700}.type img{width:42px;height:42px;padding:8px;border-radius:8px;background:#f0efff}.info{display:flex;flex-direction:column;gap:7px;min-width:0}.info strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px}.info small,time,.feedback{color:var(--text-secondary);font-size:12px}.feedback{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.5}.score-value{display:flex;align-items:center;gap:6px}.score-value small{padding:4px 6px;border-radius:6px;background:#f1f2f5;color:#666}.score-value small.good{background:#e8f8d2;color:#65a000}.score-value small.normal{background:#edf0ff;color:#4f5ac7}.actions{display:flex;gap:7px}.actions button,.state button{height:34px;padding:0 10px;border:1px solid var(--cool-grey-light-active);border-radius:7px;background:white;font:inherit;font-size:12px;font-weight:700;cursor:pointer}.actions .delete{color:#a64a4a}.state{display:flex;min-height:170px;flex-direction:column;align-items:center;justify-content:center;gap:12px;color:var(--text-secondary)}.state.error{color:#b44343}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:1200px){.table-head{display:none}.report-row{grid-template-columns:72px 1fr auto;gap:13px}.report-row>div:nth-child(3),.report-row>.feedback,.report-row>time{display:none}.actions{grid-column:2/4}.summary-grid{grid-template-columns:1fr}}@media(max-width:640px){.report-list-page{padding:28px 20px}.toolbar{justify-content:stretch;flex-wrap:wrap}.toolbar label{flex:1}.toolbar input{box-sizing:border-box;width:100%}.stat-card{padding:20px}.stat-card>b{font-size:25px}}
</style>
