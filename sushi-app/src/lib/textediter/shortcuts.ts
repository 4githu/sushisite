export const SHORTCUTS = {
	bold: { key: 'b', modifier: true },
	italic: { key: 'i', modifier: true },
	underline: { key: 'u', modifier: true },
	undo: { key: 'z', modifier: true },
	redo: { key: 'z', modifier: true, shift: true },
	// Alt를 함께 사용해 브라우저의 일반적인 Ctrl/Cmd 단축키와 충돌을 피한다.
	textColor: { key: 'c', modifier: true, alt: true },
	highlightColor: { key: 'h', modifier: true, alt: true }
} as const;

export function matchesShortcut(
	event: KeyboardEvent,
	shortcut: (typeof SHORTCUTS)[keyof typeof SHORTCUTS]
) {
	return (
		event.key.toLowerCase() === shortcut.key &&
		(event.ctrlKey || event.metaKey) === shortcut.modifier &&
		event.shiftKey === ('shift' in shortcut && shortcut.shift === true) &&
		event.altKey === ('alt' in shortcut && shortcut.alt === true)
	);
}
