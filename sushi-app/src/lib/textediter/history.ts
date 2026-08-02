import { cloneDocument } from './model';
import type { EditorDocument } from './types';

export class EditorHistory {
	#past: EditorDocument[] = [];
	#future: EditorDocument[] = [];
	#lastInput = 0;
	constructor(private limit = 60) {}
	record(document: EditorDocument, groupTyping = false) {
		const now = Date.now();
		if (!groupTyping || now - this.#lastInput > 800) this.#past.push(cloneDocument(document));
		this.#lastInput = groupTyping ? now : 0;
		this.#past = this.#past.slice(-this.limit);
		this.#future = [];
	}
	undo(current: EditorDocument) {
		const previous = this.#past.pop();
		if (!previous) return current;
		this.#future.push(cloneDocument(current));
		return previous;
	}
	redo(current: EditorDocument) {
		const next = this.#future.pop();
		if (!next) return current;
		this.#past.push(cloneDocument(current));
		return next;
	}
	reset() {
		this.#past = [];
		this.#future = [];
		this.#lastInput = 0;
	}
	get canUndo() {
		return this.#past.length > 0;
	}
	get canRedo() {
		return this.#future.length > 0;
	}
}
