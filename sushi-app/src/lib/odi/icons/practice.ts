import green from './report-v3/metric-flag-green.svg';
import purple from './report-v3/metric-flag-blue.svg';
import blue from './report-v3/metric-flag-purple.svg';

// Figma 2684:29359: same flag glyph, distinct colors by exercise.
// Keep existing report filenames intact; their blue/purple names are inverted.
const icons: Record<string, string> = {
	message_clarity: green,
	structure_flow: green,
	evidence_use: purple,
	claim_evidence_link: purple,
	vocabulary_expression: purple,
	gaze: blue,
	speech_rate: blue,
	pronunciation: green,
	filler_words: green,
	time_management: blue
};
export function practiceIcon(id: string): string {
	return icons[id] ?? blue;
}
