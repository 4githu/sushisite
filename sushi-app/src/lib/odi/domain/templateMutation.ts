import { get, writable } from 'svelte/store';
export const templateMutationBusy = writable(false);
/** One draft cannot be saved and prepared concurrently; both operations may assign its first ID. */
export async function withTemplateMutation<T>(operation: () => Promise<T>): Promise<T> {
	if (get(templateMutationBusy))
		throw new Error('환경을 저장하거나 세션을 준비하고 있습니다. 완료 후 다시 시도해 주세요.');
	templateMutationBusy.set(true);
	try {
		return await operation();
	} finally {
		templateMutationBusy.set(false);
	}
}
