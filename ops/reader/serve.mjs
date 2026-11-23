import http from 'node:http';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const build = resolve(process.argv[2]);
const revision = process.env.PAIPER_REVISION;
if (!/^[a-f0-9]{40}$/.test(revision || '')) throw new Error('A release revision is required');
const { handler } = await import(pathToFileURL(`${build}/handler.js`).href);
const server = http.createServer((req, res) => {
  if (new URL(req.url, 'http://localhost').pathname === '/personal-project/reader/_release') {
    res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ revision }));
    return;
  }
  res.setHeader('X-Paiper-Revision', revision);
  handler(req, res);
});
server.requestTimeout = 0;
server.listen(Number(process.env.PAIPER_PORT || 5194), '127.0.0.1');
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 10_000).unref();
});
