"""Account-gated reverse proxy for the Hermes web dashboard.

The AI Office hostname is routed to this Sushi FastAPI service. Sushi's existing
password login remains the only credential verifier; this middleware checks a
separate account-to-system binding before proxying any dashboard HTTP or WS
request to the loopback-only Hermes server.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlsplit

import httpx
from fastapi import Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from auth import JMT, service, userdb
from browser_space_sync import handle as handle_browser_space_sync
import deskrpg_sso


AI_OFFICE_HOST = os.getenv("AI_OFFICE_HOST", "ai.chobab.app").strip().lower()
HERMES_UPSTREAM = os.getenv("HERMES_OFFICE_UPSTREAM", "http://127.0.0.1:9119").rstrip("/")
SYSTEM_ID = "hermes-office"
SESSION_COOKIE = "mainauth"
BROWSER_SYNC_PATH = "/api/browser-sync"
BROWSER_SYNC_DOWNLOAD_PATH = "/api/browser-sync/extension.zip"
BROWSER_SYNC_ARCHIVE = Path.home() / "Documents/Hermes-Workspace/50-browser-sync/Ego-Space-Sync.zip"
BROWSER_SYNC_EXTENSION_ORIGIN = "chrome-extension://pagdeaccggmacjihecbecgbcihhdcpoh"
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def ensure_access_schema() -> None:
    """Create the system registry and account-system relationship tables."""
    with userdb.get_connection() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS ai_office_systems (
                system_id TEXT PRIMARY KEY,
                hostname TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                upstream_url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS ai_office_account_systems (
                account_id INTEGER NOT NULL,
                system_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (account_id, system_id)
            )"""
        )
        db.execute(
            """INSERT OR IGNORE INTO ai_office_systems(system_id, hostname, label, upstream_url, enabled)
               VALUES (?, ?, ?, ?, 1)
               """,
            (SYSTEM_ID, AI_OFFICE_HOST, "Hermes AI Office", HERMES_UPSTREAM),
        )
        db.commit()


def system_for_account(account_id: int, hostname: str):
    with userdb.get_connection() as db:
        row = db.execute(
            """SELECT s.system_id, s.label, s.upstream_url, a.role
               FROM ai_office_account_systems AS a
               JOIN ai_office_systems AS s ON s.system_id = a.system_id
               JOIN users AS u ON u.id = a.account_id
               WHERE a.account_id=? AND lower(s.hostname)=?
                 AND a.enabled=1 AND s.enabled=1""",
            (account_id, hostname.lower()),
        ).fetchone()
    return dict(row) if row else None


def registered_hostname(hostname: str) -> bool:
    with userdb.get_connection() as db:
        return db.execute(
            "SELECT 1 FROM ai_office_systems WHERE lower(hostname)=? AND enabled=1",
            (hostname.lower(),),
        ).fetchone() is not None


def bind_account(email: str, system_id: str = SYSTEM_ID, role: str = "owner") -> int:
    """Bind an existing Sushi account to a registered system; return its ID."""
    email = email.strip().lower()
    if role not in {"owner", "viewer"}:
        raise ValueError("role must be owner or viewer")
    ensure_access_schema()
    with userdb.get_connection() as db:
        account = db.execute(
            "SELECT id FROM users WHERE lower(email)=?", (email,)
        ).fetchone()
        if not account:
            raise ValueError("Sushi account not found")
        system = db.execute(
            "SELECT 1 FROM ai_office_systems WHERE system_id=? AND enabled=1",
            (system_id,),
        ).fetchone()
        if not system:
            raise ValueError("system not found")
        account_id = int(account["id"])
        db.execute(
            """INSERT INTO ai_office_account_systems(account_id, system_id, role, enabled)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(account_id, system_id) DO UPDATE SET
                   role=excluded.role, enabled=1""",
            (account_id, system_id, role),
        )
        db.commit()
    return account_id


def list_bindings():
    ensure_access_schema()
    with userdb.get_connection() as db:
        rows = db.execute(
            """SELECT u.email, a.system_id, a.role, a.enabled
               FROM ai_office_account_systems AS a
               JOIN users AS u ON u.id=a.account_id
               ORDER BY lower(u.email), a.system_id"""
        ).fetchall()
    return [dict(row) for row in rows]


def register_system(system_id: str, hostname: str, label: str, upstream_url: str) -> None:
    """Register or update a dashboard service with a loopback-only upstream."""
    parsed = urlsplit(upstream_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("upstream must be an HTTP loopback URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("upstream URL cannot contain credentials, query, or fragment")
    if (not system_id or len(system_id) > 80 or not hostname or len(hostname) > 253
            or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for char in hostname)
            or not label.strip() or len(label) > 120):
        raise ValueError("invalid system id or label")
    ensure_access_schema()
    with userdb.get_connection() as db:
        db.execute(
            """INSERT INTO ai_office_systems(system_id, hostname, label, upstream_url, enabled)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(system_id) DO UPDATE SET
                   hostname=excluded.hostname, label=excluded.label,
                   upstream_url=excluded.upstream_url, enabled=1""",
            (system_id, hostname.lower(), label.strip(), upstream_url.rstrip("/")),
        )
        db.commit()


def unbind_account(email: str, system_id: str = SYSTEM_ID) -> bool:
    ensure_access_schema()
    with userdb.get_connection() as db:
        row = db.execute(
            "SELECT id FROM users WHERE lower(email)=?", (email.strip().lower(),)
        ).fetchone()
        if not row:
            return False
        cur = db.execute(
            "DELETE FROM ai_office_account_systems WHERE account_id=? AND system_id=?",
            (int(row["id"]), system_id),
        )
        db.commit()
        return cur.rowcount > 0


LOGIN_PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>Hermes AI Office 로그인</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#18222d;background:#f3f5f7}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px}
.card{width:min(100%,420px);background:#fff;border:1px solid #e1e6eb;border-radius:18px;padding:34px;box-shadow:0 16px 48px #26374612}
.mark{width:44px;height:44px;border-radius:13px;background:#18222d;color:white;display:grid;place-items:center;font-weight:750;letter-spacing:-1px}
h1{font-size:24px;letter-spacing:-.5px;margin:22px 0 8px}p{color:#687582;line-height:1.55;margin:0 0 24px;font-size:14px}
label{display:block;font-size:13px;font-weight:650;margin:16px 0 7px}input{width:100%;height:46px;border:1px solid #ccd5dd;border-radius:10px;padding:0 12px;font:inherit;background:#fff;color:#18222d}
input:focus{outline:3px solid #dbeafe;border-color:#4c83c3}button{width:100%;height:48px;border:0;border-radius:10px;background:#202c38;color:white;font:inherit;font-weight:700;margin-top:22px;cursor:pointer}
button:disabled{opacity:.62;cursor:wait}.error{min-height:20px;margin:14px 0 0;color:#a93333;font-size:13px}.foot{font-size:12px;color:#84909b;margin-top:22px}
</style></head><body data-next="__NEXT_PATH__"><main class="card"><div class="mark" aria-hidden="true">H</div>
<h1>Hermes AI Office</h1><p>Sushi 계정으로 로그인하세요. 이 계정에 연결된 시스템만 표시됩니다.</p>
<form id="login" method="post" action="/auth/office-login"><label for="email">이메일</label><input id="email" name="email" type="email" autocomplete="username" required autofocus>
<label for="password">비밀번호</label><input id="password" name="password" type="password" autocomplete="current-password" required>
<button id="submit" type="submit">로그인</button><div class="error" id="error" role="alert" aria-live="polite">__ERROR_MESSAGE__</div></form>
<div class="foot">비밀번호는 Sushi 인증 서버에서 확인하며 AI 오피스 시스템에 저장하지 않습니다.</div></main>
<script>
const form=document.getElementById('login'),button=document.getElementById('submit'),error=document.getElementById('error');
function nextPath(){const p=document.body.dataset.next||'/ai-office';return p.startsWith('/')&&!p.startsWith('//')&&!p.includes('\\')?p:'/ai-office'}
// Old login links could carry credentials in the query string. Remove them
// immediately so refreshes, redirects, or copied links cannot retain them.
if(location.search)history.replaceState(null,'',location.pathname+location.hash);
form.addEventListener('submit',async e=>{e.preventDefault();error.textContent='';button.disabled=true;
try{const response=await fetch('/auth/login',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('password').value})});
const result=await response.json();if(!response.ok||!result.success)throw new Error(result.message||'이메일 또는 비밀번호를 확인해주세요.');
document.getElementById('password').value='';location.replace(nextPath());}catch(err){error.textContent=err.message||'로그인에 실패했습니다.';button.disabled=false;}});
</script></body></html>"""


def _host(scope: Scope) -> str:
    for key, value in scope.get("headers", []):
        if key.lower() == b"host":
            return value.decode("latin-1").split(":", 1)[0].lower()
    return ""


def _safe_return_path(request: Request) -> str:
    path = request.url.path
    if path in {"/", "/login"} or path.startswith("/auth/") or not path.startswith("/") or path.startswith("//") or "\\" in path:
        path = "/channels" if _host(request.scope) == deskrpg_sso.HOST else "/office"
    # Never carry query parameters through login. They may contain credentials
    # from an older login link and would re-expose them in browser history/logs.
    return path


def _origin_allowed(origin: str | None, hostname: str, method: str = "GET") -> bool:
    if not origin:
        return method.upper() in {"GET", "HEAD", "OPTIONS"}
    parsed = urlsplit(origin)
    return parsed.scheme == "https" and parsed.netloc.lower() == hostname.lower()


def _browser_sync_origin(request: Request, hostname: str) -> bool:
    origin = request.headers.get("origin")
    return origin == BROWSER_SYNC_EXTENSION_ORIGIN or _origin_allowed(origin, hostname, request.method)


def _browser_sync_cors(response: Response, request: Request) -> Response:
    if request.headers.get("origin") == BROWSER_SYNC_EXTENSION_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = BROWSER_SYNC_EXTENSION_ORIGIN
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    response.headers["Cache-Control"] = "no-store"
    return response


def _account_id(request: Request | WebSocket) -> int | None:
    try:
        payload = JMT.check_jwt(request, SESSION_COOKIE)
        return int(payload["sub"])
    except Exception:
        return None


def _login_response(request: Request, error_message: str = "") -> Response:
    next_path = html.escape(_safe_return_path(request), quote=True)
    return HTMLResponse(
        LOGIN_PAGE.replace("__NEXT_PATH__", next_path).replace("__ERROR_MESSAGE__", html.escape(error_message)),
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "same-origin",
            "X-Content-Type-Options": "nosniff",
        },
        status_code=200,
    )


def _unauthorized(request: Request) -> Response:
    accept = request.headers.get("accept", "")
    is_document = "text/html" in accept or request.url.path in {"/", "/login", "/ai-office"}
    if is_document and request.method in {"GET", "HEAD"}:
        return _login_response(request)
    return JSONResponse(
        {"detail": "Sushi 계정 로그인이 필요합니다."},
        status_code=401,
        headers={"Cache-Control": "no-store"},
    )


def _binding_denied() -> Response:
    return HTMLResponse(
        """<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>접근 권한 없음</title><body style="font:16px -apple-system,BlinkMacSystemFont,sans-serif;max-width:560px;margin:12vh auto;padding:24px;color:#18222d"><h1>이 시스템에 연결된 계정이 아닙니다</h1><p>관리자에게 Sushi 계정과 AI 오피스 시스템 연결을 요청해 주세요.</p><form action="/auth/logout" method="post"><button>로그아웃</button></form></body></html>""",
        status_code=403,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _upstream_url(base: str, scope: Scope) -> str:
    base = base.rstrip("/")
    path = scope.get("raw_path", scope.get("path", "/").encode()).decode("latin-1")
    query = scope.get("query_string", b"").decode("latin-1")
    return f"{base}{path}" + (f"?{query}" if query else "")


async def _proxy_http(request: Request, send: Send, upstream: str, hostname: str, upstream_cookie: str | None = None) -> None:
    upstream_origin = f"{urlsplit(upstream).scheme}://{urlsplit(upstream).netloc}"
    headers: dict[str, str] = {}
    for name, value in request.headers.items():
        lowered = name.lower()
        if lowered in _HOP_BY_HOP or lowered in {"host", "cookie", "authorization", "content-length", "origin", "referer"}:
            continue
        headers[name] = value
    headers["Origin"] = upstream_origin
    headers["X-Forwarded-Host"] = hostname
    headers["X-Forwarded-Proto"] = "https"
    if upstream_cookie:
        headers["Cookie"] = upstream_cookie

    async def body_stream():
        async for chunk in request.stream():
            yield chunk

    client = httpx.AsyncClient(timeout=None, follow_redirects=False)
    try:
        outbound = client.build_request(
            request.method,
            _upstream_url(upstream, request.scope),
            headers=headers,
            content=body_stream() if request.method not in {"GET", "HEAD"} else None,
        )
        response = await client.send(outbound, stream=True)
    except httpx.HTTPError:
        await client.aclose()
        error = JSONResponse({"detail": "Hermes 서버에 연결할 수 없습니다."}, status_code=502)
        await error(scope=request.scope, receive=request.receive, send=send)
        return

    response_headers: list[tuple[bytes, bytes]] = []
    for name, value in response.headers.multi_items():
        lowered = name.lower()
        if lowered in _HOP_BY_HOP or lowered in {"set-cookie", "cache-control"}:
            continue
        if lowered == "location":
            value = value.replace(upstream_origin, f"https://{hostname}")
        response_headers.append((name.encode("latin-1"), value.encode("latin-1")))
    response_headers.extend(
        [
            (b"cache-control", b"private, max-age=31536000, immutable" if upstream_cookie and request.url.path.startswith("/_next/static/") else b"private, no-store"),
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"same-origin"),
        ]
    )

    async def stream_upstream():
        try:
            async for chunk in response.aiter_raw():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    outgoing = StreamingResponse(stream_upstream(), status_code=response.status_code)
    outgoing.raw_headers = response_headers
    await outgoing(scope=request.scope, receive=request.receive, send=send)


async def _proxy_websocket(websocket: WebSocket, upstream: str, upstream_cookie: str | None = None) -> None:
    try:
        from websockets.asyncio.client import connect
    except ImportError:
        await websocket.close(code=1011, reason="WebSocket proxy is unavailable")
        return

    parts = urlsplit(upstream)
    scheme = "wss" if parts.scheme == "https" else "ws"
    target = _upstream_url(upstream, websocket.scope)
    target = target.replace(f"{parts.scheme}://", f"{scheme}://", 1)
    try:
        async with connect(
            target,
            origin=f"{parts.scheme}://{parts.netloc}",
            subprotocols=websocket.scope.get("subprotocols") or None,
            additional_headers={"Cookie": upstream_cookie} if upstream_cookie else None,
            open_timeout=10,
            close_timeout=2,
            max_size=None,
        ) as upstream_ws:
            selected = upstream_ws.subprotocol
            await websocket.accept(subprotocol=selected)

            async def from_client():
                while True:
                    message = await websocket.receive()
                    if message["type"] == "websocket.disconnect":
                        return
                    if message.get("bytes") is not None:
                        await upstream_ws.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream_ws.send(message["text"])

            async def to_client():
                async for message in upstream_ws:
                    if isinstance(message, bytes):
                        await websocket.send_bytes(message)
                    else:
                        await websocket.send_text(message)

            tasks = [asyncio.create_task(from_client()), asyncio.create_task(to_client())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*done, *pending, return_exceptions=True)
    except Exception:
        try:
            await websocket.close(code=1011, reason="Hermes WebSocket unavailable")
        except RuntimeError:
            pass


class AIOfficeGatewayMiddleware:
    """Gate every route on the AI Office hostname, then proxy to Hermes."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        host = _host(scope)
        if scope.get("type") not in {"http", "websocket"} or not host or not registered_hostname(host):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            request = Request(scope, receive=receive)
            path = request.url.path

            if host == deskrpg_sso.HOST and path == "/auth/desk-exchange":
                account_id = deskrpg_sso.consume_ticket(request.query_params.get("ticket", ""))
                binding = system_for_account(account_id, host) if account_id else None
                account = userdb.get_user(user_id=account_id) if binding else None
                if account:
                    token = JMT.make_jwt(account_id, dict(account), ["name", "email", "id"], lifetime_seconds=JMT.MAIN_SESSION_SECONDS)
                    response = RedirectResponse("/channels", status_code=303)
                    response.set_cookie(SESSION_COOKIE, token, httponly=True, secure=True, samesite="lax", path="/", max_age=JMT.MAIN_SESSION_SECONDS)
                else:
                    response = RedirectResponse("https://ai.chobab.app/office", status_code=303)
                response.headers["Cache-Control"] = "no-store"
                response.headers["Referrer-Policy"] = "no-referrer"
                await response(scope, receive, send)
                return

            # Clean old credential-bearing links before they reach Hermes or
            # appear in browser history, even if the page script is unavailable.
            if path == "/ai-office" and any(
                key.lower() in {"email", "password"}
                for key, _ in parse_qsl(request.url.query, keep_blank_values=True)
            ):
                response = RedirectResponse(url=path, status_code=303, headers={"Cache-Control": "no-store"})
                await response(scope, receive, send)
                return

            # Native form fallback: if JavaScript fails to initialize, never
            # let the browser fall back to GET and put credentials in the URL.
            if (path, request.method) == ("/auth/office-login", "POST"):
                if not _origin_allowed(request.headers.get("origin"), host, request.method):
                    response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                    await response(scope, receive, send)
                    return
                fields = parse_qs((await request.body()).decode("utf-8", errors="replace"), keep_blank_values=True)
                email = fields.get("email", [""])[0].strip().lower()
                password = fields.get("password", [""])[0]
                success, result = service.login_with_password(email, password)
                if not success:
                    response = _login_response(request, str(result or "이메일 또는 비밀번호를 확인해주세요."))
                    await response(scope, receive, send)
                    return

                forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
                try:
                    visitor_scheme = json.loads(request.headers.get("cf-visitor", "{}")).get("scheme")
                except (TypeError, json.JSONDecodeError):
                    visitor_scheme = None
                secure_cookie = forwarded_proto == "https" or visitor_scheme == "https" or request.url.scheme == "https"
                token = JMT.make_jwt(
                    result["id"], result, ["name", "email", "id"],
                    lifetime_seconds=JMT.MAIN_SESSION_SECONDS,
                )
                response = RedirectResponse("/channels" if host == deskrpg_sso.HOST else "/office", status_code=303, headers={"Cache-Control": "no-store"})
                response.set_cookie(
                    key=SESSION_COOKIE, value=token, httponly=True,
                    secure=secure_cookie, samesite="none" if secure_cookie else "lax",
                    path="/", max_age=JMT.MAIN_SESSION_SECONDS,
                )
                await response(scope, receive, send)
                return

            # The gateway wraps CORSMiddleware, so browser preflight requests
            # must reach the app's CORS handler before session authentication.
            if request.method == "OPTIONS":
                if path == BROWSER_SYNC_PATH and request.headers.get("origin") == BROWSER_SYNC_EXTENSION_ORIGIN:
                    if request.headers.get("access-control-request-method", "").upper() not in {"GET", "PUT"}:
                        response = JSONResponse({"detail": "허용하지 않는 요청입니다."}, status_code=403)
                    else:
                        response = Response(status_code=204)
                        response.headers["Access-Control-Allow-Methods"] = "GET, PUT, OPTIONS"
                        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
                        response.headers["Access-Control-Max-Age"] = "600"
                    await _browser_sync_cors(response, request)(scope, receive, send)
                    return
                if not _origin_allowed(request.headers.get("origin"), host, request.method):
                    response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                    await response(scope, receive, send)
                    return
                await self.app(scope, receive, send)
                return

            # Reuse Sushi's existing password verifier and logout cookie handling.
            if (path, request.method) in {
                ("/auth/login", "POST"),
                ("/auth/logout", "POST"),
            }:
                if not _origin_allowed(request.headers.get("origin"), host, request.method):
                    response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                    await response(scope, receive, send)
                    return
                await self.app(scope, receive, send)
                return

            account_id = _account_id(request)
            if account_id is None:
                response = _unauthorized(request)
                if path == BROWSER_SYNC_PATH:
                    response = _browser_sync_cors(response, request)
                await response(scope, receive, send)
                return
            binding = system_for_account(account_id, host)
            if not binding:
                response = _binding_denied()
                if path == BROWSER_SYNC_PATH:
                    response = _browser_sync_cors(response, request)
                await response(scope, receive, send)
                return
            if binding["role"] not in {"owner", "viewer"}:
                response = _binding_denied()
                await response(scope, receive, send)
                return
            if host == AI_OFFICE_HOST and path in {"/", "/office"} and request.method in {"GET", "HEAD"}:
                response = RedirectResponse("/ai-office?view=office", status_code=303, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
                await response(scope, receive, send)
                return
            if path == BROWSER_SYNC_DOWNLOAD_PATH:
                if not _origin_allowed(request.headers.get("origin"), host, request.method):
                    response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                elif binding["role"] != "owner":
                    response = JSONResponse({"detail": "소유자 계정만 내려받을 수 있습니다."}, status_code=403)
                elif request.method != "GET":
                    response = JSONResponse({"detail": "지원하지 않는 요청입니다."}, status_code=405)
                elif not BROWSER_SYNC_ARCHIVE.is_file():
                    response = JSONResponse({"detail": "확장 파일을 찾을 수 없습니다."}, status_code=404)
                else:
                    response = FileResponse(BROWSER_SYNC_ARCHIVE, media_type="application/zip",
                                            filename="Ego-Space-Sync.zip")
                response.headers["Cache-Control"] = "no-store"
                await response(scope, receive, send)
                return
            if path == BROWSER_SYNC_PATH:
                if not _browser_sync_origin(request, host):
                    response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                elif binding["role"] != "owner":
                    response = JSONResponse({"detail": "소유자 계정만 동기화할 수 있습니다."}, status_code=403)
                else:
                    response = await handle_browser_space_sync(request, account_id)
                await _browser_sync_cors(response, request)(scope, receive, send)
                return
            if path.startswith("/api/plugins/hermes-workplace/files/") and binding["role"] != "owner":
                response = JSONResponse({"detail": "파일함은 소유자 계정만 사용할 수 있습니다."}, status_code=403)
                await response(scope, receive, send)
                return
            if not _origin_allowed(request.headers.get("origin"), host, request.method):
                response = JSONResponse({"detail": "요청 출처를 확인할 수 없습니다."}, status_code=403)
                await response(scope, receive, send)
                return
            if binding["role"] == "viewer" and request.method not in {"GET", "HEAD", "OPTIONS"}:
                response = JSONResponse({"detail": "읽기 전용 계정입니다."}, status_code=403)
                await response(scope, receive, send)
                return
            upstream = binding["upstream_url"]
            cookie = None
            if binding["system_id"] == deskrpg_sso.SYSTEM_ID:
                if path in {"/", "/auth"}:
                    response = RedirectResponse("/channels", status_code=303)
                    await response(scope, receive, send)
                    return
                if path.startswith(("/_internal", "/api/auth/register", "/api/auth/login", "/api/auth/logout")):
                    response = JSONResponse({"detail": "계정 로그인과 로그아웃은 Sushi 계정 메뉴를 이용해주세요."}, status_code=403)
                    await response(scope, receive, send)
                    return
                try:
                    cookie = deskrpg_sso.with_locale(await deskrpg_sso.upstream_cookie(account_id, binding["role"]), request)
                except Exception:
                    response = JSONResponse({"detail": "사무실 계정 연결을 완료하지 못했습니다. 잠시 후 다시 시도해주세요."}, status_code=503)
                    await response(scope, receive, send)
                    return
                if path.startswith("/socket.io"):
                    upstream = deskrpg_sso.SOCKET_UPSTREAM
            await _proxy_http(request, send, upstream, host, cookie)
            return

        websocket = WebSocket(scope, receive=receive, send=send)
        account_id = _account_id(websocket)
        if account_id is None:
            await websocket.close(code=4401, reason="Sushi login required")
            return
        binding = system_for_account(account_id, host)
        if not binding:
            await websocket.close(code=4403, reason="System access denied")
            return
        if not _origin_allowed(websocket.headers.get("origin"), host, "websocket"):
            await websocket.close(code=4403, reason="Invalid request origin")
            return
        if binding["role"] != "owner":
            await websocket.close(code=4403, reason="Read-only account")
            return
        upstream, cookie = binding["upstream_url"], None
        if binding["system_id"] == deskrpg_sso.SYSTEM_ID:
            if not websocket.url.path.startswith("/socket.io"):
                await websocket.close(code=4403, reason="Unsupported socket path")
                return
            upstream = deskrpg_sso.SOCKET_UPSTREAM
            cookie = deskrpg_sso.with_locale(await deskrpg_sso.upstream_cookie(account_id, binding["role"]), websocket)
        await _proxy_websocket(websocket, upstream, cookie)


def install_ai_office_gateway(app) -> None:
    ensure_access_schema()
    deskrpg_sso.ensure_schema()
    app.add_middleware(AIOfficeGatewayMiddleware)
