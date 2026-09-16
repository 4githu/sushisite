import { describe, it, expect } from 'vitest';
import {
	summarizeSession,
	summarizeHistory,
	groupSessions,
	grade,
	recommendations
} from './sessionSummary';
import type { OdiSession } from '../stores/session';
const record = (id: string, score: number | null = 80, templateId = 't') =>
	({
		session_id: id,
		template_id: templateId,
		template: { environment: { title: '동일 제목' }, type: 'presentation' },
		feedback: {
			score: { overall_score: score },
			duration: { actual_seconds: 60, qa_seconds: 30 },
			score_card: { scores: { engagement: 72 } }
		},
		state: 'completed',
		created_at: '2026-09-12T00:00:00Z'
	}) as unknown as OdiSession;
describe('session summaries', () => {
	it('distinguishes zero from unmeasured', () => {
		const rows = [summarizeSession(record('a', 0)), summarizeSession(record('b', null))];
		expect(summarizeHistory(rows)).toEqual({ average: 0, best: 0, seconds: 180 });
		expect(grade(null)).toBe('미측정');
		expect(grade(65)).toBe('보통');
	});
	it('groups by identity, never title', () =>
		expect(
			groupSessions([
				summarizeSession(record('a', 90, 't1')),
				summarizeSession(record('b', 80, 't2')),
				summarizeSession(record('c', 70, 't1'))
			]).map((g) => [g.id, g.items.length, g.delta])
		).toEqual([
			['t1', 2, 20],
			['t2', 1, null]
		]));
	it('excludes unmeasurable training recommendations', () => {
		const r = record('a');
		(r.feedback as any).detail_analysis = {
			delivery_metrics: [
				{ id: 'gaze', score: 1 },
				{ id: 'pronunciation', score: null },
				{ id: 'filler_words', score: 40 }
			]
		};
		expect(recommendations(r)[0]).toBe('filler_words');
		expect(recommendations(r)).not.toContain('gaze');
	});
});
