import type { JSONContent } from '@tiptap/core';
// Upgrade legacy per-block check state without flattening formatting, tables or attachments.
export function restoreDailyChecklist(
	rich: JSONContent,
	note: string,
	checks: Record<string, boolean>
): JSONContent {
	const lines = note.split('\n');
	const content: JSONContent[] = [];
	for (const [index, node] of (rich.content || []).entries()) {
		const task = /^\s*- \[([ xX])\]/.exec(lines[index] || '');
		if (node.type === 'paragraph' && (task || checks[node.attrs?.id])) {
			let list = content.at(-1);
			if (list?.type !== 'taskList') {
				list = { type: 'taskList', content: [] };
				content.push(list);
			}
			list.content!.push({
				type: 'taskItem',
				attrs: { checked: !!checks[node.attrs?.id] || task?.[1].toLowerCase() === 'x' },
				content: [node]
			});
		} else content.push(node);
	}
	return { ...rich, content };
}
export function richDailyNote(text: string, ids: string[] = []): JSONContent {
	const content: JSONContent[] = [];
	for (const [index, line] of text.split('\n').entries()) {
		const task = /^\s*- \[([ xX])\]\s?(.*)$/.exec(line);
		const heading = /^(#{1,3}) (.*)$/.exec(line);
		const value = task ? task[2] : heading ? heading[2] : line;
		const paragraph: JSONContent = {
			type: heading ? 'heading' : 'paragraph',
			attrs: {
				id: ids[index] || crypto.randomUUID(),
				...(heading ? { level: heading[1].length } : {})
			},
			content: value ? [{ type: 'text', text: value }] : []
		};
		if (task) {
			let list = content.at(-1);
			if (list?.type !== 'taskList') {
				list = { type: 'taskList', content: [] };
				content.push(list);
			}
			list.content!.push({
				type: 'taskItem',
				attrs: { checked: task[1].toLowerCase() === 'x' },
				content: [paragraph]
			});
		} else content.push(paragraph);
	}
	return { type: 'doc', content };
}
export function plainDailyNote(doc: JSONContent): string {
	const value = (n: JSONContent): string =>
		n.type === 'text'
			? n.text || ''
			: n.type === 'hardBreak'
				? '\n'
				: (n.content || []).map(value).join('');
	const lines: string[] = [];
	function walk(n: JSONContent) {
		if (n.type === 'taskItem') {
			lines.push(`- [${n.attrs?.checked ? 'x' : ' '}] ${value(n)}`);
			return;
		}
		if (['paragraph', 'heading', 'codeBlock'].includes(n.type || '')) {
			lines.push((n.type === 'heading' ? '#'.repeat(n.attrs?.level || 1) + ' ' : '') + value(n));
			return;
		}
		if (n.type === 'image' || n.type === 'attachment') {
			lines.push(n.attrs?.alt || n.attrs?.name || '첨부파일');
			return;
		}
		(n.content || []).forEach(walk);
	}
	walk(doc);
	return lines.join('\n');
}
