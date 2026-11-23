"""Owner-only Reader translation server for an explicitly local personal profile.

Run this module directly: it always binds 127.0.0.1 and refuses proxy headers.
Do not mount it into the multi-user app or expose it through a reverse proxy.
The existing mainauth JWT is an app identity, not a provider account connection.
"""
import argparse
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from personal_project.router import current_user_id
from . import translate_reader_segments


def _local_ip(host: str | None) -> bool:
    try:
        return bool(host) and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def create_app(*, owner_id: int, executable: str, profile_home: str, reader_origin: str | None = None) -> FastAPI:
    if isinstance(owner_id, bool) or not isinstance(owner_id, int) or owner_id <= 0:
        raise ValueError('a positive, server-verified Sushi owner ID is required')
    if not os.path.isabs(executable) or not os.path.isabs(profile_home):
        raise ValueError('absolute Hermes executable and profile paths are required')
    executable_path = Path(executable).resolve(strict=True)
    home = Path(profile_home).resolve(strict=True)
    if not executable_path.is_file() or not os.access(executable_path, os.X_OK) or not home.is_dir():
        raise ValueError('Hermes executable or profile is unavailable')
    settings = (str(executable_path), str(home))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    if reader_origin:
        origin_url = urlsplit(reader_origin)
        if (origin_url.scheme != 'http' or origin_url.hostname not in ('localhost', '127.0.0.1', '::1')
                or not origin_url.port or origin_url.path or origin_url.query or origin_url.fragment
                or origin_url.username or origin_url.password):
            raise ValueError('reader origin must be an exact http loopback origin with a port')
        app.add_middleware(CORSMiddleware, allow_origins=[reader_origin], allow_credentials=True,
                           allow_methods=['POST'], allow_headers=['Content-Type'])

    @app.post('/api/personal/reader/translate')
    async def translate(request: Request, response: Response, user_id: int = Depends(current_user_id)):
        # The personal profile must never be selected from a shared service request.
        if (not request.client or not _local_ip(request.client.host)
                or not request.scope.get('server') or not _local_ip(request.scope['server'][0])
                or request.url.hostname not in ('localhost', '127.0.0.1', '::1')
                or any(name in request.headers for name in ('forwarded', 'x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'x-forwarded-port', 'x-real-ip'))):
            raise HTTPException(status_code=403, detail={'code': 'personal_local_only', 'message': '로컬 연결만 허용됩니다.'})
        origin = request.headers.get('origin')
        if origin:
            parsed = urlsplit(origin)
            request_origin = urlsplit(str(request.base_url))
            same_origin = (parsed.scheme == request_origin.scheme and parsed.hostname == request_origin.hostname
                           and parsed.port == request_origin.port)
            if not same_origin and origin != reader_origin:
                raise HTTPException(status_code=403, detail={'code': 'personal_local_origin', 'message': '로컬 화면만 허용됩니다.'})
        if user_id != owner_id:
            raise HTTPException(status_code=403, detail={'code': 'personal_owner_only', 'message': '지정된 계정만 사용할 수 있습니다.'})
        if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
            raise HTTPException(status_code=415, detail={'code': 'json_required', 'message': 'JSON 요청이 필요합니다.'})
        response.headers['Cache-Control'] = 'no-store, no-cache, max-age=0, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        return await translate_reader_segments(request, user_id, personal_settings=settings)

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description='Run an owner-only local Reader translation server')
    parser.add_argument('--owner-id', type=int, required=True, help='verified Sushi mainauth user id')
    parser.add_argument('--hermes-executable', required=True)
    parser.add_argument('--hermes-home', required=True)
    parser.add_argument('--port', type=int, default=9011)
    parser.add_argument('--reader-origin', help='exact local browser origin, for example http://localhost:5173')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('invalid port')
    import uvicorn
    app = create_app(owner_id=args.owner_id, executable=args.hermes_executable,
                     profile_home=args.hermes_home, reader_origin=args.reader_origin)
    uvicorn.run(app, host='127.0.0.1', port=args.port, proxy_headers=False, access_log=False)


if __name__ == '__main__':
    main()
