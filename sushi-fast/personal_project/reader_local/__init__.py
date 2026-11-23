"""Opt-in loopback-only translation companion prototype.

The module contains no provider implementation or credential handling. A launcher
must inject a provider and expose ``pairing_code`` only through a trusted local
channel. Request/response text and pairing material are never persisted or logged.
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Protocol
from urllib.parse import urlsplit

LOOPBACK_HOST = "127.0.0.1"
PAIRING_TTL_SECONDS = 300
MAX_BODY_BYTES = 256 * 1024
MAX_SEGMENTS = 50
MAX_SEGMENT_CHARS = 5_000
MAX_TOTAL_CHARS = 20_000
MAX_ID_CHARS = 128
MAX_LANGUAGE_CHARS = 64
_ID_PATTERN = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z", re.ASCII)


class TranslationProvider(Protocol):
    """Narrow injected interface; no provider or network client is included."""

    def translate(self, segments: list[dict[str, str]], target_language: str) -> list[dict[str, str]]: ...


@dataclass(frozen=True)
class Response:
    status: int
    body: dict[str, object]
    headers: dict[str, str]


class Companion:
    """In-memory pairing guard and translation-only request dispatcher."""

    def __init__(
        self,
        provider: TranslationProvider,
        *,
        browser_origin: str,
        pairing_code: str | None = None,
        clock: Callable[[], float] = time.monotonic,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        parsed = urlsplit(browser_origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("browser_origin must be an exact HTTP(S) origin")
        self._provider = provider
        self._browser_origin = f"{parsed.scheme}://{parsed.netloc}"
        self._pairing_code = pairing_code or secrets.token_urlsafe(24)
        self._clock = clock
        self._pairing_expires_at = clock() + PAIRING_TTL_SECONDS
        self._token_factory = token_factory
        self._lock = threading.Lock()
        self._code_consumed = False
        self._csrf_value: str | None = None
        self._csrf_expires_at = 0.0

    @property
    def pairing_code(self) -> str:
        """Ephemeral code; a trusted local launcher must not log or publish it."""
        return self._pairing_code

    def handle(
        self,
        method: str,
        path: str,
        *,
        origin: str | None,
        host: str | None,
        headers: dict[str, str],
        body: bytes,
    ) -> Response:
        if not self._is_loopback_host(host):
            return self._error(403, "host_not_allowed")
        if path == "/health" and method == "GET":
            return Response(200, {"status": "ok", "scope": "loopback"}, self._base_headers())
        if origin != self._browser_origin:
            return self._error(403, "origin_not_allowed")
        if method == "OPTIONS":
            return Response(204, {}, {
                **self._base_headers(),
                "Access-Control-Allow-Origin": self._browser_origin,
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, X-Reader-Pairing",
                "Access-Control-Max-Age": "60",
                "Vary": "Origin",
            })
        if method not in {"POST"}:
            return self._error(405, "method_not_allowed", cors=True)
        if len(body) > MAX_BODY_BYTES:
            return self._error(413, "request_too_large", cors=True)
        normalized_headers = {key.lower(): value for key, value in headers.items()}
        if path == "/pair":
            return self._pair(body)
        if path == "/translate":
            pairing_error = self._pairing_error(normalized_headers.get("x-reader-pairing"))
            if pairing_error is not None:
                return self._error(403, pairing_error, cors=True)
            return self._translate(body)
        return self._error(404, "not_found", cors=True)

    @staticmethod
    def _is_loopback_host(host: str | None) -> bool:
        if not host or "@" in host or "/" in host or "\\" in host:
            return False
        try:
            parsed = urlsplit("//" + host)
            return parsed.hostname in {"127.0.0.1", "localhost"} and parsed.username is None
        except ValueError:
            return False

    def _pair(self, body: bytes) -> Response:
        payload = self._parse_json(body)
        if not isinstance(payload, dict) or set(payload) != {"pairing_code"}:
            return self._error(400, "invalid_pairing_request", cors=True)
        supplied = payload.get("pairing_code")
        if not isinstance(supplied, str) or len(supplied) > 128:
            return self._error(403, "pairing_unavailable", cors=True)
        with self._lock:
            if (
                self._code_consumed
                or self._clock() >= self._pairing_expires_at
                or not hmac.compare_digest(supplied, self._pairing_code)
            ):
                return self._error(403, "pairing_unavailable", cors=True)
            self._code_consumed = True
            self._csrf_value = self._token_factory()
            self._csrf_expires_at = self._clock() + PAIRING_TTL_SECONDS
            csrf_value = self._csrf_value
        return Response(200, {"pairing": csrf_value, "expires_in": PAIRING_TTL_SECONDS}, {
            **self._base_headers(),
            "Access-Control-Allow-Origin": self._browser_origin,
            "Vary": "Origin",
        })

    def _pairing_error(self, supplied: str | None) -> str | None:
        if not isinstance(supplied, str):
            return "pairing_required"
        with self._lock:
            if self._csrf_value is None:
                return "pairing_required"
            if self._clock() >= self._csrf_expires_at:
                return "pairing_expired"
            if not hmac.compare_digest(supplied, self._csrf_value):
                return "pairing_required"
            return None

    def _translate(self, body: bytes) -> Response:
        payload = self._parse_json(body)
        if payload is None:
            return self._error(400, "invalid_json", cors=True)
        validated = self._validate_payload(payload)
        if isinstance(validated, str):
            return self._error(400, validated, cors=True)
        segments, target_language = validated
        try:
            result = self._provider.translate(segments, target_language)
            translations = self._validate_result(result, segments)
        except Exception:
            # Never return exception text: providers may include source excerpts.
            return self._error(502, "translation_failed", cors=True)
        return Response(200, {"translations": translations}, {
            **self._base_headers(),
            "Access-Control-Allow-Origin": self._browser_origin,
            "Vary": "Origin",
        })

    @staticmethod
    def _parse_json(body: bytes) -> object | None:
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def _validate_payload(payload: object) -> tuple[list[dict[str, str]], str] | str:
        if not isinstance(payload, dict) or set(payload) - {"segments", "target_language"}:
            return "invalid_payload"
        segments = payload.get("segments")
        if not isinstance(segments, list) or not 1 <= len(segments) <= MAX_SEGMENTS:
            return "invalid_segments"
        output: list[dict[str, str]] = []
        seen: set[str] = set()
        total = 0
        for segment in segments:
            if not isinstance(segment, dict) or set(segment) != {"id", "text"}:
                return "invalid_segment"
            segment_id, text = segment["id"], segment["text"]
            if not isinstance(segment_id, str) or len(segment_id) > MAX_ID_CHARS or not _ID_PATTERN.fullmatch(segment_id):
                return "invalid_segment_id"
            if segment_id in seen:
                return "duplicate_segment_id"
            if not isinstance(text, str) or not text.strip():
                return "invalid_segment_text"
            if len(text) > MAX_SEGMENT_CHARS:
                return "segment_too_large"
            total += len(text)
            if total > MAX_TOTAL_CHARS:
                return "translation_text_too_large"
            seen.add(segment_id)
            output.append({"id": segment_id, "text": text})
        language = payload.get("target_language", "English")
        if not isinstance(language, str) or not language.strip() or len(language) > MAX_LANGUAGE_CHARS:
            return "invalid_target_language"
        return output, language.strip()

    @staticmethod
    def _validate_result(result: object, segments: list[dict[str, str]]) -> list[dict[str, str]]:
        if not isinstance(result, list) or len(result) != len(segments):
            raise ValueError("invalid provider response")
        expected = {segment["id"] for segment in segments}
        by_id: dict[str, str] = {}
        for item in result:
            if not isinstance(item, dict) or set(item) != {"id", "text"}:
                raise ValueError("invalid provider response")
            segment_id, text = item["id"], item["text"]
            if (
                not isinstance(segment_id, str)
                or segment_id not in expected
                or segment_id in by_id
                or not isinstance(text, str)
                or not text.strip()
                or len(text) > MAX_SEGMENT_CHARS
            ):
                raise ValueError("invalid provider response")
            by_id[segment_id] = text
        if set(by_id) != expected:
            raise ValueError("invalid provider response")
        return [{"id": segment["id"], "text": by_id[segment["id"]]} for segment in segments]

    def _error(self, status: int, code: str, *, cors: bool = False) -> Response:
        headers = self._base_headers()
        if cors:
            headers.update({"Access-Control-Allow-Origin": self._browser_origin, "Vary": "Origin"})
        return Response(status, {"error": code}, headers)

    @staticmethod
    def _base_headers() -> dict[str, str]:
        return {"Cache-Control": "no-store", "Pragma": "no-cache", "Content-Type": "application/json"}


def make_server(companion: Companion, port: int = 0) -> ThreadingHTTPServer:
    """Bind only to IPv4 loopback; caller controls lifecycle and never supplies host."""

    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self) -> None:
            raw_path = urlsplit(self.path).path
            length_header = self.headers.get("Content-Length")
            if self.headers.get("Transfer-Encoding"):
                response = companion._error(400, "invalid_request")
                body = b""
            else:
                try:
                    length = int(length_header or "0")
                except ValueError:
                    length = -1
                if length < 0:
                    response = companion._error(400, "invalid_request")
                    body = b""
                elif length > MAX_BODY_BYTES:
                    response = companion._error(413, "request_too_large")
                    body = b""
                else:
                    body = self.rfile.read(length) if length else b""
                    response = companion.handle(
                        self.command,
                        raw_path,
                        origin=self.headers.get("Origin"),
                        host=self.headers.get("Host"),
                        headers=dict(self.headers.items()),
                        body=body,
                    )
            response_bytes = json.dumps(response.body, separators=(",", ":")).encode("utf-8")
            self.send_response(response.status)
            for name, value in response.headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(response_bytes)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response_bytes)

        def do_GET(self) -> None:
            self._dispatch()

        def do_POST(self) -> None:
            self._dispatch()

        def do_OPTIONS(self) -> None:
            self._dispatch()

        def log_message(self, _format: str, *args: object) -> None:
            # BaseHTTPRequestHandler's default request log can contain URL values.
            return

    server = ThreadingHTTPServer((LOOPBACK_HOST, port), Handler)
    server.daemon_threads = True
    return server
