import type { Course, Lesson } from './catalog';
import { courseLessons, overlaps } from './catalog';
let rows: Course[] = [];
let text: string[] = [];
self.onmessage = ({ data }) => {
	if (data.type === 'load') {
		rows = data.courses;
		text = rows.map((c) =>
			[c.name, c.professor, c.department, c.sbjt_cd, c.lt_no]
				.join(' ')
				.normalize('NFKC')
				.toLocaleLowerCase()
		);
		self.postMessage({ id: data.id, loaded: true });
		return;
	}
	const start = performance.now();
	const words = (data.q || '')
		.normalize('NFKC')
		.toLocaleLowerCase()
		.trim()
		.split(/\s+/)
		.filter(Boolean);
	const matches = rows.filter(
		(c, i) =>
			words.every((w: string) => text[i].includes(w)) &&
			(!data.department || (c.departments || [c.department]).includes(data.department)) &&
			(!data.classification || c.classification.includes(data.classification)) &&
			(data.day === '' || c.slots.some((s) => String(s.day_index) === data.day)) &&
			(!data.credits || c.credits === Number(data.credits)) &&
			(!data.after || courseLessons(c).some((s) => s.start >= data.after)) &&
			(!data.before || courseLessons(c).some((s) => s.end <= data.before)) &&
			(!data.emptyOnly ||
				!courseLessons(c).some((a) => (data.lessons as Lesson[]).some((b) => overlaps(a, b))))
	);
	self.postMessage({
		id: data.id,
		courses: matches.slice(data.offset, data.offset + 40),
		total: matches.length,
		departments: [...new Set(rows.flatMap((c) => c.departments || [c.department]))].sort(),
		classifications: [...new Set(rows.flatMap((c) => c.classification))].sort(),
		duration: performance.now() - start
	});
};
