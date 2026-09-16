import type { OdiSession } from '../stores/session';
export function numberOrNull(value: unknown): number | null {
	if (value === null || value === undefined || value === '') return null;
	const n = Number(value);
	return Number.isFinite(n) ? n : null;
}
export function summarizeSession(session: OdiSession) {
	const f = session.feedback as Record<string, any> | null,
		env = session.template?.environment ?? {},
		scores = f?.score_card?.scores ?? {};
	const score = numberOrNull(f?.score?.overall_score ?? f?.overall_score);
	const evc = {
		engagement: numberOrNull(scores.engagement),
		credibility: numberOrNull(scores.credibility),
		clarity: numberOrNull(scores.clarity)
	};
	return {
		session,
		id: session.session_id,
		templateId: session.template_id,
		title: String(env.title || env.position || env.company_name || '제목 없는 세션'),
		type: session.template?.type === 'interview' ? '면접' : '발표',
		score,
		evc,
		seconds: Math.max(
			0,
			(numberOrNull(f?.duration?.actual_seconds) ?? 0) +
				(numberOrNull(f?.duration?.qa_seconds) ?? 0)
		),
		date: session.ended_at ?? session.created_at,
		summary: String(f?.ai_insight?.description ?? '세부 피드백을 확인해 보세요.'),
		audience: Number(session.template?.audience?.audience_count ?? env.interviewer_count ?? 0),
		details: `${env.duration_minutes ?? 0}분 · ${session.template?.type === 'interview' ? '면접' : `Q&A ${env.question_count ?? 0}개`}`
	};
}
export type SessionSummary = ReturnType<typeof summarizeSession>;
export function completedSummaries(sessions: OdiSession[]) {
	return sessions
		.filter((s) => s.state === 'completed' && s.feedback)
		.map(summarizeSession)
		.sort((a, b) => b.date.localeCompare(a.date) || b.id.localeCompare(a.id));
}
export function summarizeHistory(rows: SessionSummary[]) {
	const scores = rows.flatMap((s) => (s.score === null ? [] : [s.score]));
	return {
		average: scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null,
		best: scores.length ? Math.max(...scores) : null,
		seconds: rows.reduce((sum, r) => sum + r.seconds, 0)
	};
}
export function groupSessions(rows: SessionSummary[]) {
	const groups = new Map<string, SessionSummary[]>();
	for (const row of rows) {
		const key = row.templateId ?? row.id;
		groups.set(key, [...(groups.get(key) ?? []), row]);
	}
	return [...groups].map(([id, items]) => ({
		id,
		items,
		latest: items[0],
		delta:
			items[0].score !== null && items[1]?.score != null ? items[0].score - items[1].score : null
	}));
}
export function grade(score: number | null) {
	return score === null ? '미측정' : score >= 80 ? '우수' : score >= 65 ? '보통' : '개선';
}
export function shortDate(value: string) {
	return new Date(value).toLocaleDateString('ko-KR');
}
export const availableTrainingIds = [
	'message_clarity',
	'structure_flow',
	'evidence_use',
	'claim_evidence_link',
	'vocabulary_expression',
	'speech_rate',
	'filler_words',
	'time_management'
];
export const trainingNames: Record<string, string> = {
	message_clarity: '메시지 명확성',
	structure_flow: '구조와 흐름',
	evidence_use: '근거 활용',
	claim_evidence_link: '주장·근거 연결',
	vocabulary_expression: '어휘와 표현',
	speech_rate: '발화 속도',
	filler_words: '습관어 줄이기',
	time_management: '시간 운영'
};
export function recommendations(latest?: { feedback?: unknown }) {
	const details = (latest?.feedback as any)?.detail_analysis;
	const metrics = [...(details?.content_metrics ?? []), ...(details?.delivery_metrics ?? [])]
		.filter((m) => availableTrainingIds.includes(m.id) && numberOrNull(m.score) !== null)
		.sort((a, b) => a.score - b.score);
	return [
		...new Set([...metrics.map((m) => m.id), 'message_clarity', 'speech_rate', 'filler_words'])
	].slice(0, 3) as string[];
}
