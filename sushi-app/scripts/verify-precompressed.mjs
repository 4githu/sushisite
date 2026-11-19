import { readdir, readFile, writeFile, rename } from 'node:fs/promises';
import path from 'node:path';
import { brotliDecompressSync, gunzipSync, brotliCompressSync, gzipSync } from 'node:zlib';

// A successful adapter build must not publish empty/stale compressed variants.
// Browsers prefer Brotli and may cache a 200 response even when its body is empty.
export async function verifyPrecompressed(directory) {
	let checked = 0, repaired = 0;
	async function visit(dir) {
		for (const entry of await readdir(dir, { withFileTypes: true })) {
			const file = path.join(dir, entry.name);
			if (entry.isDirectory()) { await visit(file); continue; }
			if (!/\.(br|gz)$/.test(file)) continue;
			const source = await readFile(file.slice(0, -3));
			const compressed = await readFile(file);
			const brotli = file.endsWith('.br');
			let valid = false;
			try { valid = (brotli ? brotliDecompressSync(compressed) : gunzipSync(compressed)).equals(source); } catch {}
			checked++;
			if (!valid) {
				const next = brotli ? brotliCompressSync(source) : gzipSync(source);
				if (!(brotli ? brotliDecompressSync(next) : gunzipSync(next)).equals(source)) throw Error(`Asset compression failed: ${file}`);
				await writeFile(file + '.repair', next);
				await rename(file + '.repair', file);
				repaired++;
			}
		}
	}
	await visit(directory);
	console.log(`Compressed assets verified: ${checked}, repaired: ${repaired}`);
	return { checked, repaired };
}
