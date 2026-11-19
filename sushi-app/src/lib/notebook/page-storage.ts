// Bounded immutable chunks keep textbook annotations below the API's 500KB document limit.
export async function packPage(items: unknown[]) {
	const json = JSON.stringify(items);
	const stream = new Blob([json]).stream().pipeThrough(new CompressionStream('gzip'));
	const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
	let binary = '';
	for (let i = 0; i < bytes.length; i += 16384)
		binary += String.fromCharCode(...bytes.subarray(i, i + 16384));
	const data = btoa(binary);
	const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
		.map((b) => b.toString(16).padStart(2, '0'))
		.join('');
	return { hash, chunks: data.match(/.{1,300000}/g) || [''] };
}
export async function unpackPage(chunks: string[]) {
	const bytes = Uint8Array.from(atob(chunks.join('')), (c) => c.charCodeAt(0));
	const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
	return JSON.parse(await new Response(stream).text());
}
