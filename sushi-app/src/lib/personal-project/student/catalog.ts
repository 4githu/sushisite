export type Slot = { day_index: number | null; start_time: string | null; end_time: string | null };
export type Course = {
	id: number;
	name: string;
	professor: string;
	department: string;
	departments?: string[];
	sbjt_cd: string;
	lt_no: string;
	credits: number;
	room: string;
	status: string;
	classification: string[];
	slots: Slot[];
};
export type Lesson = {
	title: string;
	weekday: number;
	start: string;
	end: string;
	location: string;
};
export type Term = { id: string; year: string; term: string; label: string; count: number };
export type Catalog = {
	supported?: boolean;
	revision: string;
	terms: Term[];
	source: string;
	sourceUpdatedAt: string;
	importedAt: string;
};
export type Draft = {
	course_ids: number[];
	manual_lessons: Lesson[];
	starts_on: string;
	ends_on: string;
	skip_holidays: boolean;
	excluded_dates: string[];
	revision: number;
};
export const days = ['월', '화', '수', '목', '금', '토', '일'];
export function minutes(time: string) {
	const [h, m] = time.split(':').map(Number);
	return h * 60 + m;
}
export function validSlot(
	s: Slot
): s is Slot & { day_index: number; start_time: string; end_time: string } {
	return (
		s.day_index !== null &&
		s.day_index >= 0 &&
		s.day_index <= 6 &&
		Boolean(
			s.start_time &&
			s.end_time &&
			/^\d{2}:\d{2}$/.test(s.start_time) &&
			/^\d{2}:\d{2}$/.test(s.end_time) &&
			minutes(s.start_time) < minutes(s.end_time)
		)
	);
}
export function courseLessons(c: Course): Lesson[] {
	return c.slots.filter(validSlot).map((s) => ({
		title: c.name,
		weekday: s.day_index,
		start: s.start_time,
		end: s.end_time,
		location: c.room || ''
	}));
}
export function overlaps(a: Lesson, b: Lesson) {
	return a.weekday === b.weekday && a.start < b.end && b.start < a.end;
}
export function times(c: Course) {
	return (
		c.slots
			.filter(validSlot)
			.map((s) => `${days[s.day_index]} ${s.start_time}–${s.end_time}`)
			.join(' · ') || '시간 미정'
	);
}
export function termDates(term: Term) {
	const summer = term.term === 'U000200001U000300002',
		winter = term.term === 'U000200002U000300002';
	return {
		starts_on: `${term.year}-${summer ? '06-22' : winter ? '12-21' : term.term.startsWith('U000200001') ? '03-01' : '09-01'}`,
		ends_on: winter
			? `${Number(term.year) + 1}-02-15`
			: `${term.year}-${summer ? '08-15' : term.term.startsWith('U000200001') ? '06-30' : '12-31'}`
	};
}

export function academicSlot(term: Term, admission: number | null, offset = 0) {
	if (!admission) return '';
	const index =
		(Number(term.year) - admission) * 2 + (term.term.startsWith('U000200001') ? 0 : 1) - offset;
	return index < 0
		? ''
		: term.term.endsWith('U000300002')
			? `${Math.floor(index / 2) + 1}학년 ${index % 2 === 0 ? '여름' : '겨울'} 계절`
			: `${Math.floor(index / 2) + 1}-${(index % 2) + 1}`;
}
