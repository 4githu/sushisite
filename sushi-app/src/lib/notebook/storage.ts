import type { NotebookData } from './types';
let dbPromise: Promise<IDBDatabase> | undefined;
function db() {
	return (dbPromise ??= new Promise((resolve, reject) => {
		const r = indexedDB.open('netaq-notes', 1);
		r.onupgradeneeded = () => r.result.createObjectStore('workspace');
		r.onsuccess = () => resolve(r.result);
		r.onerror = () => reject(r.error);
	}));
}
export async function readValue(key: string): Promise<any> {
	const d = await db();
	return new Promise((resolve, reject) => {
		const tx = d.transaction('workspace');
		const r = tx.objectStore('workspace').get(key);
		tx.oncomplete = () => resolve(r.result);
		tx.onerror = () => reject(tx.error);
	});
}
export async function writeValue(key: string, value: unknown): Promise<void> {
	const d = await db();
	return new Promise((resolve, reject) => {
		const tx = d.transaction('workspace', 'readwrite');
		tx.objectStore('workspace').put(value, key);
		tx.oncomplete = () => resolve();
		tx.onerror = () => reject(tx.error);
	});
}
export function createLocalNotebookStorage(id = 'current') {
	let lastSource: ArrayBuffer | null | undefined,
		splitSource = false;
	const key = id === 'current' ? 'current' : 'document:' + id;
	const sourceKey = id === 'current' ? 'pdf-source' : key + ':pdf-source';
	return {
		async read(_url = ''): Promise<NotebookData | null> {
			const d = await db();
			return new Promise((resolve, reject) => {
				const tx = d.transaction('workspace'),
					store = tx.objectStore('workspace');
				const a = store.get(key),
					b = store.get(sourceKey);
				tx.oncomplete = () => {
					const meta = a.result;
					if (meta) {
						splitSource = b.result !== undefined;
						lastSource = splitSource ? b.result : meta.pdf;
						resolve({ ...meta, pdf: lastSource });
					} else resolve(null);
				};
				tx.onerror = () => reject(tx.error);
			});
		},
		async save(value: NotebookData): Promise<void> {
			const d = await db();
			return new Promise((resolve, reject) => {
				const tx = d.transaction('workspace', 'readwrite'),
					store = tx.objectStore('workspace');
				const { pdf, ...meta } = value;
				store.put(meta, key);
				if (!splitSource || pdf !== lastSource) store.put(pdf ?? null, sourceKey);
				tx.oncomplete = () => {
					lastSource = pdf;
					splitSource = true;
					resolve();
				};
				tx.onerror = () => reject(tx.error);
			});
		}
	};
}
const legacy = createLocalNotebookStorage();
export const read = legacy.read;
export const save = legacy.save;
