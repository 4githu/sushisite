import type { JSONContent } from '@tiptap/core';
import { createDocument, createId, normalizeDocument } from '$lib/textediter/model';
import type { EditorDocument, TextBlock, TextChunk } from '$lib/textediter/types';

function inline(block: TextBlock): JSONContent[] {
	return block.children
		.filter((c) => c.text)
		.map((c) => ({
			type: 'text',
			text: c.text,
			marks: [
				...(['bold', 'italic', 'underline', 'strike', 'code'] as const)
					.filter((k) => c[k])
					.map((type) => ({ type })),
				...(c.highlightColor ? [{ type: 'highlight', attrs: { color: c.highlightColor } }] : []),
				...(c.textColor || c.fontFamily || c.fontSize
					? [
							{
								type: 'textStyle',
								attrs: {
									color: c.textColor,
									fontFamily: c.fontFamily,
									fontSize: c.fontSize ? `${c.fontSize}px` : undefined
								}
							}
						]
					: [])
			]
		}));
}
function textNode(b: TextBlock): JSONContent {
	const attrs = { id: b.id, ...(b.level ? { level: b.level } : {}) };
	if (b.type === 'bulletList' || b.type === 'orderedList')
		return {
			type: b.type,
			content: [{ type: 'listItem', content: [{ type: 'paragraph', attrs, content: inline(b) }] }]
		};
	if (b.type === 'blockquote')
		return { type: 'blockquote', content: [{ type: 'paragraph', attrs, content: inline(b) }] };
	return { type: b.type, attrs, content: inline(b) };
}
export function toRich(value: EditorDocument | null): JSONContent {
	const d = normalizeDocument(value);
	if (d.richContent?.type === 'doc') return d.richContent;
	return {
		type: 'doc',
		content: d.blocks.map((b) =>
			b.type === 'table'
				? {
						type: 'table',
						attrs: { id: b.id },
						content: b.rows.map((row) => ({
							type: 'tableRow',
							content: row.map((cell) => ({
								type: 'tableCell',
								attrs: { id: cell.id },
								content: cell.blocks.map(textNode)
							}))
						}))
					}
				: textNode(b)
		)
	};
}
export function fromRich(rich: JSONContent, base: EditorDocument | null): EditorDocument {
	const d = base || createDocument();
	const blocks: EditorDocument['blocks'] = [];
	function chunks(n: JSONContent): TextChunk[] {
		return (n.content || []).flatMap((c) =>
			c.type === 'text'
				? [
						{
							type: 'text' as const,
							text: c.text || '',
							...Object.fromEntries(
								(c.marks || []).flatMap((m) =>
									m.type === 'highlight'
										? [['highlightColor', m.attrs?.color]]
										: m.type === 'textStyle'
											? Object.entries({
													textColor: m.attrs?.color,
													fontFamily: m.attrs?.fontFamily,
													fontSize: parseInt(m.attrs?.fontSize) || undefined
												}).filter(([, v]) => v !== undefined)
											: [[m.type, true]]
								)
							)
						}
					]
				: c.type === 'hardBreak'
					? [{ type: 'text' as const, text: '\n' }]
					: chunks(c)
		);
	}
	function text(n: JSONContent): TextBlock {
		return {
			id: n.attrs?.id || createId('block'),
			type: n.type === 'heading' ? 'heading' : n.type === 'codeBlock' ? 'codeBlock' : 'paragraph',
			level: n.attrs?.level,
			children: chunks(n)
		};
	}
	function walk(n: JSONContent) {
		if (n.type === 'table') {
			blocks.push({
				id: n.attrs?.id || createId('table'),
				type: 'table',
				rows: (n.content || []).map((r) =>
					(r.content || []).map((c) => ({
						id: c.attrs?.id || createId('cell'),
						blocks: (c.content || []).map(text)
					}))
				)
			});
			return;
		}
		if (['paragraph', 'heading', 'codeBlock', 'detailsSummary'].includes(n.type || '')) {
			blocks.push(text(n));
			return;
		}
		if (n.type === 'image' || n.type === 'attachment') {
			blocks.push({
				id: n.attrs?.id || createId('block'),
				type: 'paragraph',
				children: [{ type: 'text', text: n.attrs?.alt || n.attrs?.name || '첨부파일' }]
			});
			return;
		}
		(n.content || []).forEach(walk);
	}
	walk(rich);
	return {
		...d,
		version: 1,
		schemaVersion: 2,
		updatedAt: new Date().toISOString(),
		blocks: blocks.length ? blocks : createDocument().blocks,
		richContent: rich
	};
}
