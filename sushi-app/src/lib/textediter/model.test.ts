import { describe, expect, it } from 'vitest';
import { alterTable, applyMark, getMarkState, insertTable, replaceSelectionText } from './commands';
import { EditorHistory } from './history';
import { createDocument, createTextBlock, normalizeDocument, toAnalysisJSON } from './model';

describe('textediter document model', () => {
	it('rejects unknown blocks and unsafe mark values while merging identical chunks', () => {
		const document = normalizeDocument({
			documentId: 'safe-document',
			blocks: [
				{
					id: 'paragraph-1',
					type: 'unknown',
					children: [
						{ type: 'text', text: '안녕', bold: true, textColor: 'javascript:alert(1)' },
						{ type: 'text', text: '하세요', bold: true }
					]
				}
			]
		});
		expect(document.blocks[0]?.type).toBe('paragraph');
		if (document.blocks[0]?.type === 'table') throw new Error('unexpected table');
		expect(document.blocks[0]?.children).toEqual([
			{ type: 'text', text: '안녕하세요', bold: true }
		]);
	});

	it('splits a selected range, reports mixed state, and normalizes after removal', () => {
		const document = createDocument();
		const block = document.blocks[0];
		if (!block || block.type === 'table') throw new Error('missing paragraph');
		block.children = [{ type: 'text', text: 'abcdef' }];
		const selection = {
			anchor: { blockId: block.id, offset: 1 },
			focus: { blockId: block.id, offset: 4 }
		};
		const marked = applyMark(document, selection, 'highlightColor', '#fef08a').document;
		expect(
			getMarkState(
				marked,
				{ anchor: { blockId: block.id, offset: 0 }, focus: { blockId: block.id, offset: 6 } },
				'highlightColor',
				'#fef08a'
			)
		).toBe('mixed');
		const analysis = toAnalysisJSON(marked);
		expect(analysis.annotations[0]).toMatchObject({
			blockId: block.id,
			start: 1,
			end: 4,
			text: 'bcd',
			color: '#fef08a'
		});
		const removed = applyMark(marked, selection, 'highlightColor', undefined).document;
		if (removed.blocks[0]?.type === 'table') throw new Error('unexpected table');
		expect(removed.blocks[0]?.children).toEqual([{ type: 'text', text: 'abcdef' }]);
	});

	it('applies a mark across stable block ids', () => {
		const document = createDocument();
		const first = document.blocks[0];
		if (!first || first.type === 'table') throw new Error('missing paragraph');
		first.children = [{ type: 'text', text: 'first' }];
		const second = createTextBlock('paragraph', 'second');
		document.blocks.push(second);
		const selection = {
			anchor: { blockId: first.id, offset: 2 },
			focus: { blockId: second.id, offset: 3 }
		};
		const marked = applyMark(document, selection, 'textColor', '#2563eb').document;
		expect(
			toAnalysisJSON(marked).segments.filter((segment) =>
				segment.formats.some((format) => format.name === 'textColor')
			)
		).toHaveLength(2);
	});

	it('replaces selected text at the captured offset with pending marks', () => {
		const document = createDocument();
		const block = document.blocks[0];
		if (!block || block.type === 'table') throw new Error('missing paragraph');
		block.children = [{ type: 'text', text: 'hello world' }];
		const result = replaceSelectionText(
			document,
			{
				anchor: { blockId: block.id, offset: 6 },
				focus: { blockId: block.id, offset: 11 }
			},
			'Svelte',
			{ bold: true }
		);
		if (result.document.blocks[0]?.type === 'table') throw new Error('unexpected table');
		expect(result.document.blocks[0]?.children).toEqual([
			{ type: 'text', text: 'hello ' },
			{ type: 'text', text: 'Svelte', bold: true }
		]);
		expect(result.selection.focus.offset).toBe(12);
	});

	it('preserves paragraph indentation depth through normalization', () => {
		const document = normalizeDocument({
			documentId: 'indented-document',
			blocks: [
				{
					id: 'paragraph-1',
					type: 'paragraph',
					depth: 2,
					children: [{ type: 'text', text: 'indented' }]
				}
			]
		});
		if (document.blocks[0]?.type === 'table') throw new Error('unexpected table');
		expect(document.blocks[0]?.depth).toBe(2);
	});

	it('preserves table indentation depth and clamps it to the editor limit', () => {
		const document = normalizeDocument({
			documentId: 'indented-table',
			blocks: [
				{
					id: 'table-1',
					type: 'table',
					depth: 20,
					rows: [[{ id: 'cell-1', blocks: [{ type: 'paragraph', children: [{ text: '값' }] }] }]]
				}
			]
		});
		expect(document.blocks[0]?.type).toBe('table');
		expect(document.blocks[0]?.type === 'table' && document.blocks[0].depth).toBe(6);
	});

	it('changes tables and keeps bounded snapshot undo/redo state', () => {
		const initial = createDocument();
		const withTable = insertTable(initial, initial.blocks[0]?.id, 2, 2);
		const table = withTable.blocks[1];
		if (!table || table.type !== 'table') throw new Error('missing table');
		const changed = alterTable(withTable, table.id, 'addRow', 1);
		expect(changed.blocks[1]?.type === 'table' && changed.blocks[1].rows).toHaveLength(3);
		const history = new EditorHistory();
		history.record(initial);
		expect(history.undo(changed).blocks).toHaveLength(1);
		expect(history.redo(initial).blocks).toHaveLength(2);
	});
});
