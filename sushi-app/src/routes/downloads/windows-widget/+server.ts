import { createReadStream } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import { join } from 'node:path';
import { Readable } from 'node:stream';
import type { RequestHandler } from './$types';
export const GET: RequestHandler = async () => {
	try {
		const dir = join(process.cwd(), '..', 'windows-widget', 'dist');
		const manifest = JSON.parse(await readFile(join(dir, 'updater-manifest.json'), 'utf8'));
		if (typeof manifest.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(manifest.version)) throw new Error('Invalid update version');
		const filename = `NETAQ-${manifest.version}-x64-setup.exe`;
		const file = join(dir, filename);
		const info = await stat(file);
		return new Response(Readable.toWeb(createReadStream(file)) as ReadableStream<Uint8Array>, {
			headers: {
				'Content-Type': 'application/vnd.microsoft.portable-executable',
				'Content-Length': String(info.size),
				'Content-Disposition': `attachment; filename="${filename}"`,
				'X-Content-Type-Options': 'nosniff',
				'Cache-Control': 'no-cache'
			}
		});
	} catch {
		return new Response('설치 파일을 준비하지 못했어요. 잠시 후 다시 시도해주세요.', {
			status: 503,
			headers: { 'Content-Type': 'text/plain; charset=utf-8' }
		});
	}
};
