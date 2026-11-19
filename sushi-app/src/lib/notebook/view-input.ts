/** Layout and page-turn direction are intentionally independent. */
export function visiblePageIndices(
	mode: string,
	index: number,
	count: number,
	twoPage = false
): number[] {
	if (mode === 'continuous') return Array.from({ length: count }, (_, i) => i);
	const first = twoPage ? Math.floor(index / 2) * 2 : index;
	return twoPage && first + 1 < count ? [first, first + 1] : [first];
}
export function visiblePageRows(
	mode: string,
	index: number,
	count: number,
	twoPage: boolean
): number[][] {
	const indices = visiblePageIndices(mode, index, count, twoPage);
	const rows: number[][] = [];
	for (let i = 0; i < indices.length; i += twoPage ? 2 : 1)
		rows.push(indices.slice(i, i + (twoPage ? 2 : 1)));
	return rows;
}
export function adjacentPage(index: number, direction: number, twoPage: boolean): number {
	return twoPage ? Math.floor(index / 2) * 2 + direction * 2 : index + direction;
}
export function penOverride(e: {
	pointerType: string;
	buttons: number;
	button: number;
	type?: string;
}): 'eraser' | 'lasso' | null {
	if (e.pointerType !== 'pen') return null;
	if (e.buttons & 32 || (e.type === 'pointerdown' && e.button === 5)) return 'eraser';
	if (e.buttons & 2 || (e.type === 'pointerdown' && e.button === 2)) return 'lasso';
	return null;
}
/** Desktop-site mode can remove Android from both Chrome and Samsung's UA.
 * UA client hints retain the platform. The Linux/touch fallback covers older
 * Chromium versions; Windows pens must keep their standard button handling. */
export function usesAndroidPen(nav: {
	userAgent: string;
	platform?: string;
	maxTouchPoints?: number;
	userAgentData?: { platform: string };
}): boolean {
	if (/Windows|Macintosh|CrOS/i.test(nav.userAgent)) return false;
	return (
		/Android/i.test(nav.userAgentData?.platform || '') ||
		/Android/i.test(nav.userAgent) ||
		(/Linux/i.test(nav.userAgent + ' ' + (nav.platform || '')) &&
			(nav.maxTouchPoints || 0) > 0 &&
			/Chrome|SamsungBrowser/i.test(nav.userAgent))
	);
}

/** Samsung/Chromium can report a barrel held in hover as primary buttons=1.
 * Recognize it ONLY before a tip down, and only on Android. Ordinary tip contact
 * also uses 1, so never infer a button from a writing move or a long-press menu.
 * Once touching, browsers which merge both bits cannot expose mid-stroke release;
 * keep that override for this contact only and clear on lift/cancel/blur/exit.
 * https://bugzilla.mozilla.org/show_bug.cgi?id=2082727#c3
 * https://github.com/delfinchiknakite-netizen/excalidraw-stylus-menu
 */
export function createPenInput(android: () => boolean = () => false) {
	let contact = false,
		pointer: number | undefined,
		hoverBarrel = false,
		standardSeen = false;
	return {
		reset() {
			contact = false;
			pointer = undefined;
			hoverBarrel = false;
			standardSeen = false;
		},
		update(e: {
			type: string;
			pointerType: string;
			pointerId: number;
			pressure: number;
			buttons: number;
			button: number;
		}) {
			if (e.pointerType !== 'pen') return { contact: false, override: null };
			if (pointer !== e.pointerId) {
				contact = false;
				hoverBarrel = false;
				pointer = e.pointerId;
				standardSeen = false;
			}
			if (e.buttons & 34) {
				standardSeen = true;
				hoverBarrel = false;
			}
			if (e.type === 'pointerup' || e.type === 'pointercancel') {
				contact = false;
				hoverBarrel = false;
			} else if (e.type === 'pointerdown') {
				contact = e.pressure > 0 || !!(e.buttons & 1);
			} else if (e.type === 'pointermove') {
				if (!contact && android() && !standardSeen) hoverBarrel = e.buttons === 1;
				if (e.pressure === 0 && !(e.buttons & 1)) {
					contact = false;
					hoverBarrel = false;
				} else if (e.pressure > 0 && e.buttons & 34) contact = true;
			}
			const standard = penOverride(e);
			// Standard bits always take precedence (including an inverted eraser).
			return { contact, override: standard ?? (hoverBarrel ? ('eraser' as const) : null) };
		}
	};
}
