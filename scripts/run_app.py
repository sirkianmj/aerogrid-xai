"""Launch AeroGrid-XAI in a browser from the terminal.

Serves the built frontend and the API from one FastAPI process, then
opens the default browser at http://localhost:PORT/. Ctrl-C stops.

This is the terminal equivalent of the packaged .app. No native
window; the browser is the UI.

Usage:
    python3 scripts/run_app.py
    AEROGRID_PORT=9000 python3 scripts/run_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

_FRONTEND_CSP = (
    "default-src 'self'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws://localhost:* ws://127.0.0.1:* "
    "http://localhost:* http://127.0.0.1:*; "
    "worker-src 'self' blob:; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)
_FRONTEND_EXACT = {"/"}
_FRONTEND_PREFIXES = ("/assets/", "/favicon", "/index.html")


def _is_frontend(path: str) -> bool:
    return path in _FRONTEND_EXACT or path.startswith(_FRONTEND_PREFIXES)


class _DesktopCSPMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not _is_frontend(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def wrap(message):
            if message.get("type") == "http.response.start":
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() != b"content-security-policy"
                ]
                headers.append((b"content-security-policy", _FRONTEND_CSP.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, wrap)


class _APIPrefixRewriteMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                new_scope = dict(scope)
                new_scope["path"] = path[4:] or "/"
                raw = scope.get("raw_path", b"")
                if raw.startswith(b"/api"):
                    new_scope["raw_path"] = raw[4:] or b"/"
                scope = new_scope
        await self.app(scope, receive, send)


app.add_middleware(_DesktopCSPMiddleware)
app.add_middleware(_APIPrefixRewriteMiddleware)

_frontend_dir = REPO / "frontend" / "dist"
if _frontend_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )


def main() -> None:
    import uvicorn

    port = int(os.environ.get("AEROGRID_PORT", "8000"))
    print(f"AeroGrid-XAI listening on http://localhost:{port}/", flush=True)
    print("Press Ctrl-C to stop.", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
