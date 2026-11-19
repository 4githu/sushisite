import type { NotebookPage } from './types';
export type PaperTemplate = { pattern: 'ruled' | 'blank'; color: 'white' | 'yellow' | 'black' };
export const standardPaper: PaperTemplate = { pattern: 'ruled', color: 'white' };
export const paperColors = { white: '#ffffff', yellow: '#fff5cf', black: '#25272b' };
export function validPaper(value: unknown): value is PaperTemplate {
	const p = value as PaperTemplate;
	return (
		!!p && ['ruled', 'blank'].includes(p.pattern) && ['white', 'yellow', 'black'].includes(p.color)
	);
}
export function readPaperDefault(): PaperTemplate {
	try {
		const p = JSON.parse(localStorage.getItem('netaq-paper-default') || 'null');
		if (validPaper(p)) return p;
	} catch {}
	return { ...standardPaper };
}
export function savePaperDefault(p: PaperTemplate) {
	localStorage.setItem('netaq-paper-default', JSON.stringify(p));
}
export function paperFor(p: NotebookPage): PaperTemplate {
	return validPaper(p.paper) ? p.paper : standardPaper;
}
export function createPaperPage(paper: PaperTemplate = standardPaper): NotebookPage {
	return { id: crypto.randomUUID(), source: null, w: 794, h: 1123, items: [], paper: { ...paper } };
}
