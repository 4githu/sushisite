import { expect, it } from 'vitest';
import { withTemplateMutation } from './templateMutation';
it('blocks overlapping save and prepare and releases after completion', async () => {
	let release!: () => void;
	const first = withTemplateMutation(() => new Promise<void>((resolve) => (release = resolve)));
	await expect(withTemplateMutation(async () => 42)).rejects.toThrow('환경을 저장하거나');
	release();
	await first;
	await expect(withTemplateMutation(async () => 42)).resolves.toBe(42);
});
it('releases the draft when saving fails', async () => {
	await expect(
		withTemplateMutation(async () => {
			throw new Error('network');
		})
	).rejects.toThrow('network');
	await expect(withTemplateMutation(async () => true)).resolves.toBe(true);
});
