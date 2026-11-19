// Backdrop dismissal goes through each dialog's own cancel handler, preserving
// saving guards, unsaved editors and memo recovery rather than hiding its DOM.
export function installDialogDismissal(root: HTMLElement) {
	let outside: HTMLDialogElement | null = null;
	const current = () =>
		[...root.querySelectorAll<HTMLDialogElement>('dialog[open]')].at(-1) || null;
	const beyond = (dialog: HTMLDialogElement, event: PointerEvent | MouseEvent) => {
		const r = dialog.getBoundingClientRect();
		return (
			event.clientX < r.left ||
			event.clientX > r.right ||
			event.clientY < r.top ||
			event.clientY > r.bottom
		);
	};
	const down = (event: PointerEvent) => {
		const dialog = current();
		outside = dialog && beyond(dialog, event) ? dialog : null;
	};
	const click = (event: MouseEvent) => {
		const dialog = current();
		if (dialog && dialog === outside && beyond(dialog, event)) {
			const cancelled = new Event('cancel', { cancelable: true });
			if (dialog.dispatchEvent(cancelled)) dialog.close();
		}
		outside = null;
	};
	document.addEventListener('pointerdown', down, true);
	document.addEventListener('click', click, true);
	return () => {
		document.removeEventListener('pointerdown', down, true);
		document.removeEventListener('click', click, true);
	};
}
