import {
	blockText,
	cloneDocument,
	createId,
	createTable,
	createTextBlock,
	normalizeChunks
} from './model';
import type {
	EditorDocument,
	EditorSelection,
	MarkName,
	MarkState,
	TextBlock,
	TextChunk,
	TextMarks
} from './types';

export interface CommandResult {
	document: EditorDocument;
	selection: EditorSelection;
}

function ordered(selection: EditorSelection): [number, number] {
	return selection.anchor.offset <= selection.focus.offset
		? [selection.anchor.offset, selection.focus.offset]
		: [selection.focus.offset, selection.anchor.offset];
}

export function findTextBlock(document: EditorDocument, blockId: string): TextBlock | undefined {
	for (const block of document.blocks) {
		if (block.type !== 'table' && block.id === blockId) return block;
		if (block.type === 'table')
			for (const row of block.rows)
				for (const cell of row) {
					const found = cell.blocks.find((child) => child.id === blockId);
					if (found) return found;
				}
	}
}

function splitRange(
	chunks: TextChunk[],
	start: number,
	end: number,
	change: (chunk: TextChunk) => TextChunk
): TextChunk[] {
	const output: TextChunk[] = [];
	let cursor = 0;
	for (const chunk of chunks) {
		const chunkEnd = cursor + chunk.text.length;
		const left = Math.max(0, start - cursor);
		const right = Math.min(chunk.text.length, end - cursor);
		if (left > 0) output.push({ ...chunk, text: chunk.text.slice(0, left) });
		if (right > left) output.push(change({ ...chunk, text: chunk.text.slice(left, right) }));
		if (right < chunk.text.length)
			output.push({ ...chunk, text: chunk.text.slice(Math.max(left, right)) });
		cursor = chunkEnd;
	}
	return normalizeChunks(output);
}

function valuesInRange(block: TextBlock, selection: EditorSelection, mark: MarkName): unknown[] {
	const [start, end] = ordered(selection);
	const values: unknown[] = [];
	let cursor = 0;
	for (const chunk of block.children) {
		const chunkEnd = cursor + chunk.text.length;
		if (
			(end === start && cursor <= start && start <= chunkEnd) ||
			(cursor < end && chunkEnd > start)
		)
			values.push(chunk[mark]);
		cursor = chunkEnd;
	}
	return values;
}

function textBlocks(document: EditorDocument): TextBlock[] {
	const blocks: TextBlock[] = [];
	for (const block of document.blocks) {
		if (block.type === 'table') {
			for (const row of block.rows) for (const cell of row) blocks.push(...cell.blocks);
		} else blocks.push(block);
	}
	return blocks;
}

function selectedBlocks(document: EditorDocument, selection: EditorSelection) {
	const blocks = textBlocks(document);
	const anchorIndex = blocks.findIndex((block) => block.id === selection.anchor.blockId);
	const focusIndex = blocks.findIndex((block) => block.id === selection.focus.blockId);
	if (anchorIndex < 0 || focusIndex < 0) return [];
	const forward = anchorIndex <= focusIndex;
	const chosen = blocks.slice(
		Math.min(anchorIndex, focusIndex),
		Math.max(anchorIndex, focusIndex) + 1
	);
	const first = forward ? selection.anchor : selection.focus;
	const last = forward ? selection.focus : selection.anchor;
	return chosen.map((block, index) => ({
		block,
		start: index === 0 ? first.offset : 0,
		end: index === chosen.length - 1 ? last.offset : blockText(block).length
	}));
}

export function getMarkState(
	document: EditorDocument,
	selection: EditorSelection | null,
	mark: MarkName,
	value: unknown = true
): MarkState {
	if (!selection) return 'inactive';
	const values = selectedBlocks(document, selection).flatMap(({ block, start, end }) =>
		valuesInRange(
			block,
			{ anchor: { blockId: block.id, offset: start }, focus: { blockId: block.id, offset: end } },
			mark
		)
	);
	if (!values.length) return 'inactive';
	const matching = values.filter((item) => item === value).length;
	return matching === values.length ? 'active' : matching === 0 ? 'inactive' : 'mixed';
}

export function applyMark(
	document: EditorDocument,
	selection: EditorSelection,
	mark: MarkName,
	value: TextMarks[MarkName] | undefined
): CommandResult {
	const next = cloneDocument(document);
	for (const { block, start, end: rawEnd } of selectedBlocks(next, selection)) {
		let end = rawEnd;
		if (start === end) end = Math.min(blockText(block).length, start + 1);
		block.children = splitRange(block.children, start, end, (chunk) => {
			if (value == null || value === false) delete chunk[mark];
			else Object.assign(chunk, { [mark]: value });
			return chunk;
		});
	}
	next.updatedAt = new Date().toISOString();
	return { document: next, selection };
}

export function replaceSelectionText(
	document: EditorDocument,
	selection: EditorSelection,
	text: string,
	marks: TextMarks = {}
): CommandResult {
	const next = cloneDocument(document);
	if (selection.anchor.blockId !== selection.focus.blockId) return { document: next, selection };
	const block = findTextBlock(next, selection.anchor.blockId);
	if (!block) return { document: next, selection };
	const [start, end] = ordered(selection);
	const output: TextChunk[] = [];
	let cursor = 0;
	let inserted = false;
	for (const chunk of block.children) {
		const chunkEnd = cursor + chunk.text.length;
		const before = chunk.text.slice(0, Math.max(0, start - cursor));
		const after = chunk.text.slice(Math.max(0, end - cursor));
		if (before) output.push({ ...chunk, text: before });
		if (!inserted && cursor <= start && start <= chunkEnd) {
			if (text) output.push({ type: 'text', text, ...marks });
			inserted = true;
		}
		if (after && chunkEnd >= end) output.push({ ...chunk, text: after });
		cursor = chunkEnd;
	}
	if (!inserted && text) output.push({ type: 'text', text, ...marks });
	block.children = normalizeChunks(output);
	next.updatedAt = new Date().toISOString();
	const offset = start + text.length;
	return {
		document: next,
		selection: {
			anchor: { blockId: block.id, offset },
			focus: { blockId: block.id, offset }
		}
	};
}

export function replaceBlockText(
	document: EditorDocument,
	blockId: string,
	text: string,
	marks: TextMarks = {}
): EditorDocument {
	const next = cloneDocument(document);
	const block = findTextBlock(next, blockId);
	if (block) block.children = normalizeChunks([{ type: 'text', text, ...marks }]);
	next.updatedAt = new Date().toISOString();
	return next;
}

export function changeBlockType(
	document: EditorDocument,
	blockId: string,
	type: TextBlock['type'],
	level?: 1 | 2 | 3
): EditorDocument {
	const next = cloneDocument(document);
	const block = findTextBlock(next, blockId);
	if (block) {
		block.type = type;
		block.level = type === 'heading' ? (level ?? 1) : undefined;
		block.depth = type === 'bulletList' || type === 'orderedList' ? (block.depth ?? 0) : undefined;
	}
	next.updatedAt = new Date().toISOString();
	return next;
}

export function insertTable(
	document: EditorDocument,
	afterBlockId: string | undefined,
	rows: number,
	columns: number
): EditorDocument {
	const next = cloneDocument(document);
	const index = next.blocks.findIndex((block) => block.id === afterBlockId);
	next.blocks.splice(index < 0 ? next.blocks.length : index + 1, 0, createTable(rows, columns));
	next.updatedAt = new Date().toISOString();
	return next;
}

export function alterTable(
	document: EditorDocument,
	tableId: string,
	action: 'addRow' | 'addColumn' | 'deleteRow' | 'deleteColumn' | 'deleteTable',
	rowIndex = 0,
	columnIndex = 0
): EditorDocument {
	const next = cloneDocument(document);
	const tableIndex = next.blocks.findIndex((block) => block.id === tableId);
	const table = next.blocks[tableIndex];
	if (!table || table.type !== 'table') return next;
	if (action === 'deleteTable') next.blocks.splice(tableIndex, 1);
	else if (action === 'addRow')
		table.rows.splice(
			rowIndex + 1,
			0,
			structuredClone(table.rows[Math.max(0, rowIndex)]).map((cell) => ({
				...cell,
				id: createId('cell'),
				blocks: cell.blocks.map((block) => ({
					...block,
					id: createId('block'),
					children: [{ type: 'text', text: '' }]
				}))
			}))
		);
	else if (action === 'addColumn')
		for (const row of table.rows)
			row.splice(columnIndex + 1, 0, {
				id: createId('cell'),
				blocks: [
					{ id: createId('block'), type: 'paragraph', children: [{ type: 'text', text: '' }] }
				]
			});
	else if (action === 'deleteRow' && table.rows.length > 1) table.rows.splice(rowIndex, 1);
	else if (action === 'deleteColumn' && table.rows[0]?.length > 1)
		for (const row of table.rows) row.splice(columnIndex, 1);
	if (!next.blocks.length) next.blocks.push(createTextBlock());
	next.updatedAt = new Date().toISOString();
	return next;
}
