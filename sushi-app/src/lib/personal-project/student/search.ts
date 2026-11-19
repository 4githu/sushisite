import Worker from './search.worker?worker';
import { request } from '../shared/api';
import type { Course } from './catalog';
export class CourseSearch {
	worker = new Worker();
	sequence = 0;
	loadGeneration = 0;
	pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();
	constructor() {
		this.worker.onmessage = ({ data }) => {
			this.pending.get(data.id)?.resolve(data);
			this.pending.delete(data.id);
		};
		this.worker.onerror = () => {
			for (const p of this.pending.values())
				p.reject(Error('검색 도구를 시작하지 못했습니다. 다시 불러와주세요.'));
			this.pending.clear();
		};
	}
	send(data: Record<string, unknown>): Promise<any> {
		const id = ++this.sequence;
		return new Promise((resolve, reject) => {
			this.pending.set(id, { resolve, reject });
			this.worker.postMessage({ ...data, id });
		});
	}
	async load(term: string, revision: string) {
		const generation = ++this.loadGeneration;
		const key = new Request(
			`${location.origin}/__catalog/${encodeURIComponent(revision)}/${encodeURIComponent(term)}`
		);
		let cache: Cache | undefined;
		let data: { courses: Course[] } | undefined;
		try {
			cache = await caches.open('ondo-public-catalog-v2');
			const response = await cache.match(key);
			if (response) data = await response.json();
		} catch {
			/* Network fallback when storage is unavailable. */
		}
		if (!data) {
			data = await request(`/student/catalog/${encodeURIComponent(term)}/snapshot`);
			try {
				await cache?.put(key, new Response(JSON.stringify(data)));
			} catch {
				/* Quota does not block search. */
			}
		}
		if (generation !== this.loadGeneration) return;
		await this.send({ type: 'load', courses: data!.courses });
	}
	destroy() {
		for (const p of this.pending.values()) p.reject(Error('검색 화면을 닫았습니다.'));
		this.pending.clear();
		this.worker.terminate();
	}
}
