import http from 'node:http';

// Keep the same API routes and stream uploads/SSE without buffering or changing limits.
const apiPaths = ['/auth', '/api', '/odi/coaching', '/odi/db', '/odi/files', '/odi/xreal_rehear'];
process.env.SUSHI_PROTOCOL_HEADER = 'x-sushi-proto';
const { handler } = await import('../build-node/handler.js');
const server = http.createServer((req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  if (!apiPaths.some(prefix => path === prefix || path.startsWith(prefix + '/'))) {
    // This server binds only to loopback behind the existing Cloudflare tunnel.
    req.headers['x-sushi-proto'] = req.headers['x-forwarded-proto'] === 'https' || String(req.headers.host).endsWith('.chobab.app') || req.headers.host === 'chobab.app' ? 'https' : 'http';
    handler(req, res);
    return;
  }
  const headers = { ...req.headers, 'accept-encoding': 'identity' };
  const upstream = http.request({ hostname: '127.0.0.1', port: 8000,
    path: req.url, method: req.method, headers }, response => {
    res.writeHead(response.statusCode, response.headers);
    response.pipe(res);
  });
  upstream.on('error', () => {
    if (!res.headersSent) res.writeHead(502, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ detail: '서버 연결을 다시 시도해주세요.' }));
  });
  req.on('aborted', () => upstream.destroy());
  res.on('close', () => { if (!res.writableFinished) upstream.destroy(); });
  req.pipe(upstream);
});
server.requestTimeout = 0;
server.listen(Number(process.env.PORT || 5173), '127.0.0.1');
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 10000).unref();
});
