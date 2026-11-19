export type InkPoint = { x: number; y: number; p?: number };
/** Normalized objects retain imported extension fields from older notebook versions. */
export type NotebookItem = { id: string; kind: string; [key: string]: any };
export type NotebookPage = {
	paper?: import('./paper').PaperTemplate;
	id?: string;
	source?: number | null;
	rotation?: number;
	w: number;
	h: number;
	items: NotebookItem[];
};
export type NotebookData = {
	title?: string;
	pages: NotebookPage[];
	pdf?: ArrayBuffer | null;
	pdfName?: string;
	pdfUrl?: string;
	pageIndex?: number;
};
