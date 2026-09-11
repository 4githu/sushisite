<script lang="ts">
	import AudienceReactionCard from './AudienceReactionCard.svelte';
	import DetailAnalysisCard from './DetailAnalysisCard.svelte';
	import ScoreOverviewCard from './ScoreOverviewCard.svelte';
	import TimelineFeedbackCard from './TimelineFeedbackCard.svelte';
	import {
		reportBookmark,
		reportClarity,
		reportCoach,
		reportCredibility,
		reportEngagement,
		reportQaAiAvatar,
		reportQaImprovement,
		reportQaStrength,
		reportQaWaveform,
		reportSend,
		reportThumbUp,
		reportTraining,
		reportTrendingUp,
		figmaArrowForward,
		figmaChevronDown,
		figmaReportCalendar,
		figmaReportDownload,
		figmaReportGroup,
		figmaReportSchedule
	} from '$lib/odi/icons';
	import {
		formatDateTime,
		formatKoreanDuration,
		formatSeconds,
		scoreCardLabel,
		scoreGrade
	} from './reportUtils';
	import type {
		ReportFeedback,
		ReportQaQuestion,
		ReportSession,
		ReportTraining
	} from './reportTypes';

	type TabId = 'summary' | 'timeline' | 'details' | 'qa' | 'training';
	type MetricKey = 'engagement' | 'clarity' | 'credibility';

	let {
		session,
		showTimelineVideo = true,
		onOpenPrevious,
		onDownload,
		onStartTraining
	}: {
		session: ReportSession;
		showTimelineVideo?: boolean;
		onOpenPrevious?: () => void;
		onDownload?: () => void;
		onStartTraining?: () => void;
	} = $props();

	let activeTab = $state<TabId>('summary');
	let timelineFilter = $state<'all' | 'E' | 'V' | 'C'>('all');
	let selectedQuestionIndex = $state(0);
	let showSecondaryTraining = $state(true);

	const feedback = $derived((session.feedback ?? {}) as ReportFeedback);
	const template = $derived(session.template ?? {});
	const environment = $derived(template.environment ?? {});
	const files = $derived(template.files ?? {});
	const title = $derived(String(environment.title ?? environment.company_name ?? '세션 리포트'));
	const audienceCount = $derived(
		template.audience?.audience_count ?? environment.interviewer_count ?? '-'
	);
	const plannedSeconds = $derived(
		feedback.duration?.planned_seconds ?? Number(environment.duration_minutes ?? 0) * 60
	);
	const qaSeconds = $derived(feedback.duration?.qa_seconds ?? 0);
	const actualSeconds = $derived(feedback.duration?.actual_seconds ?? plannedSeconds);
	const totalSeconds = $derived(actualSeconds + qaSeconds);
	const overall = $derived(feedback.score?.overall_score);
	const percentile = $derived(feedback.score?.percentile);
	const previousDelta = $derived(
		session.comparison?.previous_session?.score_delta ?? feedback.score?.previous_session_delta
	);
	const scores = $derived(feedback.score_card?.scores ?? {});
	const descriptions = $derived(feedback.score_card?.descriptions ?? {});
	const warnings = $derived(feedback.generation?.warnings ?? []);
	const timeline = $derived(feedback.timeline ?? []);
	const qaFeedback = $derived(feedback.qa_feedback);
	const qaQuestions = $derived.by(
		(): ReportQaQuestion[] =>
			qaFeedback?.questions ??
			(feedback.qa_history ?? []).map((item) => ({
				question: item.question,
				answer: item.answer
			}))
	);
	const selectedQuestion = $derived(qaQuestions[selectedQuestionIndex] ?? qaQuestions[0]);
	const visibleTimelineSeries = $derived(
		timelineFilter === 'all' ? (['E', 'V', 'C'] as const) : [timelineFilter]
	);
	const evidenceById = $derived(
		new Map((feedback.evidence ?? []).map((item) => [item.evidence_id, item]))
	);

	const fileNames = $derived(
		[
			files.slide?.original_name,
			files.script?.original_name ?? (files.script_content ? '발표 스크립트.txt' : null),
			files.paper?.original_name
		].filter(Boolean) as string[]
	);

	const tabs: { id: TabId; label: string }[] = [
		{ id: 'summary', label: '요약' },
		{ id: 'timeline', label: '발표 타임라인 분석' },
		{ id: 'details', label: '세부 요소 분석' },
		{ id: 'qa', label: 'Q&A 피드백' },
		{ id: 'training', label: '맞춤 훈련' }
	];

	const metrics: {
		key: MetricKey;
		icon: string;
		meaning: string;
	}[] = [
		{
			key: 'engagement',
			icon: reportEngagement,
			meaning: '청중이 발표 흐름에 관심을 유지하도록 이끈 정도예요.'
		},
		{
			key: 'credibility',
			icon: reportCredibility,
			meaning: '주장에 근거가 있고 발표 태도가 믿음을 주었는지 봐요.'
		},
		{
			key: 'clarity',
			icon: reportClarity,
			meaning: '핵심 메시지와 설명 순서를 쉽게 이해할 수 있었는지 봐요.'
		}
	];

	const keyFeedback = $derived.by(() => {
		const generated = [
			...(feedback.ai_insight?.strengths ?? []).map((item) => ({ ...item, type: 'positive' })),
			...(feedback.ai_insight?.improvements ?? []).map((item) => ({ ...item, type: 'warning' }))
		];
		const items = generated.slice(0, 3);
		items.push(
			...timeline.slice(0, Math.max(0, 3 - items.length)).map((item) => ({
				type: item.type,
				title: item.title,
				description: item.description,
				action: '',
				evidence_ids: item.evidence_ids ?? [`segment-${item.source_step}`]
			}))
		);

		if (items.length < 3 && feedback.ai_insight?.title) {
			items.push({
				type: 'positive',
				title: feedback.ai_insight.title,
				description: feedback.ai_insight.description ?? '',
				action: '',
				evidence_ids: []
			});
		}

		return items.slice(0, 3);
	});

	const trainings = $derived.by((): ReportTraining[] => {
		if ((feedback.recommended_trainings?.length ?? 0) > 0) {
			return feedback.recommended_trainings ?? [];
		}

		const ranked = metrics
			.map((metric) => ({ key: metric.key, score: scores[metric.key] ?? 0 }))
			.sort((a, b) => a.score - b.score);
		const weakest = ranked[0]?.key ?? 'engagement';
		const fallback: Record<MetricKey, ReportTraining> = {
			engagement: {
				id: 'engagement-fallback',
				title: '발화 속도 안정화 훈련',
				description: '핵심 구간에서 말의 속도와 호흡을 조절해 청중의 집중을 안정적으로 유지해요.',
				duration_minutes: 3,
				type: 'VR 훈련',
				priority: true
			},
			clarity: {
				id: 'clarity-fallback',
				title: '핵심 메시지 구조화 훈련',
				description: '결론을 먼저 말하고 근거를 짧게 덧붙이는 전달 순서를 연습해요.',
				duration_minutes: 3,
				type: 'VR 훈련',
				priority: true
			},
			credibility: {
				id: 'credibility-fallback',
				title: '근거 연결 훈련',
				description: '주장과 사례, 자료를 자연스럽게 연결해 답변의 설득력을 높여요.',
				duration_minutes: 3,
				type: 'VR 훈련',
				priority: true
			}
		};

		return [fallback[weakest]];
	});

	function changeTab(tab: TabId) {
		activeTab = tab;
		window.requestAnimationFrame(() => {
			document.querySelector<HTMLElement>('.v3-tab-panel')?.focus({ preventScroll: true });
		});
	}

	function feedbackTone(type: string) {
		if (type === 'positive') return 'positive';
		if (type === 'warning') return 'warning';
		return 'negative';
	}

	function metricEnglish(key: MetricKey) {
		return key === 'engagement' ? 'Engagement' : key === 'clarity' ? 'Clarity' : 'Credibility';
	}

	function qaScore(question: ReportQaQuestion) {
		const values = Object.values(question.scores ?? {}).filter(Number.isFinite) as number[];
		if (values.length === 0) return null;
		return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
	}

	function qaMetricAverage(key: 'understanding' | 'clarity' | 'evidence') {
		const values = qaQuestions
			.map((question) => question.scores?.[key])
			.filter(Number.isFinite) as number[];
		return values.length
			? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
			: null;
	}
</script>

<div class="report-v3" data-report-version="v3">
	<button type="button" class="back-link clickable" onclick={onOpenPrevious}>
		<span class="back-icon" aria-hidden="true"><img src={figmaArrowForward} alt="" /></span> 세션 목록으로
		돌아가기
	</button>

	<header class="hero">
		<div class="hero-copy">
			<p>이번 세션 결과</p>
			<h1>{title}</h1>

			<div class="meta-row">
				<span
					><img src={figmaReportCalendar} alt="" />{formatDateTime(
						session.started_at ?? session.created_at
					)}</span
				>
				<span><img src={figmaReportGroup} alt="" />{audienceCount}인</span>
				<span
					><img src={figmaReportSchedule} alt="" />발표 {formatKoreanDuration(actualSeconds)} · Q&A {formatKoreanDuration(
						qaSeconds
					)} · 총 {formatKoreanDuration(totalSeconds)}</span
				>
			</div>

			{#if fileNames.length > 0}
				<div class="file-row">
					<img src={figmaReportDownload} alt="" /><strong>첨부 자료</strong>
					{#each fileNames as fileName, index}
						<span>{fileName}</span>{#if index < fileNames.length - 1}<i>·</i>{/if}
					{/each}
				</div>
			{/if}
		</div>

		<div class="hero-score" aria-label="총점">
			<div><strong>{Number.isFinite(overall) ? overall : '--'}</strong><span>/100</span></div>
			{#if percentile !== null && percentile !== undefined}
				<em>상위 {percentile}%</em>
			{/if}
			{#if previousDelta !== null && previousDelta !== undefined}
				<p>지난 세션 대비 <b>{previousDelta > 0 ? '+' : ''}{previousDelta}점</b></p>
			{/if}
		</div>
	</header>

	<nav class="report-tabs" aria-label="결과 리포트 항목">
		{#each tabs as tab}
			<button
				type="button"
				class:active={activeTab === tab.id}
				aria-selected={activeTab === tab.id}
				role="tab"
				onclick={() => changeTab(tab.id)}>{tab.label}</button
			>
		{/each}
	</nav>

	{#if warnings.length > 0}
		<div class="generation-notice" role="status">
			<strong>일부 입력이 제한된 상태로 분석되었습니다.</strong>
			<span>{warnings.join(', ')}</span>
		</div>
	{/if}

	<section class="v3-tab-panel" tabindex="-1" aria-live="polite">
		{#if activeTab === 'summary'}
			<div class="tab-heading compact">
				<h2>세션 점수</h2>
			</div>

			<div class="score-layout">
				<div class="score-overview"
					><ScoreOverviewCard {feedback} comparison={session.comparison} variant="v3" /></div
				>

				<div class="metric-cards">
					{#each metrics as metric}
						<article class="metric-card">
							<div class="metric-copy">
								<div class="metric-title">
									<div>
										<h3>{metricEnglish(metric.key)}</h3>
										<small>{scoreCardLabel(metric.key)}</small>
									</div>
								</div>
								<p class="metric-number">
									<strong>{scores[metric.key] ?? '--'}</strong><small>/100</small><span
										>{scoreGrade(scores[metric.key])}</span
									>
								</p>
								<p>{descriptions[metric.key] ?? metric.meaning}</p>
							</div>
							<div class={`metric-icon ${metric.key}`}>
								<img src={metric.icon} alt="" aria-hidden="true" />
							</div>
						</article>
					{/each}
				</div>
			</div>

			<div class="insight-strip">
				<strong>총평</strong>
				<span
					>{feedback.ai_insight?.title ??
						feedback.ai_insight?.description ??
						'발표의 핵심 결과를 분석했어요.'}</span
				>
			</div>

			{#if feedback.ai_insight?.title || keyFeedback.length > 0}
				<section class="summary-section">
					<div class="section-title">
						<h2>핵심 피드백</h2>
						<p>{feedback.ai_insight?.description ?? '이번 발표에서 먼저 확인할 결과예요.'}</p>
					</div>
					<div class="feedback-grid">
						{#each keyFeedback as item}
							<article class={`feedback-card ${feedbackTone(item.type)}`}>
								<div class="feedback-kind">
									<img
										src={item.type === 'positive' ? reportThumbUp : reportTrendingUp}
										alt=""
									/><span>{item.type === 'positive' ? '잘한 점' : '개선 포인트'}</span>
								</div>
								<h3>{item.title}</h3>
								<p>{item.description}</p>
								{#if item.action}<p class="feedback-action">
										<strong>다음 행동</strong>{item.action}
									</p>{/if}
								{#if item.evidence_ids?.[0] && evidenceById.get(item.evidence_ids[0])}
									<small class="evidence-link"
										>근거 {formatSeconds(evidenceById.get(item.evidence_ids[0])?.start_sec)} · 슬라이드
										{evidenceById.get(item.evidence_ids[0])?.slide}</small
									>
								{/if}
							</article>
						{/each}
					</div>
				</section>
			{/if}

			<section class="summary-section">
				<div class="section-title with-action">
					<div>
						<h2>발표 타임라인</h2>
						<p>청중 반응과 대표 구간을 시간순으로 확인하세요.</p>
					</div>
					<button type="button" class="text-action clickable" onclick={() => changeTab('timeline')}
						>자세히 보기 <span class="inline-arrow"><img src={figmaArrowForward} alt="" /></span
						></button
					>
				</div>
				<div class="surface-card"><AudienceReactionCard {feedback} /></div>
				<TimelineFeedbackCard
					{feedback}
					sessionId={session.session_id}
					showMedia={showTimelineVideo}
					maxItems={4}
					variant="figma"
				/>
			</section>

			{#if qaQuestions.length > 0}
				<section class="summary-section">
					<div class="section-title with-action">
						<div>
							<h2>Q&A 피드백</h2>
							<p>질문 의도와 답변의 핵심을 빠르게 확인하세요.</p>
						</div>
						<button type="button" class="text-action" onclick={() => changeTab('qa')}
							>자세히 보기 <span class="inline-arrow"><img src={figmaArrowForward} alt="" /></span
							></button
						>
					</div>
					<article class="summary-qa-card">
						<div class="ring-score">
							<strong>{qaFeedback?.score ?? '—'}</strong><span>/100</span>
						</div>
						<div>
							<strong>{qaFeedback?.summary ?? '질문과 답변 기록이 연결되었습니다.'}</strong>
							<p>
								총 {qaQuestions.length}개 질문 · 평균 답변 {Math.round(
									qaFeedback?.average_answer_seconds ?? 0
								)}초
							</p>
						</div>
						<button type="button" onclick={() => changeTab('qa')}
							>Q&A 결과 보기 <img src={figmaArrowForward} alt="" /></button
						>
					</article>
				</section>
			{/if}

			<section class="summary-section">
				<div class="section-title with-action">
					<div>
						<h2>다음 발표를 위한 훈련 추천</h2>
						<p>가장 먼저 개선하면 좋은 영역이에요.</p>
					</div>
					<button type="button" class="text-action clickable" onclick={() => changeTab('training')}
						>전체 보기 <span class="inline-arrow"><img src={figmaArrowForward} alt="" /></span
						></button
					>
				</div>
				<article class="training-card priority">
					<div class="training-symbol"><img src={reportTraining} alt="" /></div>
					<div class="training-copy">
						<small>가장 먼저 연습해보세요</small>
						<h3>{trainings[0]?.title}</h3>
						<p>{trainings[0]?.description}</p>
						<div>
							<span>약 {trainings[0]?.duration_minutes ?? 3}분</span><span
								>{trainings[0]?.type ?? 'VR 훈련'}</span
							>
						</div>
					</div>
					<button type="button" class="primary-action clickable" onclick={onStartTraining}
						>훈련 시작하기 <span class="inline-arrow"><img src={figmaArrowForward} alt="" /></span
						></button
					>
				</article>
			</section>
		{:else if activeTab === 'timeline'}
			<div class="tab-heading">
				<h2>발표 타임라인</h2>
			</div>
			<div class="timeline-summary">
				{feedback.ai_insight?.description ??
					'발표 흐름과 청중 반응이 달라진 지점을 함께 살펴보세요.'}
			</div>
			<div class="timeline-filters" aria-label="청중 반응 범례">
				{#each [{ id: 'all', label: '전체' }, { id: 'E', label: '시선 응시' }, { id: 'V', label: '질문 생성' }, { id: 'C', label: '긍정 반응' }] as filter}
					<button
						type="button"
						class:active={timelineFilter === filter.id}
						onclick={() => (timelineFilter = filter.id as typeof timelineFilter)}
						>{filter.label}</button
					>
				{/each}
			</div>
			<div class="surface-card timeline-chart">
				<AudienceReactionCard
					{feedback}
					variant="timeline"
					visibleSeries={[...visibleTimelineSeries]}
				/>
			</div>
			<TimelineFeedbackCard
				{feedback}
				sessionId={session.session_id}
				showMedia={showTimelineVideo}
				maxItems={8}
				variant="figma"
			/>
		{:else if activeTab === 'details'}
			<div class="tab-heading">
				<h2>세부 평가 요소</h2>
			</div>
			<DetailAnalysisCard {feedback} />
		{:else if activeTab === 'qa'}
			<div class="tab-heading">
				<h2>Q&A 피드백</h2>
				<p>
					발표 후 진행된 Q&A의 답변을 분석하여 개선점을 확인하고, AI와 함께 더 나은 답변을
					연습해보세요.
				</p>
			</div>

			{#if qaQuestions.length === 0}
				<div class="empty-card">
					<img class="empty-icon" src={reportCoach} alt="" />
					<strong>질문별 Q&A 분석을 준비하고 있어요.</strong>
					<p>
						기존 리포트의 총점과 발표 분석은 정상적으로 볼 수 있습니다. Q&A 데이터가 연결되면 문항별
						답변과 개선 예시가 이곳에 표시됩니다.
					</p>
				</div>
			{:else}
				<div class="qa-summary surface-card">
					<div class="ring-score">
						<strong>{qaFeedback?.score ?? '--'}</strong><span>/100</span><small
							>{qaFeedback?.score ? scoreGrade(qaFeedback.score) : '평가 대기'}</small
						>
					</div>
					<div class="qa-summary-copy">
						<h3>{qaFeedback?.summary ?? '질문과 답변 기록을 바탕으로 응답 내용을 확인했어요.'}</h3>
						<ul>
							<li>총 {qaQuestions.length}개의 질문에 답변했어요.</li>
							<li>
								평균 답변 시간 {Math.round(qaFeedback?.average_answer_seconds ?? 0)}초를 기록했어요.
							</li>
							<li>근거가 있는 평가만 점수로 표시해요.</li>
						</ul>
					</div>
					<div class="qa-summary-metrics">
						{#each [{ label: '질문 이해', value: qaMetricAverage('understanding') }, { label: '답변 명확성', value: qaMetricAverage('clarity') }, { label: '근거 활용', value: qaMetricAverage('evidence') }, { label: '평균 답변 시간', value: qaFeedback?.average_answer_seconds, suffix: '초' }] as metric}
							<div>
								<span>{metric.label}</span><strong
									>{metric.value ?? '—'}<small
										>{metric.value !== null && metric.value !== undefined
											? (metric.suffix ?? '/100')
											: ''}</small
									></strong
								>
							</div>
						{/each}
					</div>
				</div>

				<div class="qa-question-tabs" role="tablist" aria-label="Q&A 질문 선택">
					{#each qaQuestions as question, index}
						<button
							type="button"
							class:active={selectedQuestionIndex === index}
							onclick={() => (selectedQuestionIndex = index)}
							><span>Q{index + 1}</span><strong>{question.question}</strong><small
								>{qaScore(question) === null
									? '평가 대기'
									: scoreGrade(qaScore(question) ?? 0)}</small
							></button
						>
					{/each}
				</div>

				<div class="qa-workspace">
					<article class="qa-detail-card">
						<header>
							<span>Q{selectedQuestionIndex + 1}</span>
							<h3>{selectedQuestion?.question}</h3>
							<time>{formatSeconds(selectedQuestion?.time_sec)}</time><img
								src={reportBookmark}
								alt="북마크"
							/>
						</header>
						<div class="question-intent">
							<strong>질문 의도</strong><span
								>{selectedQuestion?.intent ??
									'질문 의도 분석 데이터가 아직 제공되지 않았습니다.'}</span
							>
						</div>
						<div class="answer-title">
							<strong>내 답변</strong><span
								>{formatSeconds(selectedQuestion?.time_sec)} ~ {formatSeconds(
									(selectedQuestion?.time_sec ?? 0) + (selectedQuestion?.answer_duration_sec ?? 0)
								)} ({Math.round(selectedQuestion?.answer_duration_sec ?? 0)}초)</span
							>
						</div>
						<div class="waveform">
							<button type="button" disabled aria-label="답변 오디오 없음">▶</button><img
								src={reportQaWaveform}
								alt="답변 음성 파형"
							/><time>0:00 / {formatSeconds(selectedQuestion?.answer_duration_sec)}</time>
						</div>
						<p class="answer-transcript">{selectedQuestion?.answer}</p>
						<div class="qa-feedback-grid">
							<div>
								<img src={reportQaStrength} alt="" /><strong>잘한 점</strong>
								<p>
									{selectedQuestion?.strength ??
										'이 문항의 강점 분석 데이터가 아직 제공되지 않았습니다.'}
								</p>
							</div>
							<div>
								<img src={reportQaImprovement} alt="" /><strong>개선 포인트</strong>
								<p>
									{selectedQuestion?.improvement ??
										'이 문항의 개선 분석 데이터가 아직 제공되지 않았습니다.'}
								</p>
							</div>
						</div>
						<div class="question-scores">
							{#each [{ label: '질문 이해', value: selectedQuestion?.scores?.understanding }, { label: '답변 명확성', value: selectedQuestion?.scores?.clarity }, { label: '근거 활용', value: selectedQuestion?.scores?.evidence }] as metric}<div
								>
									<span>{metric.label}</span><strong
										>{metric.value ?? '—'}<small>{metric.value !== undefined ? '/100' : ''}</small
										></strong
									>
								</div>{/each}
							<button type="button" class="primary-action" onclick={onStartTraining}
								>이 질문으로 다시 연습하기 <img src={figmaArrowForward} alt="" /></button
							>
						</div>
					</article>

					<aside class="qa-ai-panel" aria-label="Re:hear AI 답변 예시">
						<div class="ai-brand">
							<img src={reportQaAiAvatar} alt="" /><strong>Re:hear AI</strong>
						</div>
						<p>이 Q&A에 대해 궁금한 점을 물어보세요. AI가 맞춤형 피드백을 제공해드려요.</p>
						<div class="chat-bubble user">이 답변이 좋은 이유는 무엇인가요?</div>
						<div class="chat-bubble">
							{selectedQuestion?.strength ?? '추가 생성 없이 저장된 평가 데이터만 표시합니다.'}
						</div>
						<div class="suggested-answer">
							<strong>개선된 답변 예시</strong>
							<p>
								{selectedQuestion?.suggested_answer ??
									'현재 리포트에는 AI 답변 예시가 없습니다. 추가 생성 없이 기록된 답변과 평가 근거만 표시합니다.'}
							</p>
							<button type="button" disabled
								>이 예시로 연습하기 <img src={figmaArrowForward} alt="" /></button
							>
						</div>
						<label class="chat-input"
							><span>궁금한 점을 입력하세요.</span><button type="button" disabled
								><img src={reportSend} alt="전송" /></button
							></label
						>
					</aside>
				</div>
			{/if}
		{:else}
			<div class="tab-heading">
				<h2>맞춤 훈련</h2>
				<p>다음 발표를 위해 이번 세션에서 가장 먼저 개선하면 좋은 영역이에요.</p>
			</div>
			<div class="training-list">
				{#each trainings.slice(0, 1) as training, index}
					<article class:priority={training.priority || index === 0} class="training-card">
						<div class="training-symbol"><img src={reportTraining} alt="" /></div>
						<div class="training-copy">
							{#if training.priority || index === 0}<small>가장 먼저 연습해보세요</small>{/if}
							<h3>{training.title ?? '맞춤 훈련'}</h3>
							<p>{training.description ?? feedback.ai_insight?.description}</p>
							<div>
								<span>약 {training.duration_minutes ?? 3}분</span><span
									>{training.type ?? 'VR 훈련'}</span
								>
							</div>
						</div>
						<button type="button" class="primary-action clickable" onclick={onStartTraining}
							>훈련 시작하기 <span class="inline-arrow"><img src={figmaArrowForward} alt="" /></span
							></button
						>
					</article>
				{/each}
				{#if trainings.length > 1}
					<button
						class="more-training-toggle"
						type="button"
						aria-expanded={showSecondaryTraining}
						onclick={() => (showSecondaryTraining = !showSecondaryTraining)}
						>다른 추천 훈련 {trainings.length - 1}개 더 보기
						<span class="training-toggle-icon" class:expanded={showSecondaryTraining}
							><img src={figmaChevronDown} alt="" /></span
						></button
					>
					{#if showSecondaryTraining}
						<h3 class="other-training-title">다른 추천 훈련</h3>
						{#each trainings.slice(1) as training}
							<article class="training-card">
								<div class="training-symbol"><img src={reportTraining} alt="" /></div>
								<div class="training-copy">
									<h3>{training.title}</h3>
									<p>{training.description}</p>
									<div>
										<span>약 {training.duration_minutes ?? 3}분</span><span
											>{training.type ?? 'VR 훈련'}</span
										>
									</div>
								</div>
								<button type="button" class="primary-action secondary" onclick={onStartTraining}
									>훈련 시작하기 <span class="inline-arrow"
										><img src={figmaArrowForward} alt="" /></span
									></button
								>
							</article>
						{/each}
					{/if}
				{/if}
			</div>
		{/if}
	</section>

	<footer class="report-footer">
		<button type="button" class="download-action clickable" onclick={onDownload}
			><img src={figmaReportDownload} alt="" />리포트 다운로드</button
		>
	</footer>
</div>

<style>
	.report-v3 {
		width: min(100%, 1514px);
		min-width: 0;
		margin: 0 auto;
		display: grid;
		gap: 32px;
		container-type: inline-size;
		color: var(--brand-black);
	}

	.back-link {
		width: max-content;
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--primary);
		font-size: 15px;
		font-weight: var(--font-medium);
	}

	.back-icon {
		display: grid;
		width: 24px;
		height: 24px;
		place-items: center;
	}
	.back-icon img {
		display: block;
		width: 24px;
		height: 24px;
		object-fit: contain;
		transform: rotate(180deg);
		transform-origin: center;
	}
	.inline-arrow {
		display: inline-grid;
		width: 24px;
		height: 24px;
		place-items: center;
		flex: 0 0 24px;
	}
	.inline-arrow img {
		display: block;
		width: 24px;
		height: 24px;
		object-fit: contain;
	}

	.hero {
		min-width: 0;
		padding: clamp(30px, 4vw, 58px) clamp(28px, 5vw, 76px);
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(230px, 0.34fr);
		gap: clamp(28px, 5vw, 72px);
		align-items: center;
		border-radius: 28px;
		background: linear-gradient(110deg, #07104d 0%, #050632 62%, #0b063b 100%);
		color: #fff;
		overflow: hidden;
	}

	.hero-copy,
	.hero-score {
		min-width: 0;
	}

	.hero-copy > p {
		margin-bottom: 10px;
		color: #807dfe;
		font-size: 16px;
		font-weight: var(--font-medium);
	}

	.hero h1 {
		max-width: 760px;
		font-size: clamp(30px, 3.1vw, 48px);
		font-weight: var(--font-bold);
		line-height: 1.28;
		letter-spacing: -0.02em;
		overflow-wrap: anywhere;
	}

	.meta-row,
	.file-row {
		margin-top: 22px;
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px 24px;
		color: #caced9;
		font-size: 14px;
		line-height: 1.5;
	}

	.meta-row > span {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	.meta-row img {
		width: 18px;
		height: 18px;
	}

	.file-row > img {
		width: 18px;
		height: 18px;
		flex: 0 0 18px;
	}

	.file-row {
		margin-top: 18px;
		color: #b0c9ff;
		gap: 8px;
	}

	.file-row strong {
		margin-right: 18px;
	}

	.file-row span {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.file-row i {
		font-style: normal;
	}

	.hero-score {
		display: grid;
		justify-items: start;
		gap: 12px;
	}

	.hero-score > div {
		display: flex;
		align-items: flex-end;
		gap: 14px;
	}

	.hero-score strong {
		color: #cfff5e;
		font-size: clamp(86px, 9vw, 150px);
		font-weight: var(--font-bold);
		line-height: 0.82;
		letter-spacing: -0.05em;
	}

	.hero-score span {
		padding-bottom: 8px;
		color: #c5c5c5;
		font-size: 24px;
		font-weight: var(--font-bold);
	}

	.hero-score em {
		padding: 6px 24px;
		border-radius: 999px;
		background: #7920e6;
		font-style: normal;
		font-size: 15px;
	}

	.hero-score p {
		color: #caced9;
		font-size: 14px;
	}

	.hero-score b {
		margin-left: 10px;
		color: #fff;
	}

	.report-tabs {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 4px;
	}

	.report-tabs button {
		min-width: 0;
		min-height: 58px;
		padding: 10px 12px;
		border-bottom: 3px solid #e2e4eb;
		color: #616678;
		font-size: clamp(15px, 1.3vw, 20px);
		font-weight: var(--font-medium);
		line-height: 1.3;
		word-break: keep-all;
	}

	.report-tabs button:hover,
	.report-tabs button.active {
		border-color: var(--primary);
		color: var(--primary);
	}

	.generation-notice {
		padding: 12px 16px;
		display: flex;
		flex-wrap: wrap;
		gap: 8px 16px;
		border-radius: 8px;
		background: #fff8df;
		color: var(--text-secondary);
		font-size: 14px;
	}

	.v3-tab-panel {
		min-width: 0;
		display: grid;
		gap: 36px;
		outline: none;
	}

	.tab-heading h2,
	.section-title h2 {
		font-size: clamp(28px, 3vw, 40px);
		font-weight: var(--font-bold);
		line-height: 1.3;
	}

	.tab-heading p,
	.section-title p {
		margin-top: 6px;
		color: var(--text-secondary);
		font-size: 17px;
		line-height: 1.5;
	}

	.tab-heading.compact h2 {
		font-size: 28px;
	}

	.surface-card,
	.metric-card,
	.feedback-card,
	.training-card,
	.empty-card {
		min-width: 0;
		border: 1px solid #eceef3;
		border-radius: 16px;
		background: #fff;
		box-shadow: 0 2px 10px rgba(5, 6, 50, 0.08);
	}

	.surface-card {
		padding: clamp(18px, 2.5vw, 30px);
	}

	.score-overview {
		padding: 0;
		box-shadow: none;
	}

	.score-overview :global(.report-card) {
		box-shadow: none;
	}

	.score-layout {
		display: grid;
		gap: 20px;
	}

	.metric-cards {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 10px;
	}

	.metric-card {
		min-height: 307px;
		padding: 33px 38px 44px 44px;
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 28px;
	}

	.metric-icon {
		width: 167px;
		height: 167px;
		flex: 0 0 167px;
		display: grid;
		place-items: center;
		background: transparent;
	}

	.metric-icon img {
		width: 167px;
		height: 167px;
		object-fit: contain;
	}

	.metric-copy {
		min-width: 0;
		display: grid;
		gap: 8px;
		width: 210px;
	}

	.metric-title {
		display: flex;
		align-items: flex-start;
		gap: 6px;
	}

	.metric-title h3 {
		font-size: 32px;
		font-weight: 600;
	}
	.metric-title small {
		display: block;
		margin-top: 2px;
		color: #030812;
		font-size: 20px;
		font-weight: 400;
	}

	.metric-number {
		display: flex;
		align-items: flex-end;
		gap: 4px;
		color: #636363;
		font-size: 20px;
	}

	.metric-number strong {
		margin-right: 2px;
		color: #111325;
		font-size: 64px;
		font-weight: 600;
	}
	.metric-number small {
		padding-bottom: 12px;
		font-size: 20px;
	}
	.metric-number span {
		align-self: center;
		margin-left: 8px;
		padding: 6px 15px;
		border-radius: 14px;
		background: #d9e0ff;
		color: #03f;
		font-size: 20px;
		white-space: nowrap;
	}

	.metric-copy > p:last-child {
		color: var(--text-secondary);
		font-size: 20px;
		line-height: 1.5;
		word-break: keep-all;
	}

	.insight-strip {
		min-height: 70px;
		padding: 0;
		display: flex;
		align-items: center;
		gap: 0;
		border-radius: 8px;
		background: transparent;
		font-size: 20px;
		line-height: 1.5;
	}

	.timeline-summary {
		margin-top: -22px;
		padding: 11px 18px;
		border: 1px solid #e2e4eb;
		border-radius: 8px;
		background: #f2f2ff;
		color: var(--primary);
		text-align: center;
		font-size: 15px;
	}

	.timeline-filters {
		margin-top: -24px;
		display: flex;
		justify-content: flex-end;
		flex-wrap: wrap;
		gap: 10px;
	}

	.timeline-filters button {
		padding: 7px 12px;
		border: 1px solid #d4d6e2;
		border-radius: 999px;
		color: #616678;
		font-size: 13px;
	}

	.timeline-filters button.active {
		border-color: var(--primary);
		background: #f2f2ff;
		color: var(--primary);
	}

	.timeline-chart {
		padding: 24px 28px 12px;
		box-shadow: none;
	}

	.insight-strip strong {
		width: 251px;
		height: 70px;
		display: grid;
		place-items: center;
		border-radius: 8px;
		background: #807dfe;
		color: #fff;
		font-size: 28px;
		white-space: nowrap;
	}
	.insight-strip span {
		height: 70px;
		flex: 1;
		display: flex;
		align-items: center;
		padding: 0 31px;
		border-radius: 8px;
		background: #f2f2ff;
		font-size: 28px;
	}

	.summary-section {
		display: grid;
		gap: 20px;
	}

	.section-title.with-action {
		display: flex;
		align-items: flex-end;
		justify-content: space-between;
		gap: 20px;
	}

	.section-title h2 {
		font-size: 28px;
	}

	.text-action {
		flex: 0 0 auto;
		color: var(--primary);
		font-size: 15px;
		font-weight: var(--font-medium);
	}

	.feedback-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
	}

	.feedback-card {
		min-height: 260px;
		padding: 32px;
		display: grid;
		align-content: start;
		gap: 8px;
		border: 0;
		background: #f4f5f7;
		box-shadow: 4px 4px 3px rgba(0, 0, 0, 0.07);
	}

	.feedback-kind {
		display: flex;
		align-items: center;
		gap: 7px;
	}

	.feedback-kind img {
		width: 20px;
		height: 20px;
	}

	.feedback-kind span {
		width: max-content;
		padding: 4px 8px;
		border-radius: 999px;
		background: #fff4e8;
		color: #ff7a00;
		font-size: 12px;
		font-weight: var(--font-bold);
	}

	.feedback-card.positive .feedback-kind span {
		background: #eef0ff;
		color: #5d41d7;
	}

	.feedback-card.negative .feedback-kind span {
		background: #fff0f2;
		color: #f04a61;
	}

	.feedback-card h3 {
		font-size: 24px;
		line-height: 1.4;
	}

	.feedback-card p {
		color: var(--text-secondary);
		font-size: 16px;
		line-height: 1.5;
	}

	.feedback-card .feedback-action {
		margin-top: 4px;
		padding-top: 10px;
		border-top: 1px solid #eceef3;
		color: var(--text-primary);
	}

	.feedback-action strong {
		display: block;
		margin-bottom: 3px;
		color: var(--primary);
		font-size: 12px;
	}

	.evidence-link {
		color: #686f82;
		font-size: 12px;
	}

	.training-list {
		display: grid;
		gap: 28px;
	}

	.training-card {
		padding: clamp(24px, 3vw, 42px);
		display: grid;
		grid-template-columns: 116px minmax(0, 1fr) minmax(200px, 0.35fr);
		gap: 30px;
		align-items: center;
	}

	.training-card.priority {
		border-color: #dfe3ff;
	}

	.training-symbol {
		width: 96px;
		height: 96px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #ece9ff;
		color: #6f43ff;
		font-size: 38px;
		font-weight: var(--font-bold);
		letter-spacing: 3px;
	}

	.training-symbol img {
		width: 54px;
		height: 54px;
		object-fit: contain;
	}

	.training-copy {
		min-width: 0;
		display: grid;
		gap: 7px;
	}

	.training-copy small {
		color: var(--primary);
		font-weight: var(--font-bold);
	}

	.training-copy h3 {
		font-size: 24px;
	}

	.training-copy p {
		max-width: 680px;
		color: var(--text-secondary);
		font-size: 15px;
		line-height: 1.5;
	}

	.training-copy > div {
		display: flex;
		gap: 8px;
	}

	.training-copy > div span {
		padding: 4px 12px;
		border-radius: 8px;
		background: #e8fbb5;
		color: #59760e;
		font-size: 13px;
	}

	.training-copy > div span:last-child {
		background: #e9e9ff;
		color: #4d43c8;
	}

	.primary-action {
		min-height: 54px;
		padding: 0 24px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 20px;
		border-radius: 6px;
		background: var(--primary);
		color: #fff;
		font-size: 16px;
		font-weight: var(--font-bold);
	}

	.empty-card {
		min-height: 300px;
		padding: 40px;
		display: grid;
		place-content: center;
		gap: 8px;
		text-align: center;
	}

	.empty-card strong {
		font-size: 20px;
	}

	.empty-card p {
		max-width: 660px;
		color: var(--text-secondary);
		line-height: 1.6;
	}

	.empty-icon {
		width: 52px;
		height: 52px;
		margin: 0 auto 10px;
	}

	.qa-summary {
		display: grid;
		grid-template-columns: 150px minmax(260px, 1fr) minmax(420px, 0.9fr);
		align-items: center;
		gap: 28px;
	}

	.ring-score {
		width: 126px;
		height: 126px;
		display: grid;
		place-content: center;
		border: 10px solid #e7e9ef;
		border-bottom-color: var(--primary);
		border-radius: 50%;
		text-align: center;
	}

	.ring-score strong {
		font-size: 38px;
	}

	.ring-score span {
		font-size: 12px;
	}

	.ring-score small {
		margin-top: 2px;
		color: #616678;
		font-size: 11px;
	}

	.qa-summary h3 {
		font-size: 20px;
	}

	.qa-summary p {
		margin-top: 8px;
		color: var(--text-secondary);
		line-height: 1.5;
	}

	.qa-summary-copy ul {
		margin-top: 16px;
		display: grid;
		gap: 7px;
		color: #616678;
		font-size: 14px;
	}
	.qa-summary-copy li::marker {
		color: #0033ff;
	}
	.qa-summary-metrics {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
	}
	.qa-summary-metrics > div,
	.question-scores > div {
		min-height: 82px;
		padding: 14px;
		display: grid;
		align-content: center;
		gap: 8px;
		border: 1px solid #dfe2eb;
		border-radius: 10px;
	}
	.qa-summary-metrics span,
	.question-scores span {
		color: #616678;
		font-size: 13px;
	}
	.qa-summary-metrics strong,
	.question-scores strong {
		font-size: 24px;
	}
	.qa-summary-metrics small,
	.question-scores small {
		margin-left: 2px;
		color: #81838f;
		font-size: 11px;
	}
	.qa-question-tabs {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 12px;
	}
	.qa-question-tabs button {
		min-height: 94px;
		padding: 18px;
		display: grid;
		grid-template-columns: 36px minmax(0, 1fr);
		gap: 8px 12px;
		align-items: center;
		border: 1px solid #dfe2eb;
		border-radius: 10px;
		background: #fff;
		color: #030812;
		text-align: left;
		box-shadow: 0 2px 8px rgba(5, 6, 50, 0.06);
	}
	.qa-question-tabs button > span {
		width: 36px;
		height: 36px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #0033ff;
		color: #fff;
		font-weight: 700;
	}
	.qa-question-tabs button strong {
		font-size: 14px;
		line-height: 1.45;
	}
	.qa-question-tabs button small {
		grid-column: 2;
		width: max-content;
		padding: 3px 8px;
		border-radius: 999px;
		background: #effff2;
		color: #44b06a;
	}
	.qa-question-tabs button.active {
		border: 2px solid #0033ff;
		background: #f8f9ff;
	}
	.qa-workspace {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 330px;
		gap: 26px;
		align-items: start;
	}
	.qa-detail-card,
	.qa-ai-panel {
		border: 1px solid #dfe2eb;
		border-radius: 14px;
		background: #fff;
		box-shadow: 0 2px 10px rgba(5, 6, 50, 0.08);
	}
	.qa-detail-card {
		padding: 26px;
		display: grid;
		gap: 22px;
	}
	.qa-detail-card > header {
		display: grid;
		grid-template-columns: 38px minmax(0, 1fr) auto 24px;
		gap: 12px;
		align-items: center;
	}
	.qa-detail-card > header > span {
		width: 38px;
		height: 38px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #0033ff;
		color: #fff;
		font-weight: 700;
	}
	.qa-detail-card > header h3 {
		font-size: 20px;
	}
	.qa-detail-card > header time {
		color: #81838f;
		font-size: 13px;
	}
	.qa-detail-card > header img {
		width: 22px;
		height: 22px;
	}
	.question-intent {
		padding: 13px 16px;
		display: flex;
		gap: 28px;
		border-radius: 6px;
		background: #e9edff;
		font-size: 14px;
	}
	.question-intent strong {
		color: #0033ff;
		white-space: nowrap;
	}
	.answer-title {
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.answer-title span {
		color: #81838f;
		font-size: 13px;
	}
	.waveform {
		min-height: 56px;
		padding: 10px 14px;
		display: grid;
		grid-template-columns: 24px minmax(0, 1fr) auto;
		gap: 12px;
		align-items: center;
		border: 1px solid #dfe2eb;
		border-radius: 8px;
	}
	.waveform button {
		color: #0033ff;
		opacity: 1;
	}
	.waveform img {
		width: 100%;
		height: 32px;
		object-fit: fill;
	}
	.waveform time {
		color: #81838f;
		font-size: 12px;
	}
	.answer-transcript {
		padding: 4px 8px;
		color: #3d4150;
		font-size: 16px;
		line-height: 1.7;
		text-align: center;
	}
	.qa-feedback-grid > div {
		display: grid;
		grid-template-columns: 24px auto;
		gap: 6px 10px;
	}
	.qa-feedback-grid img {
		width: 22px;
		height: 22px;
	}
	.qa-feedback-grid p {
		grid-column: 1 / -1;
		text-align: center;
	}
	.question-scores {
		display: grid;
		grid-template-columns: repeat(3, 110px) minmax(240px, 1fr);
		gap: 10px;
		align-items: stretch;
	}
	.question-scores .primary-action img {
		width: 24px;
		height: 24px;
		filter: brightness(0) invert(1);
	}
	.qa-ai-panel {
		padding: 24px 18px;
		display: grid;
		gap: 18px;
		background: #f7f7ff;
	}
	.ai-brand {
		display: flex;
		align-items: center;
		gap: 8px;
		color: #0033ff;
	}
	.ai-brand img {
		width: 28px;
		height: 28px;
		border-radius: 7px;
	}
	.qa-ai-panel > p {
		color: #3d4150;
		font-size: 14px;
		line-height: 1.5;
	}
	.chat-bubble {
		padding: 14px;
		border-radius: 8px;
		background: #fff;
		color: #3d4150;
		font-size: 13px;
		line-height: 1.55;
	}
	.chat-bubble.user {
		margin-left: 28px;
		background: #0033ff;
		color: #fff;
	}
	.suggested-answer {
		padding: 18px 14px;
		display: grid;
		gap: 12px;
		border-radius: 10px;
		background: #fff;
		text-align: center;
	}
	.suggested-answer p {
		color: #3d4150;
		font-size: 13px;
		line-height: 1.6;
	}
	.suggested-answer button {
		min-height: 42px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		border: 1px solid #0033ff;
		border-radius: 6px;
		color: #0033ff;
		opacity: 0.65;
	}
	.suggested-answer img {
		width: 20px;
		height: 20px;
	}
	.chat-input {
		min-height: 64px;
		padding: 14px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		border: 1px solid #dfe2eb;
		border-radius: 10px;
		background: #fff;
		color: #a0a3ad;
		font-size: 13px;
	}
	.chat-input button {
		width: 32px;
		height: 32px;
		display: grid;
		place-items: center;
		border-radius: 50%;
		background: #0033ff;
		opacity: 0.55;
	}
	.chat-input img {
		width: 18px;
		height: 18px;
	}
	.summary-qa-card {
		padding: 28px 34px;
		display: grid;
		grid-template-columns: 126px minmax(0, 1fr) 230px;
		gap: 28px;
		align-items: center;
		border: 1px solid #eceef3;
		border-radius: 16px;
		background: #fff;
		box-shadow: 0 2px 10px rgba(5, 6, 50, 0.08);
	}
	.summary-qa-card p {
		margin-top: 8px;
		color: #616678;
	}
	.summary-qa-card > button {
		min-height: 52px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		border-radius: 6px;
		background: #0033ff;
		color: #fff;
		font-weight: 700;
	}
	.summary-qa-card > button img {
		width: 22px;
		height: 22px;
		filter: brightness(0) invert(1);
	}
	.more-training-toggle {
		min-height: 52px;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		color: #0033ff;
		border-top: 1px solid #dfe2eb;
		border-bottom: 1px solid #dfe2eb;
	}
	.training-toggle-icon {
		display: grid;
		width: 24px;
		height: 24px;
		place-items: center;
	}
	.training-toggle-icon img {
		display: block;
		width: 24px;
		height: 24px;
		object-fit: contain;
		transition: transform 0.2s ease;
		transform-origin: center;
	}
	.training-toggle-icon.expanded img {
		transform: rotate(180deg);
	}
	.other-training-title {
		font-size: 28px;
	}
	.primary-action.secondary {
		border: 1px solid #0033ff;
		background: #fff;
		color: #0033ff;
	}

	.qa-feedback-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
	}

	.qa-feedback-grid > div {
		padding: 16px;
		border-radius: 10px;
		background: #f4f2ff;
	}

	.qa-feedback-grid strong {
		font-size: 14px;
	}

	.qa-feedback-grid p {
		margin-top: 6px;
		color: var(--text-secondary);
		font-size: 14px;
		line-height: 1.5;
	}

	.report-footer {
		padding-top: 10px;
		display: flex;
		justify-content: flex-end;
	}

	.download-action {
		min-height: 48px;
		padding: 0 22px;
		border: 1px solid var(--cool-grey-light-active);
		border-radius: 8px;
		color: var(--text-secondary);
		font-weight: var(--font-medium);
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.download-action img {
		width: 20px;
		height: 20px;
	}

	@container (max-width: 1100px) {
		.metric-cards {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}

		.training-card {
			grid-template-columns: 96px minmax(0, 1fr);
		}

		.training-card .primary-action {
			grid-column: 2;
		}

		.qa-summary {
			grid-template-columns: 140px minmax(0, 1fr);
		}
		.qa-summary-metrics {
			grid-column: 1 / -1;
		}
		.qa-workspace {
			grid-template-columns: 1fr;
		}
		.qa-ai-panel {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
		.ai-brand,
		.qa-ai-panel > p,
		.chat-input {
			grid-column: 1 / -1;
		}
		.question-scores {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		.question-scores .primary-action {
			grid-column: 1 / -1;
		}
	}

	@container (max-width: 760px) {
		.hero {
			grid-template-columns: 1fr;
		}

		.hero-score {
			grid-template-columns: auto auto;
			align-items: center;
		}

		.hero-score p {
			grid-column: 1 / -1;
		}

		.report-tabs {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}

		.metric-cards,
		.feedback-grid,
		.qa-feedback-grid {
			grid-template-columns: 1fr;
		}

		.insight-strip {
			align-items: flex-start;
			flex-direction: column;
			gap: 4px;
		}

		.section-title.with-action {
			align-items: flex-start;
			flex-direction: column;
		}

		.training-card {
			grid-template-columns: 1fr;
		}

		.training-card .primary-action {
			grid-column: 1;
		}

		.qa-summary {
			grid-template-columns: 1fr;
		}

		.qa-question-tabs,
		.summary-qa-card {
			grid-template-columns: 1fr;
		}
		.qa-ai-panel {
			grid-template-columns: 1fr;
		}
		.ai-brand,
		.qa-ai-panel > p,
		.chat-input {
			grid-column: auto;
		}
	}

	@container (max-width: 480px) {
		.hero {
			padding: 24px 20px;
			border-radius: 18px;
		}

		.hero-score {
			grid-template-columns: 1fr;
		}

		.meta-row,
		.file-row {
			align-items: flex-start;
			flex-direction: column;
		}

		.file-row strong {
			margin-right: 0;
		}

		.file-row i {
			display: none;
		}

		.report-tabs {
			grid-template-columns: 1fr;
		}

		.metric-card {
			flex-direction: column;
		}

		.training-symbol {
			width: 76px;
			height: 76px;
		}
	}

	@media print {
		.back-link,
		.report-tabs,
		.report-footer,
		.text-action,
		.primary-action {
			display: none;
		}

		.report-v3 {
			width: 100%;
		}
	}
</style>
