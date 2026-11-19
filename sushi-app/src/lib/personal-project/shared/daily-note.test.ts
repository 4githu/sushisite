import { it, expect } from 'vitest';
import { richDailyNote, plainDailyNote, restoreDailyChecklist } from './daily-note';
it('upgrades legacy checks without discarding rich marks or unrelated tables', () => {
	const paragraph = {
		type: 'paragraph',
		attrs: { id: 'p' },
		content: [{ type: 'text', text: '자료', marks: [{ type: 'bold' }] }]
	};
	const table = { type: 'table', content: [] };
	const doc = restoreDailyChecklist({ type: 'doc', content: [paragraph, table] }, '- [x] 자료', {
		p: true
	});
	expect(doc.content?.[0].content?.[0]).toEqual({
		type: 'taskItem',
		attrs: { checked: true },
		content: [paragraph]
	});
	expect(doc.content?.[1]).toEqual(table);
});
it('preserves completed and incomplete tasks as interactive native checklist items', () => {
	const text = '# 실험\n- [ ] 준비\n- [x] 완료\n참고사항';
	const doc = richDailyNote(text);
	expect(doc.content?.[1].content?.map((n) => n.attrs?.checked)).toEqual([false, true]);
	expect(plainDailyNote(doc)).toBe(text);
});
it('serializes a newly checked rich task without losing its completion on fallback', () => {
	const doc = richDailyNote('- [ ] 자료 보내기');
	doc.content![0].content![0].attrs!.checked = true;
	expect(plainDailyNote(doc)).toBe('- [x] 자료 보내기');
});
