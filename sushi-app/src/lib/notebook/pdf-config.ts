export function pdfOptions() {
	const base = import.meta.env.BASE_URL || '/';
	return {
		cMapUrl: base + 'pdfjs/cmaps/',
		cMapPacked: true,
		standardFontDataUrl: base + 'pdfjs/standard_fonts/',
		wasmUrl: base + 'pdfjs/wasm/'
	};
}
