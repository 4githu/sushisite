const paths: Record<string, string> = {
	spread:
		'<rect x="2" y="4" width="9" height="16" rx="1"/><rect x="13" y="4" width="9" height="16" rx="1"/>',
	home: '<path d="m3 11 9-8 9 8M5 9v12h5v-7h4v7h5V9"/>',
	pen: '<path d="m5 20 1.7-6.2L16.8 3.7a1.8 1.8 0 0 1 2.5 0l1 1a1.8 1.8 0 0 1 0 2.5L10.2 17.3 5 20Z"/><path d="m14.8 5.7 3.5 3.5m-11.6 4.6 3.5 3.5M4 22h15"/>',
	eraser:
		'<path d="m4.2 13 8.6-9a2 2 0 0 1 2.8-.1l4.1 3.9a2 2 0 0 1 .1 2.8l-8.6 9H8.6l-4.3-4.1a1.8 1.8 0 0 1-.1-2.5Z"/><path d="m9.4 7.5 6.9 6.6M10 19.6h10"/>',
	highlight: '<path d="m5 14 8-9 6 5-8 9H7l-2-5Z"/><path d="m9 10 6 5M6 19l-2 3h7"/>',
	lasso:
		'<path d="M6 17C1 14 3 6 11 5c9-1 12 8 5 12-3 2-7 2-9 0" stroke-dasharray="2.5 2.5"/><path d="M7 17c-3-3-5 0-2 2 3 1 3 3 1 4"/>',
	text: '<path d="M5 6V4h14v2M12 4v16M8 20h8"/>',
	image:
		'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m4 18 5-5 3 3 4-5 5 6"/>',
	camera: '<path d="M8 6 10 3h4l2 3h4v15H4V6Z"/><circle cx="12" cy="13" r="4"/>',
	pages:
		'<rect x="4" y="3" width="12" height="16" rx="1.5"/><path d="M8 7h5M8 10h5M8 13h4M18 7h2v14H8v-1"/>',
	hand: '<path d="M8 11V5a1.5 1.5 0 0 1 3 0v5-7a1.5 1.5 0 0 1 3 0v7-5a1.5 1.5 0 0 1 3 0v6-3a1.5 1.5 0 0 1 3 0v7c0 5-3 7-7 7-3 0-5-2-6-4l-3-5c-1-2 1-3 2-2l2 2Z"/>',
	memo: '<path d="M4 4h16v12H9l-5 4V4Z"/><path d="M8 8h8M8 12h5"/>',
	trash: '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
	open: '<path d="M3 7h7l2 3h9l-3 10H3V7Zm0 0V4h7l2 3h7v3"/>',
	plus: '<path d="M12 4v16M4 12h16"/>',
	download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
	undo: '<path d="m8 4-5 5 5 5M3 9h10a7 7 0 0 1 0 14"/>',
	redo: '<path d="m16 4 5 5-5 5m5-5H11a7 7 0 0 0 0 14"/>',
	close: '<path d="m6 6 12 12M6 18 18 6"/>'
};
export const icon = (name: string) =>
	`<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.pen}</svg>`;
