export type ScriptSection = { slide: number | null; text: string; start?: number; end?: number };
export type ScriptSuggestion = {
	id: string;
	category: 'length' | 'structure' | 'terms' | 'rhythm';
	start: number;
	end: number;
	original: string;
	replacement: string;
};
export type ScriptAnalysis = {
	source_text: string;
	source_hash: string;
	version: number;
	sections: ScriptSection[];
	suggestions: ScriptSuggestion[];
	page_count: number;
	mapping_available: boolean;
	estimated_seconds: number;
};
export function applySuggestions(
	analysis: ScriptAnalysis,
	ids: string[],
	current: string
): ScriptSection[] {
	if (current !== analysis.source_text)
		throw new Error('원문이 변경되었습니다. 다시 검사해 주세요.');
	const suggestions = analysis.suggestions
		.filter((s) => ids.includes(s.id))
		.sort((a, b) => a.start - b.start);
	const chars = Array.from(current);
	for (let i = 0; i < suggestions.length; i++) {
		const s = suggestions[i];
		if (
			chars.slice(s.start, s.end).join('') !== s.original ||
			(i > 0 && suggestions[i - 1].end > s.start)
		)
			throw new Error('수정 범위가 겹치거나 변경되었습니다. 다시 검사해 주세요.');
	}
	let cursor = 0;
	return analysis.sections.map((section) => {
		const start = cursor,
			end = start + Array.from(section.text).length;
		cursor = end;
		const local = Array.from(section.text);
		for (const s of suggestions.toReversed()) {
			if (s.start >= start && s.end <= end)
				local.splice(s.start - start, s.end - s.start, ...Array.from(s.replacement));
			else if (s.start < end && s.end > start)
				throw new Error('슬라이드를 가로지르는 제안입니다. 다시 검사해 주세요.');
		}
		return { slide: section.slide, text: local.join('') };
	});
}
