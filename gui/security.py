"""
PHARMAKON local-server guard.

The Studio server listens on 127.0.0.1 only, but a localhost port is still reachable from any
web page open in the user's browser (cross-site requests, DNS rebinding). This module provides:

  * LocalGuardMiddleware - pure-ASGI middleware that
      - accepts only requests whose Host is the local server (blocks DNS rebinding),
      - rejects foreign Origin and cross-site Sec-Fetch-Site requests (blocks CSRF / cross-site reads),
      - requires a per-run secret token for every /api/* route (cookie for the UI, header for tools).
    No CORS headers are ever emitted: the UI is served by the same origin and needs none.
  * path helpers that restrict which files the API may read or open.

Standard library only, so it is easy to test without FastAPI.
"""
import hmac
import json
import os
import secrets
import urllib.parse
from http.cookies import SimpleCookie
from pathlib import Path

COOKIE_NAME = "ph_session"
TOKEN_HEADER = "x-pharmakon-token"
PUBLIC_API_PATHS = frozenset({"/api/ping"})

AUDIO_EXTS = frozenset({".wav", ".flac", ".mp3", ".ogg", ".aif", ".aiff"})
REPORT_SUFFIXES = ("MASTERING_REPORT.html", "interactive_map.html")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_file_path() -> Path:
    return Path.home() / ".pharmakon" / "session_token"


def write_token_file(token: str, path: Path = None) -> Path:
    """Store the run token where only the current user can read it (used by launcher --stop)."""
    p = Path(path) if path else token_file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token, encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return p


def read_token_file(path: Path = None) -> str:
    try:
        return (Path(path) if path else token_file_path()).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class LocalGuardMiddleware:
    def __init__(self, app, token: str, port: int = 7860, extra_hosts=()):
        self.app = app
        self.token = token
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
        hosts.update(h.lower() for h in extra_hosts)
        self.hosts = hosts
        self.origins = {f"http://{h}" for h in hosts}

    @staticmethod
    def _headers(scope):
        return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

    def _token_ok(self, headers) -> bool:
        supplied = headers.get(TOKEN_HEADER, "")
        if not supplied:
            jar = SimpleCookie()
            try:
                jar.load(headers.get("cookie", ""))
            except Exception:
                jar = SimpleCookie()
            morsel = jar.get(COOKIE_NAME)
            supplied = morsel.value if morsel else ""
        return bool(supplied) and hmac.compare_digest(supplied.encode(), self.token.encode())

    async def _deny(self, scope, receive, send, status: int, reason: str):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"detail": reason}).encode()
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode()),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = self._headers(scope)
        if headers.get("host", "").lower() not in self.hosts:
            await self._deny(scope, receive, send, 403, "Forbidden host")
            return
        origin = headers.get("origin")
        if origin is not None and origin.lower() not in self.origins:
            await self._deny(scope, receive, send, 403, "Forbidden origin")
            return
        if headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
            await self._deny(scope, receive, send, 403, "Cross-site request blocked")
            return

        path = scope.get("path", "")
        if path.startswith("/api/") and path not in PUBLIC_API_PATHS and not self._token_ok(headers):
            await self._deny(scope, receive, send, 401, "Missing or invalid session token")
            return

        if scope["type"] == "http" and path == "/":
            cookie = f"{COOKIE_NAME}={self.token}; HttpOnly; SameSite=Strict; Path=/".encode()

            async def send_with_cookie(message):
                if message["type"] == "http.response.start":
                    message = dict(message)
                    message["headers"] = list(message.get("headers", [])) + [(b"set-cookie", cookie)]
                await send(message)

            await self.app(scope, receive, send_with_cookie)
            return

        await self.app(scope, receive, send)


# ---------------------------------------------------------------- path helpers

def clean_user_path(raw: str) -> str:
    p = urllib.parse.unquote(raw or "").strip().strip('"').strip("'")
    if p.startswith("file:///"):
        p = p[8:]
    return p


def is_audio_path(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTS


def is_report_path(path: str) -> bool:
    return os.path.basename(path).endswith(REPORT_SUFFIXES)


def is_inside(path, root) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False
