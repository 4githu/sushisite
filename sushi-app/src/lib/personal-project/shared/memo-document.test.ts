import { describe, it, expect } from 'vitest';
import { mergeMemoCaptures, memoText, memoRichDocument, memoMeta } from './memo-document';
import type { Capture } from './capture';
const capture = {
	id: 'one',
	text: '위젯 기록',
	createdAt: '2026-11-16T12:00:00',
	kind: 'inbox',
	today: null,
	done: false
} as Capture;
describe('one plain memo', () => {
	it('includes saved captures once while leaving task records in the task list', () => {
		const first = mergeMemoCaptures(
			'기존 메모',
			{},
			[capture, { ...capture, id: 'task', kind: 'task' }],
			'2026-11-16'
		);
		expect(first.text).toBe('기존 메모\n\n위젯 기록');
		expect(
			mergeMemoCaptures(first.text, { includedCaptureIds: first.ids }, [capture], '2026-11-16').text
		).toBe(first.text);
	});
	it('does not pull a different day into today', () => {
		expect(mergeMemoCaptures('', {}, [capture], '2026-11-17').text).toBe('');
	});
	it('renders legacy checklists as plain text without dropping completion information', () => {
		expect(memoText('- [ ] 안내\n- [x] 회신')).toBe('안내\n완료: 회신');
	});
	it('preserves the formatted source once and keeps subsequent edits in sync', () => {
		const legacy = '{"document":{"blocks":[{"type":"table"}]}}';
		const first = memoRichDocument('새 메모', legacy, ['one']);
		const next = memoMeta(memoRichDocument('수정', first, ['one']));
		expect(next.originalRichDocument).toBe(legacy);
		expect((next.document as any).blocks[0].children[0].text).toBe('수정');
		expect(JSON.stringify(next)).not.toContain('originalRichDocument\\\":');
	});
});
