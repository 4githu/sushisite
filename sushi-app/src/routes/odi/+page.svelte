<!-- src/routes/odi/+page.svelte -->
<script lang="ts">
	import { goto } from "$app/navigation";
	import { onMount } from "svelte";
	import { odiuser } from "$lib/odi/stores";
	import { session, type OdiSession } from "$lib/odi/stores/session";
	import Button from "$lib/odi/components/common/Button.svelte";

	import {
		blueright,
		down,
		notifications,
		schedule,
		leaderboard,
		wand_stars,
		mode_heat,
		audiance,
		goal,
		flag,
		trending_up,
		calendar_month,
		sprout,

	} from "$lib/odi/icons";

	type Evc = {
		E: number;
		V: number;
		C: number;
	};

	type RecentSession = {
		session_id: string;
		template_id: string;
		title: string;
		score: number;
		duration_seconds: number;
		audience_count: number;
		created_at: string;
		average_evc: Evc;
	};

	type EvcTrendPoint = {
		date: string;
		E: number;
		V: number;
		C: number;
	};

	type Training = {
		template_id: string;
		title: string;
		category: string;
		difficulty: string;
	};

	type HomeConfig = {
		owner_id?: string;
		updated_at?: string;
		profile: {
			nickname: string;
			level: string;
			level_icon: string;
			current_exp: number;
			next_level_exp: number;
			profile_image: string | null;
		};
		statistics: {
			session_count: number;
			practice_minutes: number;
			current_streak: number;
			best_streak: number;
		};
		dashboard: {
			average_score: number;
			best_skill: string;
			best_skill_score: number;
			best_skill_percentile: number;
		};
		favorite_templates: string[];
		recent_sessions: RecentSession[];
		evc_trend: EvcTrendPoint[];
		today_insight: {
			title: string;
			description: string;
		};
		current_goal: {
			title: string;
			current_score: number;
			target_score: number;
			remaining_sessions: number;
		};
		recommended_trainings: Training[];
	};

	const fallbackConfig: HomeConfig = {
		owner_id: "dev",
		updated_at: "2026-07-15T10:32:18Z",
		profile: {
			nickname: "리히어",
			level: "새싹 보이스",
			level_icon: "seed_voice",
			current_exp: 244,
			next_level_exp: 300,
			profile_image: sprout
		},
		statistics: {
			session_count: 18,
			practice_minutes: 412,
			current_streak: 5,
			best_streak: 12
		},
		dashboard: {
			average_score: 81,
			best_skill: "시선 분배",
			best_skill_score: 91,
			best_skill_percentile: 11
		},
		favorite_templates: ["template_7fd821", "template_a934af", "template_d392bc"],
		recent_sessions: [
			{
				session_id: "session_18",
				template_id: "template_7fd821",
				title: "제품 로드맵 발표 및 Q&A",
				score: 82,
				duration_seconds: 2273,
				audience_count: 6,
				created_at: "2026-07-16T14:00:00Z",
				average_evc: { E: 0.82, V: 0.74, C: 0.79 }
			},
			{
				session_id: "session_17",
				template_id: "template_2ab482",
				title: "분기 실적 리뷰 발표",
				score: 74,
				duration_seconds: 1118,
				audience_count: 10,
				created_at: "2026-07-09T18:00:00Z",
				average_evc: { E: 0.63, V: 0.58, C: 0.69 }
			},
			{
				session_id: "session_16",
				template_id: "template_81fa19",
				title: "마케팅 전략 기획안 발표",
				score: 68,
				duration_seconds: 1757,
				audience_count: 6,
				created_at: "2026-06-26T14:00:00Z",
				average_evc: { E: 0.57, V: 0.51, C: 0.61 }
			}
		],
		evc_trend: [
			{ date: "2026-06-08", E: 0.63, V: 0.58, C: 0.66 },
			{ date: "2026-06-10", E: 0.71, V: 0.62, C: 0.69 },
			{ date: "2026-06-12", E: 0.68, V: 0.71, C: 0.63 },
			{ date: "2026-06-14", E: 0.76, V: 0.74, C: 0.72 },
			{ date: "2026-06-16", E: 0.77, V: 0.73, C: 0.76 },
			{ date: "2026-06-18", E: 0.84, V: 0.79, C: 0.83 },
			{ date: "2026-06-20", E: 0.79, V: 0.76, C: 0.74 },
			{ date: "2026-06-22", E: 0.73, V: 0.70, C: 0.69 },
			{ date: "2026-06-24", E: 0.82, V: 0.81, C: 0.79 }
		],
		today_insight: {
			title: "설득은 말하는 사람의 신뢰에서 시작됩니다.",
			description: "좋은 발표는 청중이 믿고 따라올 수 있는 흐름을 만드는 것입니다."
		},
		current_goal: {
			title: "연속 5회 평균 점수 85점 달성",
			current_score: 86,
			target_score: 85,
			remaining_sessions: 4
		},
		recommended_trainings: [
			{ template_id: "training_01", title: "습관어 줄이기", category: "명확도 훈련", difficulty: "쉬움" },
			{ template_id: "training_02", title: "적정 말하기 속도 유지", category: "몰입도 훈련", difficulty: "보통" },
			{ template_id: "training_03", title: "Q&A 답변 구조 강화", category: "신뢰도 훈련", difficulty: "보통" }
		]
	};

	const config = $derived(($odiuser?.config ?? fallbackConfig) as HomeConfig);
	const profile = $derived(config.profile);
	const statistics = $derived(config.statistics);
	const dashboard = $derived(config.dashboard);
	let loadedRecentSessions = $state<RecentSession[] | null>(null);
	let loadedUserId = $state<string | null>(null);

	const recentSessions = $derived(loadedRecentSessions ?? config.recent_sessions ?? []);
	const evcTrend = $derived(config.evc_trend ?? []);
	const todayInsight = $derived(config.today_insight);
	const currentGoal = $derived(config.current_goal);
	const trainings = $derived(config.recommended_trainings ?? []);

	const expPercent = $derived(clampPercent((profile.current_exp / Math.max(profile.next_level_exp, 1)) * 100));
	const goalPercent = $derived(clampPercent((currentGoal.current_score / Math.max(currentGoal.target_score, 1)) * 100));

	const chartWidth = 620;
	const chartHeight = 170;
	const chartPaddingX = 28;
	const chartPaddingY = 14;

	const ePath = $derived(linePath(evcTrend, "E"));
	const vPath = $derived(linePath(evcTrend, "V"));
	const cPath = $derived(linePath(evcTrend, "C"));
	const chartLabels = $derived(evcTrend.filter((_, index) => index % 2 === 0 || index === evcTrend.length - 1));

	function clampPercent(value: number) {
		if (Number.isNaN(value)) return 0;
		return Math.max(0, Math.min(100, value));
	}

	function linePath(points: EvcTrendPoint[], key: keyof Evc) {
		if (points.length === 0) return "";

		return points
			.map((point, index) => {
				const x = chartPaddingX + (index / Math.max(points.length - 1, 1)) * (chartWidth - chartPaddingX * 2);
				const y = chartHeight - chartPaddingY - point[key] * (chartHeight - chartPaddingY * 2);
				return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
			})
			.join(" ");
	}

	function formatDateTime(value: string) {
		const date = value.slice(0, 10);
		const time = value.slice(11, 16);
		const [year, month, day] = date.split("-").map(Number);
		const weekday = ["일", "월", "화", "수", "목", "금", "토"][new Date(year, month - 1, day).getDay()];
		return `${year}.${month}.${day} (${weekday}) ${time}`;
	}

	function formatChartDate(value: string) {
		const [, month, day] = value.split("-");
		return `${Number(month)}/${Number(day)}`;
	}

	function formatDuration(seconds: number) {
		const min = Math.floor(seconds / 60);
		const sec = seconds % 60;
		return `${min}:${String(sec).padStart(2, "0")}`;
	}

	function scoreGrade(score: number) {
		if (score >= 80) return "우수";
		if (score >= 70) return "보통";
		return "개선";
	}

	function scoreGradeClass(score: number) {
		if (score >= 80) return "excellent";
		if (score >= 70) return "normal";
		return "weak";
	}

	function trainingDescription(training: Training) {
		if (training.title.includes("습관어")) return "자주 사용하는 추임새와 불필요한 반복 표현을 줄여 메시지를 더 명확하게 전달해요.";
		if (training.title.includes("속도")) return "말하기 속도를 안정적으로 유지하여 전달력을 높이도록 연습해요.";
		if (training.title.includes("Q&A")) return "두괄식으로 핵심을 먼저 말하고, 근거를 덧붙이는 답변 구조를 학습해요.";
		return "최근 세션 분석을 바탕으로 필요한 역량을 집중적으로 훈련해요.";
	}

	function categoryClass(category: string) {
		if (category.includes("명확")) return "clarity";
		if (category.includes("몰입")) return "engagement";
		if (category.includes("신뢰")) return "confidence";
		return "clarity";
	}

	function openSession(sessionId: string) {
		goto(`/odi/report/${sessionId}`);
	}

	function toRecentSession(item: OdiSession): RecentSession {
		const template = item.template ?? {};
		const feedback = item.feedback ?? {};
		const environment = template.environment ?? {};
		const audience = template.audience ?? {};
		const score = feedback.score ?? {};
		const duration = feedback.duration ?? {};

		return {
			session_id: item.session_id,
			template_id: item.template_id ?? "",
			title: environment.title ?? template.title ?? "제목 없는 세션",
			score: Number(score.overall_score ?? 0),
			duration_seconds: Number(duration.actual_seconds ?? (environment.duration_minutes ? environment.duration_minutes * 60 : 0)),
			audience_count: Number(audience.audience_count ?? 0),
			created_at: item.started_at ?? item.created_at,
			average_evc: { E: 0, V: 0, C: 0 }
		};
	}

	async function loadRecentSessions() {
		try {
			const sessions = await session.listMySessions(20);
			loadedRecentSessions = sessions
				.filter((item) => item.state === "completed")
				.map(toRecentSession);
		} catch {
			// API를 불러오지 못하면 저장된 대시보드 값을 사용합니다.
			loadedRecentSessions = null;
		}
	}

	onMount(() => {
		return odiuser.subscribe((user) => {
			if (user === null || user.user_id === loadedUserId) return;

			loadedUserId = user.user_id;
			void loadRecentSessions();
		});
	});

	function startTraining(templateId: string) {
		goto(`/odi/practice/${templateId}`);
	}
</script>

<main class="home-page">
	<header class="home-header">
		<div>
			<h1 class="text-title-main">좋은 아침이에요, {profile.nickname}님 ✋</h1>
			<p class="text-caption-main header-subtitle">꾸준한 연습이 자신감을 만듭니다. 오늘도 한 걸음 더 성장해요!</p>
		</div>

		<div class="header-actions">
			<button type="button" class="top-button clickable">
				<img src={calendar_month} alt="" />
				<span class="text-button">나의 일정</span>
			</button>

			<button type="button" class="top-button clickable">
				<img src={notifications} alt="" />
				<span class="text-button">알림</span>
			</button>
		</div>
	</header>

	<section class="summary-grid">
		<article class="summary-card profile-card">
			<div class="profile-image">
				{#if profile.profile_image}
					<img src={profile.profile_image} alt={`${profile.nickname} 프로필`} />
				{/if}
			</div>

			<div class="summary-text">
				<p class="text-body-active">호칭 {profile.nickname}</p>
				<div class="mini-progress">
					<span style={`width:${expPercent}%`}></span>
				</div>
				<p class="text-caption-medium">{profile.level}</p>
			</div>
		</article>

		<article class="summary-card">
			<img src={leaderboard} alt="" />
			<div class="summary-text">
				<p class="text-body-medium">나의 평균 점수</p>
				<strong>{dashboard.average_score}점</strong>
				<p class="text-caption-medium">지난 2주간 평균</p>
			</div>
		</article>

		<article class="summary-card">
			<img src={wand_stars} alt="" />
			<div class="summary-text">
				<p class="text-body-medium">나의 강점 스킬</p>
				<strong>{dashboard.best_skill}</strong>
				<p class="text-caption-medium">우수(상위 {dashboard.best_skill_percentile}%)</p>
			</div>
		</article>

		<article class="summary-card">
			<img src={mode_heat} alt="" />
			<div class="summary-text">
				<p class="text-body-medium">연속 연습</p>
				<strong>{statistics.current_streak}일</strong>
				<p class="text-caption-medium">연속 기록 갱신 중!</p>
			</div>
		</article>
	</section>

	<section class="dashboard-grid">
		<article class="panel recent-panel">
			<div class="panel-header">
				<h2 class="text-title-small">최근 세션</h2>
				<button type="button" class="link-button clickable" onclick={() => goto("/odi/report")}>
					<span class = "inline-flex items-center gap-1 items-center">
						전체 보기
						<img src={blueright} alt="" />
					</span>
				</button>
			</div>

			<div class="recent-list">
				{#each recentSessions.slice(0, 3) as session, index}
					<button
						type="button"
						class="recent-item clickable"
						class:selected={index === 0}
						onclick={() => openSession(session.session_id)}
					>
						<span class="rank">{index + 1}</span>

						<div class="recent-body">
							<strong>{session.title}</strong>

							<div class="recent-meta">
								<span class = "inline-flex items-center gap-1"> 
									<img src={calendar_month} alt="" />
									{formatDateTime(session.created_at)}</span>
								<span class = "inline-flex items-center gap-1">
									<img src={audiance} alt="" />
									{session.audience_count}인</span>
							</div>

							<div class="recent-meta">
								<span class = "inline-flex items-center gap-1"><img src={schedule} alt="" /> {formatDuration(session.duration_seconds)}</span>
							</div>
						</div>

						<div class="score-box">
							<strong>{session.score}</strong>
							<span class={scoreGradeClass(session.score)}>{scoreGrade(session.score)}</span>
						</div>
					</button>
				{/each}
			</div>
		</article>

		<article class="panel evc-panel">
			<div class="panel-header">
				<h2 class="text-title-small">E/V/C 요소 분석</h2>

				<button type="button" class="range-button clickable">
					<span class = "inline-flex items-center gap-1">
						최근 2주
						<img src={down} alt="" />
					</span>
				</button>
			</div>

			<div class="legend">
				<span><i class="dot engagement"></i>몰입도</span>
				<span><i class="dot confidence"></i>신뢰도</span>
				<span><i class="dot clarity"></i>명확도</span>
			</div>

			<div class="chart-wrap">
				<svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} role="img" aria-label="EVC 추세 그래프">
					<g class="grid-lines">
						<line x1={chartPaddingX} y1="20" x2={chartWidth - chartPaddingX} y2="20" />
						<line x1={chartPaddingX} y1="85" x2={chartWidth - chartPaddingX} y2="85" />
						<line x1={chartPaddingX} y1="150" x2={chartWidth - chartPaddingX} y2="150" />
					</g>

					<text x="0" y="24" class="axis-label">100</text>
					<text x="8" y="89" class="axis-label">50</text>
					<text x="16" y="154" class="axis-label">0</text>

					<path class="evc-area confidence-area" d={`${vPath} L ${chartWidth - chartPaddingX} ${chartHeight - chartPaddingY} L ${chartPaddingX} ${chartHeight - chartPaddingY} Z`} />
					<path class="evc-area engagement-area" d={`${ePath} L ${chartWidth - chartPaddingX} ${chartHeight - chartPaddingY} L ${chartPaddingX} ${chartHeight - chartPaddingY} Z`} />

					<path class="evc-line engagement-line" d={ePath} />
					<path class="evc-line confidence-line" d={vPath} />
					<path class="evc-line clarity-line" d={cPath} />
				</svg>

				<div class="chart-labels">
					{#each chartLabels as item}
						<span>{formatChartDate(item.date)}</span>
					{/each}
				</div>
			</div>

			<div class="analysis-box">
				<div class="trend-icon">
					<img src={trending_up} alt="" />
				</div>

				<div>
					<strong>전반적인 전달력이 꾸준히 향상하고 있어요!</strong>
					<p>몰입도와 신뢰도가 최근 눈에 띄게 개선되었어요. 시선 처리와 메시지 구조가 더 명확해진 영향이에요. 다음 단계로는 표현의 생동감을 올려 명확도를 성장한다면 설득력이 한층 강화될 거예요.</p>
				</div>
			</div>
		</article>

		<aside class="panel insight-panel">
			<h2 class="text-title-small">오늘의 인사이트</h2>

			<div class="insight-copy">
				<strong>{todayInsight.title}</strong>
				<span>— Aristotle</span>
				<p>{todayInsight.description}</p>
			</div>

			<div class="goal-area">
				<h3 class="text-title-xs">이번 주 목표</h3>

				<div class="goal-card">
					<span class="goal-title">
						<span class = "inline-flex items-center gap-1">
							<img src={goal} alt="" />
							{currentGoal.title}
						</span>
					</span>

					<div class="goal-progress">
						<span style={`width:${goalPercent}%`}></span>
					</div>

					<p class="goal-meta">현재 {currentGoal.current_score}점 · 남은 세션 {currentGoal.remaining_sessions}회</p>
				</div>
			</div>
		</aside>
	</section>

	<section class="panel training-panel">
		<div class="panel-header">
			<div class="training-heading">
				<h2 class="text-title-small">추천 훈련</h2>
				<p class="text-body-medium">최근 세션 분석을 바탕으로 맞춤 추천해드려요.</p>
			</div>

			<button type="button" class="link-button clickable" onclick={() => goto("/odi/practice")}>훈련하러 가기 ›</button>
		</div>

		<div class="training-grid">
			{#each trainings.slice(0, 3) as training}
				<article class="training-card">

					<div class="training-left">
						<div class="flag-icon">
							<img src={flag} alt="" />
						</div>

						<div class="training-content">
							<h3>{training.title}</h3>

							<p>{trainingDescription(training)}</p>

							<div class="chips">
								<span class={categoryClass(training.category)}>
									{training.category}
								</span>

								<span class="difficulty">
									난이도 : {training.difficulty}
								</span>
							</div>
						</div>
					</div>

					<Button
						variant="outline"
						size="sm"
						width="100px"
						onclick={() => startTraining(training.template_id)}
					>
						훈련 시작
					</Button>

				</article>
			{/each}
		</div>
	</section>
</main>

<style>
	.home-page {
		width: 100%;
		min-height: 100vh;
		padding: 36px 48px 44px;
		display: flex;
		flex-direction: column;
		gap: var(--space-5);
		background: var(--surface);
	}

	.home-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: var(--space-6);
	}

	.header-subtitle {
		margin-top: var(--space-2);
		color: var(--text-secondary);
	}

	.header-actions {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.top-button {
		width: 212px;
		height: 50px;
		padding: 0 var(--space-4);
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-secondary);
	}

	.top-icon {
		color: var(--text-secondary);
		font-size: 18px;
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: var(--space-4);
	}

	.summary-card {
		min-height: 136px;
		padding: 20px;
		display: flex;
		align-items: center;
		gap: 20px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.profile-card {
		gap: var(--space-4);
	}

	.profile-image {
		width: 80px;
		height: 80px;
		flex-shrink: 0;
		overflow: hidden;
		border: 2px solid #ff35d3;
		background: #ffe7fb;
	}

	.profile-image img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.summary-icon {
		width: 48px;
		height: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border-radius: var(--radius-sm);
		font-size: 26px;
		font-weight: var(--font-bold);
	}

	.summary-icon.lime {
		background: rgba(159, 227, 0, 0.15);
		color: #9fe300;
	}

	.summary-icon.purple {
		background: rgba(128, 125, 254, 0.15);
		color: #4522c4;
	}

	.summary-icon.yellow {
		background: rgba(255, 215, 54, 0.3);
		color: #ffd736;
	}

	.summary-text {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
		color: var(--text-primary);
	}

	.summary-text strong {
		font-size: 24px;
		font-weight: var(--font-bold);
		color: var(--brand-black);
	}

	.summary-text p:last-child {
		color: var(--text-secondary);
	}

	.mini-progress {
		width: 235px;
		height: 21px;
		overflow: hidden;
		border-radius: var(--radius-sm);
		background: var(--cool-grey-light-active);
	}

	.mini-progress span {
		display: block;
		height: 100%;
		border-radius: var(--radius-sm);
		background: var(--primary);
	}

	.dashboard-grid {
		display: grid;
		grid-template-columns: 538px minmax(0, 1fr) 297px;
		gap: var(--space-5);
		align-items: stretch;
	}

	.panel {
		border-radius: var(--radius-md);
		background: var(--surface);
		box-shadow: 0 0 8px rgba(0, 0, 0, 0.15);
		overflow: hidden;
	}

	.recent-panel,
	.evc-panel,
	.insight-panel {
		min-height: 486px;
		padding: 22px;
	}

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--space-4);
	}

	.link-button {
		display: inline-flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--primary);
		font-size: 16px;
		font-weight: var(--font-medium);
	}

	.recent-list {
		margin-top: var(--space-5);
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.recent-item {
		width: 100%;
		min-height: 120px;
		padding: var(--space-4);
		display: flex;
		align-items: center;
		gap: 22px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
		text-align: left;
	}

	.recent-item.selected {
		border-color: var(--primary);
	}

	.rank {
		width: 28px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border-radius: 5.6px;
		background: var(--primary);
		color: var(--text-on-primary);
		font-size: 14px;
		font-weight: var(--font-medium);
	}

	.recent-item:not(.selected) .rank {
		background: var(--text-secondary);
	}

	.recent-body {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.recent-body strong {
		color: var(--primary);
		font-size: 18px;
		font-weight: var(--font-bold);
	}

	.recent-item:not(.selected) .recent-body strong {
		color: var(--text-primary);
	}

	.recent-meta {
		display: flex;
		align-items: center;
		gap: 28px;
		color: var(--text-secondary);
		font-size: 16px;
		font-weight: var(--font-medium);
	}

	.score-box {
		width: 68px;
		height: 80px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 2px;
		flex-shrink: 0;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.score-box strong {
		color: var(--primary);
		font-size: 22px;
		font-weight: var(--font-bold);
		line-height: 140%;
	}

	.score-box span {
		min-width: 42px;
		height: 24px;
		padding: 2px 8px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--radius-full);
		font-size: 14px;
		font-weight: var(--font-medium);
	}

	.score-box .excellent {
		background: rgba(68, 198, 153, 0.15);
		color: #44c699;
	}

	.score-box .normal {
		background: rgba(255, 215, 54, 0.15);
		color: #ffd736;
	}

	.score-box .weak {
		background: rgba(128, 125, 254, 0.15);
		color: var(--purple);
	}

	.range-button {
		width: 100px;
		height: 36px;
		padding: 0 var(--space-3);
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: 7.36px;
		background: var(--surface);
		color: var(--text-primary);
		font-size: 16px;
	}

	.legend {
		margin-top: 18px;
		display: flex;
		align-items: center;
		gap: var(--space-5);
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
	}

	.legend span {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.dot {
		width: 8px;
		height: 8px;
		display: inline-block;
		border-radius: var(--radius-full);
	}

	.dot.engagement {
		background: var(--primary);
	}

	.dot.confidence {
		background: var(--lime);
	}

	.dot.clarity {
		background: #4522c4;
	}

	.chart-wrap {
		margin-top: 24px;
	}

	.chart-wrap svg {
		width: 100%;
		height: 210px;
		display: block;
		overflow: visible;
	}

	.grid-lines line {
		stroke: var(--cool-grey-light-active);
		stroke-width: 1;
		stroke-dasharray: 3 4;
	}

	.axis-label {
		fill: var(--text-secondary);
		font-size: 13px;
		font-family: var(--font-family);
		font-weight: var(--font-medium);
	}

	.evc-area {
		opacity: 0.3;
	}

	.engagement-area {
		fill: rgba(0, 80, 255, 0.35);
	}

	.confidence-area {
		fill: rgba(159, 227, 0, 0.3);
	}

	.evc-line {
		fill: none;
		stroke-width: 2;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.engagement-line {
		stroke: var(--primary);
	}

	.confidence-line {
		stroke: #9fe300;
	}

	.clarity-line {
		stroke: #4522c4;
	}

	.chart-labels {
		margin-left: 42px;
		margin-right: 16px;
		display: flex;
		justify-content: space-between;
		color: var(--text-secondary);
		font-size: 13px;
		font-weight: var(--font-medium);
	}

	.analysis-box {
		margin-top: var(--space-5);
		min-height: 120px;
		padding: 18px 22px;
		display: flex;
		align-items: center;
		gap: var(--space-6);
		border-radius: var(--radius-sm);
		background: #f2f4ff;
	}

	.trend-icon {
		width: 90px;
		flex-shrink: 0;
		color: var(--primary);
		font-size: 80px;
		font-weight: var(--font-bold);
		line-height: 1;
	}

	.analysis-box strong {
		display: block;
		margin-bottom: var(--space-1);
		color: var(--primary);
		font-size: 18px;
		font-weight: var(--font-bold);
	}

	.analysis-box p {
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
		line-height: 140%;
	}

	.insight-panel {
		display: flex;
		flex-direction: column;
	}

	.insight-copy {
		margin-top: 54px;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.insight-copy strong {
		color: var(--primary);
		font-size: 24px;
		font-weight: var(--font-bold);
		line-height: 140%;
	}

	.insight-copy span {
		color: var(--primary);
		font-size: 18px;
		font-weight: var(--font-medium);
	}

	.insight-copy p {
		margin-top: var(--space-4);
		color: var(--text-secondary);
		font-size: 18px;
		font-weight: var(--font-medium);
		line-height: 140%;
	}

	.goal-area {
		margin-top: auto;
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.goal-card {
		padding: var(--space-3);
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.goal-title {
		color: var(--brand-dark);
		font-size: 16px;
		font-weight: var(--font-medium);
	}

	.goal-progress {
		margin-top: var(--space-4);
		width: 100%;
		height: 21px;
		overflow: hidden;
		border-radius: var(--radius-sm);
		background: var(--cool-grey-light-active);
	}

	.goal-progress span {
		display: block;
		height: 100%;
		border-radius: var(--radius-sm);
		background: var(--primary);
	}

	.goal-meta {
		margin-top: var(--space-2);
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
	}

	.training-panel {
		min-height: 222px;
		padding: 22px;
	}

	.training-heading {
		display: flex;
		align-items: center;
		gap: var(--space-5);
	}

	.training-heading p {
		color: var(--text-secondary);
	}

	.training-grid {
		margin-top: var(--space-5);
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--space-3);
	}

	.training-card {
		min-height: 128px;
		padding: var(--space-4);
		display: flex;
		align-items: flex-end;
		gap: 22px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.training-left {
		flex: 1;
		display: flex;
		align-items: flex-start;
		gap: 22px;
		min-width: 0;
	}

	.flag-icon {
		width: 36px;
		height: 36px;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border-radius: var(--radius-full);
		background: var(--primary);
		color: var(--text-on-primary);
		font-size: 18px;
	}

	.training-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		min-width: 0;
	}

	.training-content h3 {
		color: var(--text-primary);
		font-size: 18px;
		font-weight: var(--font-bold);
		line-height: 135%;
	}

	.training-content p {
		color: var(--text-secondary);
		font-size: 14px;
		font-weight: var(--font-medium);
		line-height: 135%;
	}

	.chips {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.chips span {
		padding: 2px 8px;
		border-radius: var(--radius-full);
		font-size: 12px;
		font-weight: var(--font-medium);
	}

	.chips .clarity {
		background: rgba(159, 227, 0, 0.15);
		color: #9fe300;
	}

	.chips .engagement {
		background: rgba(0, 51, 255, 0.15);
		color: var(--primary);
	}

	.chips .confidence {
		background: rgba(128, 125, 254, 0.15);
		color: #4522c4;
	}

	.chips .difficulty {
		background: rgba(255, 215, 54, 0.15);
		color: #ffd736;
	}

	@media (max-width: 1500px) {
		.home-page {
			padding: 32px;
		}

		.summary-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.dashboard-grid {
			grid-template-columns: 1fr;
		}

		.training-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
