import { it, expect } from 'vitest';
import { applySuggestions, type ScriptAnalysis } from './scriptAnalysis';
const analysis = {
	source_text: '👋abc def',
	sections: [
		{ slide: 1, text: '👋abc ' },
		{ slide: 2, text: 'def' }
	],
	suggestions: [
		{ id: '1', category: 'length', start: 1, end: 4, original: 'abc', replacement: 'A' },
		{ id: '2', category: 'terms', start: 5, end: 8, original: 'def', replacement: 'D' }
	]
} as ScriptAnalysis;
it('applies exact codepoint ranges with emoji and preserves sections', () =>
	expect(applySuggestions(analysis, ['1', '2'], analysis.source_text)).toEqual([
		{ slide: 1, text: '👋A ' },
		{ slide: 2, text: 'D' }
	]));
it('only applies selected changes', () =>
	expect(applySuggestions(analysis, ['2'], analysis.source_text)[0].text).toBe('👋abc '));
it('rejects stale or overlapping suggestions', () => {
	expect(() => applySuggestions(analysis, ['1'], 'changed')).toThrow();
	expect(() =>
		applySuggestions(
			{
				...analysis,
				suggestions: [...analysis.suggestions, { ...analysis.suggestions[0], id: '3' }]
			},
			['1', '3'],
			analysis.source_text
		)
	).toThrow();
});
