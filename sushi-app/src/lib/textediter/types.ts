export type BlockType =
	| 'paragraph'
	| 'heading'
	| 'blockquote'
	| 'codeBlock'
	| 'bulletList'
	| 'orderedList'
	| 'table';
export type FontSize = 12 | 16 | 20 | 28;

export interface TextMarks {
	bold?: boolean;
	italic?: boolean;
	underline?: boolean;
	strike?: boolean;
	code?: boolean;
	fontSize?: FontSize;
	fontFamily?: string;
	textColor?: string;
	highlightColor?: string;
}

export interface TextChunk extends TextMarks {
	type: 'text';
	text: string;
}

export interface TextBlock {
	id: string;
	type: Exclude<BlockType, 'table'>;
	level?: 1 | 2 | 3;
	depth?: number;
	children: TextChunk[];
}

export interface TableCell {
	id: string;
	blocks: TextBlock[];
}

export interface TableBlock {
	id: string;
	type: 'table';
	depth?: number;
	rows: TableCell[][];
}

export type EditorBlock = TextBlock | TableBlock;

export interface EditorDocument {
	version: 1;
	documentId: string;
	createdAt: string;
	updatedAt: string;
	blocks: EditorBlock[];
}

export interface TextPoint {
	blockId: string;
	offset: number;
	cellId?: string;
	chunkIndex?: number;
	chunkOffset?: number;
}

export interface EditorSelection {
	anchor: TextPoint;
	focus: TextPoint;
}

export type MarkName = keyof TextMarks;
export type MarkState = 'active' | 'inactive' | 'mixed';

export interface AnalysisSegment {
	blockId: string;
	blockType: TextBlock['type'];
	start: number;
	end: number;
	text: string;
	formats: Array<{ name: MarkName; value: boolean | number | string }>;
}

export interface AnalysisDocument {
	version: 1;
	documentId: string;
	segments: AnalysisSegment[];
	annotations: Array<{
		type: 'highlight';
		blockId: string;
		start: number;
		end: number;
		color: string;
		text: string;
	}>;
}
