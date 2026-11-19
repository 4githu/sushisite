import { expect, it } from 'vitest';
import { createDocument, createTextBlock } from '$lib/textediter/model';
import { toRich, fromRich } from './document';
it('keeps editable drawing strokes, image size and alignment through saved JSON', () => {
	const rich = {
		type: 'doc',
		content: [
			{
				type: 'image',
				attrs: {
					src: '/api/personal/resources/example',
					alt: '그림 메모',
					widthPct: 45,
					objectAlign: 'right',
					drawing: [
						{
							id: 'stroke-a',
							kind: 'pen',
							color: '#25262b',
							width: 3,
							points: [
								{ x: 20, y: 30, pressure: 0.5 },
								{ x: 80, y: 60, pressure: 0.7 }
							]
						}
					]
				}
			}
		]
	};
	const stored = JSON.parse(JSON.stringify(fromRich(rich, createDocument())));
	expect(toRich(stored)).toEqual(rich);
});
it('preserves Aura identities across conversion and student swaps', () => {
	const a = createDocument();
	a.blocks = [{ ...createTextBlock('paragraph', '학생 가 질문'), id: 'shared-question' }];
	const b = createDocument();
	b.blocks = [{ ...createTextBlock('paragraph', '학생 나 질문'), id: 'shared-question' }];
	const ra = fromRich(toRich(a), a),
		rb = fromRich(toRich(b), b);
	expect(ra.blocks[0].id).toBe('shared-question');
	expect(rb.blocks[0].id).toBe('shared-question');
	expect(JSON.stringify(ra)).toContain('학생 가');
	expect(JSON.stringify(rb)).not.toContain('학생 가');
	expect(toRich(ra)).toEqual(ra.richContent);
});
it('retains nested task state and table sizing in canonical JSON', () => {
	const rich = {
		type: 'doc',
		content: [
			{
				type: 'taskList',
				content: [
					{
						type: 'taskItem',
						attrs: { checked: true },
						content: [
							{
								type: 'paragraph',
								attrs: { id: 'task' },
								content: [{ type: 'text', text: '체크한 일' }]
							}
						]
					}
				]
			},
			{
				type: 'table',
				content: [
					{
						type: 'tableRow',
						content: [
							{
								type: 'tableCell',
								attrs: { id: 'cell', colwidth: [150] },
								content: [
									{
										type: 'paragraph',
										attrs: { id: 'cell-text' },
										content: [{ type: 'text', text: '표 내용' }]
									}
								]
							}
						]
					}
				]
			}
		]
	};
	expect(toRich(fromRich(rich, createDocument()))).toEqual(rich);
});
it('keeps indentation and pasted colors in both the editor and AI blocks', () => {
	const rich = {
		type: 'doc',
		content: [
			{ type: 'paragraph', attrs: { id: 'first', indent: 1 }, content: [{ type: 'text', text: '첫 단계', marks: [{ type: 'highlight', attrs: { color: 'rgb(254, 240, 138)' } }] }] },
			{ type: 'paragraph', attrs: { id: 'second', indent: 2 }, content: [{ type: 'text', text: '둘째 단계', marks: [{ type: 'textStyle', attrs: { color: 'rgb(220, 38, 38)', backgroundColor: '#fed7aa' } }] }] }
		]
	};
	const stored = JSON.parse(JSON.stringify(fromRich(rich, createDocument())));
	expect(stored.blocks.map((block: { depth: number }) => block.depth)).toEqual([1, 2]);
	expect(stored.blocks[0].children[0].highlightColor).toBe('#fef08a');
	expect(stored.blocks[1].children[0].textColor).toBe('#dc2626');
	expect(stored.blocks[1].children[0].highlightColor).toBe('#fed7aa');
	expect(toRich(stored)).toEqual(rich);
});
