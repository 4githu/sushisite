"""Mount only Reader and its distinct assets into the existing home gateway."""
import re

MARKER = '// Paiper Reader isolated build'
SNIPPET = '''
  // Paiper Reader isolated build; the existing apps keep their current build.
  if (process.env.PAIPER_READER_UPSTREAM === 'http://127.0.0.1:5194' &&
      hostname === 'chobab.app' &&
      (path === '/personal-project/reader' || path.startsWith('/personal-project/reader/') ||
       path === '/__paiper' || path.startsWith('/__paiper/'))) {
    const reader = http.request({ hostname: '127.0.0.1', port: 5194, path: req.url,
      method: req.method, headers: { ...req.headers, 'x-sushi-proto': 'https' } }, response => {
      res.writeHead(response.statusCode, response.headers);
      response.pipe(res);
    });
    reader.on('error', () => {
      if (!res.headersSent) res.writeHead(503, { 'content-type': 'text/plain; charset=utf-8', 'cache-control': 'no-store' });
      res.end('논문 리더에 다시 연결해 주세요.');
    });
    req.on('aborted', () => reader.destroy());
    res.on('close', () => { if (!res.writableFinished) reader.destroy(); });
    req.pipe(reader);
    return;
  }
'''


def mount(source):
    if MARKER in source:
        return source
    pattern = r'^(  const hostname = [^\n]+;\n)'
    result, count = re.subn(pattern, lambda m: m[0] + SNIPPET, source, flags=re.M)
    if count != 1:
        raise RuntimeError('Existing gateway layout changed; review before mounting Reader')
    return result
