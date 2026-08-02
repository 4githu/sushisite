import type {
	AnalysisDocument,
	EditorBlock,
	EditorDocument,
	TableCell,
	TextBlock,
	TextChunk,
	TextMarks
} from './types';

const COLORS = /^#[0-9a-f]{6}$/i;
export const FONT_SIZES = [12, 16, 20, 28] as const;

export function createId(prefix = 'node'): string {
	return `${prefix}-${cryptoSafeId()}`;
}

function cryptoSafeId(): string {
	if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
	return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function createTextBlock(type: TextBlock['type'] = 'paragraph', text = ''): TextBlock {
	return { id: createId('block'), type, children: [{ type: 'text', text }] };
}

export function createDocument(): EditorDocument {
	const now = new Date().toISOString();
	return {
		version: 1,
		documentId: createId('document'),
		createdAt: now,
		updatedAt: now,
		blocks: [createTextBlock()]
	};
}

export function createTable(rows = 2, columns = 2): EditorBlock {
	const safeRows = Math.min(10, Math.max(1, rows));
	const safeColumns = Math.min(10, Math.max(1, columns));
	return {
		id: createId('table'),
		type: 'table',
		rows: Array.from({ length: safeRows }, () =>
			Array.from({ length: safeColumns }, () => ({
				id: createId('cell'),
				blocks: [createTextBlock()]
			}))
		)
	};
}

function cleanMarks(value: unknown): TextMarks {
	const input = value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
	const marks: TextMarks = {};
	for (const key of ['bold', 'italic', 'underline', 'strike', 'code'] as const)
		if (input[key] === true) marks[key] = true;
	if (FONT_SIZES.includes(input.fontSize as (typeof FONT_SIZES)[number]))
		marks.fontSize = input.fontSize as TextMarks['fontSize'];
	if (typeof input.fontFamily === 'string' && /^[\w\s가-힣,'" -]{1,80}$/.test(input.fontFamily))
		marks.fontFamily = input.fontFamily;
	if (typeof input.textColor === 'string' && COLORS.test(input.textColor))
		marks.textColor = input.textColor;
	if (typeof input.highlightColor === 'string' && COLORS.test(input.highlightColor))
		marks.highlightColor = input.highlightColor;
	return marks;
}

function sameMarks(a: TextChunk, b: TextChunk): boolean {
	return [
		'bold',
		'italic',
		'underline',
		'strike',
		'code',
		'fontSize',
		'fontFamily',
		'textColor',
		'highlightColor'
	].every((key) => a[key as keyof TextMarks] === b[key as keyof TextMarks]);
}

export function normalizeChunks(chunks: unknown): TextChunk[] {
	if (!Array.isArray(chunks)) return [{ type: 'text', text: '' }];
	const result: TextChunk[] = [];
	for (const raw of chunks) {
		if (!raw || typeof raw !== 'object') continue;
		const item = raw as Record<string, unknown>;
		if (typeof item.text !== 'string') continue;
		const chunk: TextChunk = {
			type: 'text',
			text: item.text.slice(0, 100_000),
			...cleanMarks(item)
		};
		const previous = result.at(-1);
		if (previous && sameMarks(previous, chunk)) previous.text += chunk.text;
		else result.push(chunk);
	}
	return result.length ? result : [{ type: 'text', text: '' }];
}

function normalizeTextBlock(raw: Record<string, unknown>): TextBlock {
	const allowed = ['paragraph', 'heading', 'blockquote', 'codeBlock', 'bulletList', 'orderedList'];
	const type = allowed.includes(String(raw.type)) ? (raw.type as TextBlock['type']) : 'paragraph';
	const block: TextBlock = {
		id: typeof raw.id === 'string' && raw.id ? raw.id : createId('block'),
		type,
		children: normalizeChunks(raw.children)
	};
	if (type === 'heading') block.level = raw.level === 2 || raw.level === 3 ? raw.level : 1;
	if (typeof raw.depth === 'number') block.depth = Math.max(0, Math.min(6, raw.depth));
	return block;
}

function normalizeCell(raw: unknown): TableCell {
	const input = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
	const blocks = Array.isArray(input.blocks)
		? input.blocks
				.slice(0, 20)
				.map((block) => normalizeTextBlock((block ?? {}) as Record<string, unknown>))
		: [createTextBlock()];
	return {
		id: typeof input.id === 'string' && input.id ? input.id : createId('cell'),
		blocks: blocks.length ? blocks : [createTextBlock()]
	};
}

export function normalizeDocument(value: unknown): EditorDocument {
	if (!value || typeof value !== 'object') return createDocument();
	const input = value as Record<string, unknown>;
	const now = new Date().toISOString();
	const blocks: EditorBlock[] = [];
	if (Array.isArray(input.blocks)) {
		for (const raw of input.blocks.slice(0, 1000)) {
			if (!raw || typeof raw !== 'object') continue;
			const block = raw as Record<string, unknown>;
			if (block.type === 'table' && Array.isArray(block.rows)) {
				const rows = block.rows
					.slice(0, 50)
					.map((row) => (Array.isArray(row) ? row.slice(0, 20).map(normalizeCell) : []))
					.filter((row) => row.length > 0);
				if (rows.length && rows.some((row) => row.length))
					blocks.push({
						id: typeof block.id === 'string' ? block.id : createId('table'),
						type: 'table',
						...(typeof block.depth === 'number'
							? { depth: Math.max(0, Math.min(6, block.depth)) }
							: {}),
						rows
					});
			} else blocks.push(normalizeTextBlock(block));
		}
	}
	return {
		version: 1,
		documentId: typeof input.documentId === 'string' ? input.documentId : createId('document'),
		createdAt: typeof input.createdAt === 'string' ? input.createdAt : now,
		updatedAt: now,
		blocks: blocks.length ? blocks : [createTextBlock()]
	};
}

export function cloneDocument(document: EditorDocument): EditorDocument {
	return normalizeDocument(JSON.parse(JSON.stringify(document)));
}

export function blockText(block: TextBlock): string {
	return block.children.map((chunk) => chunk.text).join('');
}

export function toAnalysisJSON(document: EditorDocument): AnalysisDocument {
	const segments: AnalysisDocument['segments'] = [];
	const annotations: AnalysisDocument['annotations'] = [];
	const visit = (block: TextBlock) => {
		let offset = 0;
		for (const chunk of block.children) {
			const end = offset + chunk.text.length;
			const formats = Object.entries(chunk)
				.filter(
					([key, value]) => !['type', 'text'].includes(key) && value !== false && value != null
				)
				.map(([name, value]) => ({
					name: name as keyof TextMarks,
					value: value as boolean | number | string
				}));
			segments.push({
				blockId: block.id,
				blockType: block.type,
				start: offset,
				end,
				text: chunk.text,
				formats
			});
			if (chunk.highlightColor)
				annotations.push({
					type: 'highlight',
					blockId: block.id,
					start: offset,
					end,
					color: chunk.highlightColor,
					text: chunk.text
				});
			offset = end;
		}
	};
	for (const block of document.blocks) {
		if (block.type === 'table')
			for (const row of block.rows)
				for (const cell of row) for (const child of cell.blocks) visit(child);
		else visit(block);
	}
	return { version: 1, documentId: document.documentId, segments, annotations };
}
