import { uploadResource } from '../personal-project/resources/api';
import { request } from '../personal-project/shared/api';
import { getDocument } from 'pdfjs-dist';
import { packPage, unpackPage } from './page-storage';
import { pdfOptions } from './pdf-config';
const escape = (s: string) =>
	s.replace(
		/[&<>"']/g,
		(c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!
	);
export function createDriveAdapter(resourceId: string, notebook = false) {
	const key = `${notebook ? 'note' : 'pdf'}:${resourceId}:v2`;
	let pdfUrl = '';
	let lastPdf: ArrayBuffer | null = null;
	let revision = 0;
	let saving = Promise.resolve();
	const written = new Set<string>();
	return {
		async read(url: string) {
			const current = await request<any>(`/documents/${encodeURIComponent(key)}`);
			revision = current.revision;
			if (current.data?.engine === 'netaq-notebook-v2') {
				pdfUrl = current.data.pdfUrl || '';
				const pages = [];
				for (const p of current.data.pages) {
					if (p.chunks) {
						const chunks = [];
						for (const key of p.chunks) {
							const saved = await request<any>(`/documents/${encodeURIComponent(key)}`);
							if (typeof saved.data?.blob !== 'string')
								throw Error('페이지 저장 조각을 불러오지 못했습니다.');
							chunks.push(saved.data.blob);
							written.add(key);
						}
						pages.push({ ...p, items: await unpackPage(chunks) });
					} else pages.push(p);
				}
				return { ...current.data, pages };
			}
			if (notebook) return null;
			const legacy = await request<any>(`/documents/${encodeURIComponent('pdf:' + resourceId)}`);
			const task = getDocument({ ...pdfOptions(), url, withCredentials: true });
			const pdf = await task.promise;
			try {
				const first = await pdf.getPage(1),
					fv = first.getViewport({ scale: 1 });
				if (!legacy.data)
					return {
						pages: Array.from({ length: pdf.numPages }, (_, i) => ({
							id: crypto.randomUUID(),
							source: i,
							w: fv.width,
							h: fv.height,
							items: []
						})),
						pageIndex: 0
					};
				const pages = [];
				for (const p of legacy.data.pages) {
					let v = fv;
					if (p.source !== null && (p.strokes.length || p.notes.length || p.sourceReady))
						v = (await pdf.getPage(p.source + 1)).getViewport({
							scale: 1,
							rotation: p.sourceReady === false ? undefined : p.rotation
						});
					const items = [
						...p.strokes.map((s: any) => ({
							...s,
							kind: 'stroke',
							highlight: s.kind === 'highlight',
							points: s.points.map((q: any) => {
								const [x, y] = v.convertToViewportPoint(q.x, q.y);
								return { x, y, p: q.pressure };
							})
						})),
						...p.notes.map((n: any) => {
							const [x, y] = v.convertToViewportPoint(n.x, n.y);
							return {
								id: n.id,
								kind: 'text',
								x,
								y: y - n.size,
								w: 300,
								h: 60,
								html: `<p style="color:${/^#[0-9a-f]{6}$/i.test(n.color) ? n.color : '#242529'}">${escape(n.text).replace(/\n/g, '<br>')}</p>`
							};
						})
					];
					pages.push({
						id: p.id,
						source: p.source,
						rotation: p.sourceReady === false ? undefined : p.rotation,
						w: p.source === null ? p.width : v.width,
						h: p.source === null ? p.height : v.height,
						items
					});
				}
				return { pages, pageIndex: 0 };
			} finally {
				await pdf.loadingTask.destroy();
			}
		},
		save(value: any) {
			const result = saving
				.catch(() => {})
				.then(async () => {
					if (notebook && value.pdf && value.pdf !== lastPdf) {
						const resource = await uploadResource(
							new File([value.pdf], value.pdfName || 'notebook.pdf', { type: 'application/pdf' })
						);
						pdfUrl = resource.url;
						lastPdf = value.pdf;
					}
					if (notebook && !value.pdf && !value.pdfUrl && !value.pdfName) pdfUrl = '';
					const pages = [];
					for (let i = 0; i < value.pages.length; i++) {
						const { items, chunks: oldChunks, ...meta } = value.pages[i];
						if (!items.length) {
							pages.push({ ...meta, items: [] });
							continue;
						}
						const packed = await packPage(items);
						const keys = [];
						for (let j = 0; j < packed.chunks.length; j++) {
							const chunkKey = `${key}:p:${i}:${packed.hash.slice(0, 24)}:${j}`;
							keys.push(chunkKey);
							if (written.has(chunkKey)) continue;
							try {
								await request(`/documents/${encodeURIComponent(chunkKey)}`, {
									method: 'PUT',
									body: { revision: 0, data: { blob: packed.chunks[j] } }
								});
							} catch (error) {
								const existing = await request<any>(`/documents/${encodeURIComponent(chunkKey)}`);
								if (existing.data?.blob !== packed.chunks[j]) throw error;
							}
							written.add(chunkKey);
						}
						pages.push({ ...meta, chunks: keys });
					}
					const data = {
						title: value.title,
						...(notebook ? { pdfUrl } : {}),
						pdfName: value.pdfName,
						pageIndex: value.pageIndex,
						pages,
						engine: 'netaq-notebook-v2',
						version: 2
					};
					const response = await request<any>(`/documents/${encodeURIComponent(key)}`, {
						method: 'PUT',
						body: { revision, data }
					});
					revision = response.revision;
				});
			saving = result;
			return result;
		}
	};
}
