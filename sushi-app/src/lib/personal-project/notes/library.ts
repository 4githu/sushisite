import { request } from '../shared/api';
import { checkPersonalAuth } from '../shared/auth';
import { createDriveAdapter } from '../../notebook/drive-adapter';
import {
	createLocalNotebookStorage,
	readValue,
	writeValue,
	read as readLegacy
} from '../../notebook/storage';
import { type PaperTemplate, readPaperDefault } from '../../notebook/paper';
export type NoteEntry = {
	id: string;
	title: string;
	paper: PaperTemplate;
	updatedAt: number;
	deleted?: boolean;
};
export type NoteSection = { id: string; title: string; notes: NoteEntry[] };
export type NoteBook = { id: string; title: string; sections: NoteSection[] };
export type NoteLibrary = {
	version: 1;
	notebooks: NoteBook[];
	active: { notebook: string; section: string; note: string };
	defaults: PaperTemplate;
};
export function makeLibrary(): NoteLibrary {
	const notebook = crypto.randomUUID(),
		section = crypto.randomUUID(),
		note = 'current';
	return {
		version: 1,
		notebooks: [
			{
				id: notebook,
				title: '내 노트북',
				sections: [
					{
						id: section,
						title: '빠른 메모',
						notes: [
							{
								id: note,
								title: '첫 번째 페이지',
								paper: readPaperDefault(),
								updatedAt: Date.now()
							}
						]
					}
				]
			}
		],
		active: { notebook, section, note },
		defaults: readPaperDefault()
	};
}
export async function openLibrary() {
	const user =
		import.meta.env.DEV && import.meta.env.VITE_NOTEBOOK_LOCAL === '1'
			? null
			: await checkPersonalAuth();
	const remote = !!user;
	const owner = user?.data.id || 'guest';
	const localKey = 'library:' + owner;
	let revision = 0,
		saving = Promise.resolve();
	const saved = remote ? await request<any>('/documents/notes%3Alibrary%3Av1') : null;
	let data: NoteLibrary | undefined = remote ? saved.data : await readValue(localKey);
	if (data && (!Array.isArray(data.notebooks) || data.version !== 1))
		throw Error('노트 목록을 읽지 못했습니다. 기존 데이터는 보존했습니다.');
	const fresh = !data;
	data ??= makeLibrary();
	revision = saved?.revision || 0;
	const document = (id: string) => {
		const local = createLocalNotebookStorage(remote ? `owner:${owner}:${id}` : id);
		if (!remote) return local;
		const cloud = createDriveAdapter(id, true);
		return {
			read: async (url = '') => cloud.read(url),
			save: async (value: any) => {
				await local.save(value);
				await cloud.save(value);
			}
		};
	};
	const save = (value: NoteLibrary) => {
		const snapshot = structuredClone(value);
		const op = saving
			.catch(() => {})
			.then(async () => {
				if (remote) {
					const result = await request<any>('/documents/notes%3Alibrary%3Av1', {
						method: 'PUT',
						body: { revision, data: snapshot }
					});
					revision = result.revision;
				}
				await writeValue(localKey, snapshot);
			});
		saving = op;
		return op;
	};
	// Existing local content is only uploaded by an explicit "copy to account" action.
	const legacy = await readLegacy();
	const localCatalog: NoteLibrary | undefined = remote
		? await readValue('library:guest')
		: undefined;
	const importSummary =
		remote && (localCatalog || legacy)
			? {
					title:
						localCatalog?.notebooks.map((b) => b.title).join(', ') ||
						legacy?.title ||
						'이 기기 노트'
				}
			: null;
	async function copyLocalToAccount(target: NoteLibrary) {
		if (!remote) throw Error('로그인 후 계정으로 복사할 수 있습니다');
		const source =
			localCatalog?.notebooks ||
			(legacy
				? [
						{
							id: 'legacy',
							title: '이 기기 노트',
							sections: [
								{
									id: 'legacy',
									title: '가져온 페이지',
									notes: [
										{
											id: 'current',
											title: legacy.title || '가져온 노트',
											paper: readPaperDefault(),
											updatedAt: Date.now()
										}
									]
								}
							]
						}
					]
				: []);
		const books = structuredClone(source);
		for (const book of books) {
			book.id = crypto.randomUUID();
			for (const section of book.sections) {
				section.id = crypto.randomUUID();
				for (const note of section.notes) {
					const stored = await createLocalNotebookStorage(note.id).read('');
					note.id = crypto.randomUUID();
					if (stored) {
						const destination = document(note.id);
						await destination.read('');
						await destination.save(stored);
					}
				}
			}
		}
		target.notebooks.push(...books);
		if (books.length) {
			const b = books[0],
				s = b.sections[0];
			target.active = {
				notebook: b.id,
				section: s?.id || '',
				note: s?.notes.find((n) => !n.deleted)?.id || ''
			};
		}
		await save(target);
	}
	if (fresh) {
		if (!remote && legacy)
			data.notebooks[0].sections[0].notes[0].title = legacy.title || '가져온 노트';
		await save(data);
	}
	// Deep links from the drive resolve only against this account's catalog.
	const query = new URLSearchParams(location.search),
		bookId = query.get('notebook'),
		sectionId = query.get('section'),
		noteId = query.get('note');
	if (bookId || sectionId || noteId) {
		const book = data.notebooks.find((b) =>
			bookId
				? b.id === bookId
				: b.sections.some((s) => s.id === sectionId || s.notes.some((n) => n.id === noteId))
		);
		const section = book?.sections.find((s) =>
			sectionId ? s.id === sectionId : noteId ? s.notes.some((n) => n.id === noteId) : true
		);
		const note = section?.notes.find((n) => !n.deleted && (noteId ? n.id === noteId : true));
		if (book && section)
			data.active = { notebook: book.id, section: section.id, note: note?.id || '' };
	}
	return { data, remote, save, document, importSummary, copyLocalToAccount };
}
