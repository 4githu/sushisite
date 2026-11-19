// One owner and one command build both hosts from the exact same Svelte sources.
import { spawnSync } from 'node:child_process';
import { verifyPrecompressed } from './verify-precompressed.mjs';
import { cp, mkdir, readFile, readdir } from 'node:fs/promises';
import {createHash} from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const repo = fileURLToPath(new URL('../', import.meta.url));
const host =
	process.env.NETAQ_NOTEBOOK_HOST ||
	'/Users/sagi/Documents/Codex/2026-11-12/https-chatgpt-com-s-cx-6af54e1bfb2c81c292bedf68015a3816/outputs/netaq-notebook';
const digest=createHash('sha256');
for(const dir of ['src/lib/notebook','src/lib/personal-project/editor','src/lib/personal-project/notes']){for(const name of (await readdir(path.join(repo,dir))).sort()){if(/\.(svelte|ts|css)$/.test(name))digest.update(await readFile(path.join(repo,dir,name)));}}
const buildId=digest.digest('hex').slice(0,16);
function run(command, args, cwd, env = {}) {
	const result = spawnSync(command, args, {
		cwd,
		env: { ...process.env, ...env },
		stdio: 'inherit'
	});
	if (result.status !== 0) throw Error(command + ' failed: ' + result.status);
}
for (const target of [path.join(repo, 'static/pdfjs'), path.join(host, 'public/pdfjs')]) {
	await mkdir(target, { recursive: true });
	for (const dir of ['cmaps', 'standard_fonts', 'wasm'])
		await cp(path.join(repo, 'node_modules/pdfjs-dist', dir), path.join(target, dir), {
			recursive: true
		});
}
run('npm', ['run', 'check'], repo);
run('npm', ['run', 'build'], repo, { BUILD_TARGET: 'node', BUILD_OUT: 'build-node', VITE_NOTEBOOK_BUILD_ID:buildId });
run('npm', ['run', 'build', '--', '--outDir', 'dist-netaq-next'], host, {
	NOTEBOOK_BASE: '/notes/', VITE_NOTEBOOK_BUILD_ID:buildId
});
await verifyPrecompressed(path.join(repo, 'build-node/client'));
// Keep the old immutable assets so open notebook tabs can finish using their loaded version.
await cp(path.join(host, 'dist-netaq-next'), path.join(host, 'dist-netaq'), { recursive: true });
run('launchctl', ['kickstart', '-k', 'gui/' + process.getuid() + '/app.sushisite.frontend'], repo);
console.log('Shared notebook build '+buildId);
console.log('Both hosts released: NETAQ drive and https://netaq.chobab.app/notes/');
