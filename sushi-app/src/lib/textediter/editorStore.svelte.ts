import { applyMark, getMarkState } from './commands';
import { EditorHistory } from './history';
import { createDocument, normalizeDocument } from './model';
import type { EditorDocument, EditorSelection, MarkName, MarkState, TextMarks } from './types';

export class EditorStore {
	document = $state<EditorDocument>(createDocument());
	selection = $state<EditorSelection | null>(null);
	pendingMarks = $state<TextMarks>({});
	readonly = $state(false);
	#history = new EditorHistory();

	constructor(initialValue?: EditorDocument | null, readonly = false) {
		this.document = normalizeDocument(initialValue);
		this.readonly = readonly;
	}

	setDocument(value: unknown, record = true, typing = false) {
		if (record) this.#history.record(this.document, typing);
		this.document = normalizeDocument(value);
	}

	mutate(next: EditorDocument, typing = false) {
		this.#history.record(this.document, typing);
		this.document = next;
	}

	markState(mark: MarkName, value: unknown = true): MarkState {
		if (
			this.selection &&
			this.selection.anchor.blockId === this.selection.focus.blockId &&
			this.selection.anchor.offset === this.selection.focus.offset &&
			mark in this.pendingMarks
		)
			return this.pendingMarks[mark] === value ? 'active' : 'inactive';
		return getMarkState(this.document, this.selection, mark, value);
	}

	setMark(mark: MarkName, value: TextMarks[MarkName] | undefined) {
		const collapsed =
			!this.selection ||
			(this.selection.anchor.blockId === this.selection.focus.blockId &&
				this.selection.anchor.offset === this.selection.focus.offset);
		if (collapsed) {
			if (value == null || value === false) delete this.pendingMarks[mark];
			else Object.assign(this.pendingMarks, { [mark]: value });
			return;
		}
		this.mutate(applyMark(this.document, this.selection, mark, value).document);
	}

	undo() {
		this.document = this.#history.undo(this.document);
	}
	redo() {
		this.document = this.#history.redo(this.document);
	}
	get canUndo() {
		return this.#history.canUndo;
	}
	get canRedo() {
		return this.#history.canRedo;
	}
	resetHistory() {
		this.#history.reset();
	}
}
