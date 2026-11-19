import { createDocument, createTextBlock } from '$lib/textediter/model';
import type { Capture } from './capture';
export type MemoMeta = {
	includedCaptureIds?: string[];
	originalRichDocument?: string;
	format?: string;
	[key: string]: unknown;
};
export function memoMeta(value: string): MemoMeta {
	try {
		return JSON.parse(value) || {};
	} catch {
		return { originalRichDocument: value };
	}
}
export function memoText(value: string) {
	return value.replace(
		/^([ \t]*)- \[([ xX])\] ?/gm,
		(_, indent, checked) => indent + (checked.toLowerCase() === 'x' ? '완료: ' : '')
	);
}
export function mergeMemoCaptures(
	content: string,
	meta: MemoMeta,
	captures: Capture[],
	date: string
) {
	const ids = new Set(Array.isArray(meta.includedCaptureIds) ? meta.includedCaptureIds : []);
	const additions: string[] = [];
	for (const c of captures) {
		const day = new Date(c.createdAt);
		const local = `${day.getFullYear()}-${String(day.getMonth() + 1).padStart(2, '0')}-${String(day.getDate()).padStart(2, '0')}`;
		if (
			c.kind !== 'task' &&
			(local === date || (c.kind === 'note' && c.today === date)) &&
			!ids.has(c.id)
		) {
			additions.push(c.text);
			ids.add(c.id);
		}
	}
	return { text: [content, ...additions].filter(Boolean).join('\n\n'), ids: [...ids] };
}
export function memoRichDocument(content: string, original: string, ids: string[]) {
	const meta = memoMeta(original),
		document = { ...createDocument(), blocks: [createTextBlock('paragraph', content)] };
	// Keep the previous formatted document intact once, while the active document follows the plain text.
	const legacy =
		meta.originalRichDocument ||
		(original && meta.format !== 'netaq-plain-memo-v1' ? original : '');
	return JSON.stringify({
		format: 'netaq-plain-memo-v1',
		document,
		checks: {},
		folds: {},
		includedCaptureIds: ids,
		...(legacy ? { originalRichDocument: legacy } : {})
	});
}
