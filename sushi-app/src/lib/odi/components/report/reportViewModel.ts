import type { ReportQaQuestion } from './reportTypes';
export function feedbackTone(type: string) {
	return type === 'positive' ? 'positive' : type === 'warning' ? 'warning' : 'negative';
}
export function metricEnglish(key: string) {
	return key === 'engagement' ? 'Engagement' : key === 'clarity' ? 'Clarity' : 'Credibility';
}
export function qaScore(question: ReportQaQuestion) {
	const values = Object.values(question.scores ?? {}).filter(Number.isFinite) as number[];
	return values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null;
}
export function qaMetricAverage(
	questions: ReportQaQuestion[],
	key: 'understanding' | 'clarity' | 'evidence'
) {
	const values = questions.map((q) => q.scores?.[key]).filter(Number.isFinite) as number[];
	return values.length ? Math.round(values.reduce((a, b) => a + b, 0) / values.length) : null;
}
