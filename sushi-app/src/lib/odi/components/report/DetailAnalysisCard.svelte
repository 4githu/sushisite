<script lang="ts">
	import MetricBadge from './MetricBadge.svelte';
	import {
		contentMetricLabel,
		deliveryMetricLabel,
		formatSeconds,
		scoreGrade,
		scoreGradeType
	} from './reportUtils';
	import type { ReportDetailMetric, ReportFeedback } from './reportTypes';
	import {
		reportDetailCoaching,
		reportDetailEvidence,
		reportDetailInterpretation,
		figmaChevronDown,
		reportMetricFlagBlue,
		reportMetricFlagGreen,
		reportMetricFlagPurple
	} from '$lib/odi/icons';

	let { feedback }: { feedback: ReportFeedback } = $props();

	const detail = $derived(feedback.detail_analysis ?? {});
	const evidenceById = $derived(
		new Map((feedback.evidence ?? []).map((item) => [item.evidence_id, item]))
	);
	let expanded = $state<Record<string, boolean>>({});

	const legacyContentKeys = [
		'central_message',
		'organization',
		'supporting_material',
		'cer_validity',
		'language_clarity'
	];
	const legacyDeliveryKeys = [
		'gaze_delivery',
		'vocal_delivery',
		'pronunciation',
		'filler_words',
		'time_management'
	];
	const labels: Record<string, string> = {
		message_clarity: '메시지 명확성',
		structure_flow: '발표 구조와 흐름',
		evidence_use: '근거와 자료 활용',
		claim_evidence_link: '주장 - 근거 연결성',
		vocabulary_expression: '어휘 및 표현 적절성',
		gaze: '시선 처리',
		speech_rate: '발화 속도',
		central_message: '메시지 명확성',
		organization: '발표 구조와 흐름',
		supporting_material: '근거와 자료 활용',
		cer_validity: '주장 - 근거 연결성',
		language_clarity: '어휘 및 표현 적절성',
		gaze_delivery: '시선 처리',
		vocal_delivery: '발화 속도',
		pronunciation: '발음 정확도',
		filler_words: '습관어 사용',
		time_management: '시간 운영'
	};

	function legacyMetrics(
		keys: string[],
		source: Record<string, number> = {}
	): ReportDetailMetric[] {
		return keys.map((key) => ({
			id: key,
			label:
				labels[key] ??
				(source === detail.content_analysis ? contentMetricLabel(key) : deliveryMetricLabel(key)),
			score: Number.isFinite(source[key]) ? source[key] : null,
			status: Number.isFinite(source[key]) ? 'available' : 'unavailable'
		}));
	}

	function metricLabel(metric: ReportDetailMetric) {
		return metric.label ?? labels[metric.id] ?? metric.id;
	}

	const contentMetrics = $derived(
		detail.content_metrics?.length
			? detail.content_metrics
			: legacyMetrics(legacyContentKeys, detail.content_analysis)
	);
	const deliveryMetrics = $derived(
		detail.delivery_metrics?.length
			? detail.delivery_metrics
			: legacyMetrics(legacyDeliveryKeys, detail.delivery_analysis)
	);

	function toggle(key: string) {
		expanded = { ...expanded, [key]: !expanded[key] };
	}

	function rowFlag(index: number) {
		return [reportMetricFlagGreen, reportMetricFlagBlue, reportMetricFlagPurple][index % 3];
	}

	function evidenceText(metric: ReportDetailMetric) {
		const evidence = metric.evidence_ids?.map((id) => evidenceById.get(id)).find(Boolean);
		if (!evidence) return '연결된 수행 근거가 없는 이전 형식의 리포트입니다.';
		return `${formatSeconds(evidence.start_sec)} · 슬라이드 ${evidence.slide} — ${evidence.evaluation_summary}`;
	}
</script>

<div class="detail-analysis">
	{#if contentMetrics.length === 0 && deliveryMetrics.length === 0}
		<div class="analysis-empty">세부 분석 데이터가 아직 생성되지 않았습니다.</div>
	{:else}
		<div class="analysis-columns">
			{#each [{ title: '내용 구성', metrics: contentMetrics }, { title: '전달 방식', metrics: deliveryMetrics }] as group}
				<section>
					<h3>{group.title}</h3>
					<div class="metric-list">
						{#each group.metrics as metric, index}
							<article
								class:open={expanded[metric.id]}
								class:unavailable={metric.score === null || metric.score === undefined}
								class="metric-item"
							>
								<button
									class="metric-row"
									type="button"
									aria-expanded={Boolean(expanded[metric.id])}
									onclick={() => toggle(metric.id)}
								>
									<img class="row-flag" src={rowFlag(index)} alt="" />
									<strong class="metric-name">{metricLabel(metric)}</strong>
									<span class="metric-score"
										>{metric.score ?? '—'}<small
											>{metric.score !== null && metric.score !== undefined ? '/100' : ''}</small
										></span
									>
									<span class="progress"><i style={`width:${metric.score ?? 0}%`}></i></span>
									{#if metric.score !== null && metric.score !== undefined}
										<MetricBadge
											label={scoreGrade(metric.score)}
											type={scoreGradeType(metric.score)}
										/>
									{:else}
										<span class="unavailable-badge">평가 불가</span>
									{/if}
									<span class="chevron" aria-hidden="true"
										><img src={figmaChevronDown} alt="" /></span
									>
								</button>

								{#if expanded[metric.id]}
									<div class="metric-detail">
										<div>
											<img src={reportDetailInterpretation} alt="" /><strong>종합 해석</strong>
											<p>
												{metric.reason ?? metric.summary ??
													(metric.score === null || metric.score === undefined
														? '현재 입력으로 평가할 수 없습니다.'
														: `${scoreGrade(metric.score)} 수준으로 평가된 항목입니다.`)}
											</p>
										</div>
										<div>
											<img src={reportDetailEvidence} alt="" /><strong>평가 근거</strong>
											<p>{evidenceText(metric)}</p>
										</div>
										<div>
											<img src={reportDetailCoaching} alt="" /><strong>코칭 제안</strong>
											<p class="coaching">
												{metric.coaching ?? '평가 가능한 근거가 수집된 뒤 코칭 제안을 제공합니다.'}
											</p>
										</div>
									</div>
								{/if}
							</article>
						{/each}
					</div>
				</section>
			{/each}
		</div>
	{/if}
</div>

<style>
	.detail-analysis {
		width: 100%;
	}
	.analysis-columns {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 36px;
	}
	.analysis-columns section {
		min-width: 0;
		display: grid;
		align-content: start;
		gap: 24px;
	}
	h3 {
		color: #030812;
		font-size: 28px;
		font-weight: 700;
		letter-spacing: -0.01em;
	}
	.metric-list {
		display: grid;
		gap: 14px;
	}
	.metric-item {
		overflow: hidden;
		border: 1px solid #caced9;
		border-radius: 10px;
		background: #fff;
	}
	.metric-row {
		width: 100%;
		min-height: 74px;
		padding: 16px 18px;
		display: grid;
		grid-template-columns: 30px minmax(150px, 1fr) 74px minmax(80px, 150px) auto 22px;
		gap: 12px;
		align-items: center;
		color: #030812;
		text-align: left;
	}
	.row-flag {
		width: 28px;
		height: 28px;
		object-fit: contain;
	}
	.metric-name {
		min-width: 0;
		font-size: 18px;
		font-weight: 700;
	}
	.metric-score {
		font-size: 20px;
		font-weight: 700;
		white-space: nowrap;
	}
	.metric-score small {
		margin-left: 4px;
		color: #81838f;
		font-size: 13px;
		font-weight: 500;
	}
	.progress {
		height: 4px;
		overflow: hidden;
		border-radius: 999px;
		background: #e2e4eb;
	}
	.progress i {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: #0033ff;
	}
	.unavailable-badge {
		padding: 5px 9px;
		border-radius: 999px;
		background: #f4f5f7;
		color: #81838f;
		font-size: 12px;
		white-space: nowrap;
	}
	.chevron {
		display: grid;
		width: 24px;
		height: 24px;
		place-items: center;
	}
	.chevron img {
		display: block;
		width: 24px;
		height: 24px;
		object-fit: contain;
		transition: transform 0.2s ease;
		transform-origin: center;
	}
	.metric-item.open .chevron img {
		transform: rotate(180deg);
	}
	.metric-item.open .metric-row {
		border-bottom: 1px solid #e2e4eb;
	}
	.metric-item.unavailable .progress {
		opacity: 0.45;
	}
	.metric-detail {
		padding: 26px 34px 30px 40px;
		display: grid;
		gap: 22px;
		background: #fff;
	}
	.metric-detail > div {
		display: grid;
		grid-template-columns: 28px 112px minmax(0, 1fr);
		gap: 16px;
		align-items: start;
	}
	.metric-detail img {
		width: 28px;
		height: 28px;
		object-fit: contain;
	}
	.metric-detail strong {
		color: #030812;
		font-size: 16px;
		line-height: 28px;
	}
	.metric-detail p {
		color: #81838f;
		font-size: 15px;
		line-height: 1.55;
	}
	.metric-detail p.coaching {
		color: #0033ff;
		font-weight: 600;
	}
	.analysis-empty {
		min-height: 260px;
		display: grid;
		place-items: center;
		border: 1px dashed #caced9;
		border-radius: 10px;
		color: #616678;
	}
	@container (max-width: 980px) {
		.analysis-columns {
			grid-template-columns: 1fr;
		}
	}
	@container (max-width: 650px) {
		.metric-row {
			grid-template-columns: 28px minmax(0, 1fr) auto 20px;
		}
		.progress,
		.metric-row :global(.badge) {
			display: none;
		}
		.metric-detail > div {
			grid-template-columns: 24px 1fr;
		}
		.metric-detail p {
			grid-column: 2;
		}
	}
</style>
