"""PyInstaller entrypoint for AeroGrid-XAI desktop app.

Opens a native window (Cocoa/WebKit on macOS, WebView2 on Windows)
pointing at an in-process FastAPI server. No external browser, no
terminal window visible to the user.

The server binds to an OS-chosen free port so there is no conflict
with any dev server on 8000. Closing the window exits the process and
the daemon uvicorn thread dies with it.

On macOS, webview.start() must run on the main thread, so the uvicorn
server runs in a background daemon thread with signal handlers
disabled.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent

sys.path.insert(0, str(ROOT / "backend"))

from fastapi.staticfiles import StaticFiles  # noqa: E402

from app.main import app  # noqa: E402

# ---------------------------------------------------------------------------
# The shared SecurityHeadersMiddleware sets Content-Security-Policy:
# default-src 'none'. That is correct for API responses but blocks every
# script, style, image, and WebSocket needed by the React frontend.
# This desktop-only middleware wraps the shared stack and replaces the
# CSP header for the served frontend paths. API responses keep the
# strict default.
# ---------------------------------------------------------------------------

_DESKTOP_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "connect-src 'self' ws://localhost:* ws://127.0.0.1:* "
    "http://localhost:* http://127.0.0.1:*; "
    "worker-src 'self' blob:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

# Paths that must use the desktop CSP (the frontend) rather than the
# strict default (the API). Anything not under /assets and not the root
# HTML uses the shared policy.
_FRONTEND_PREFIXES = ("/assets/", "/favicon", "/index.html")
_FRONTEND_EXACT = {"/"}


def _is_frontend_path(path: str) -> bool:
    return path in _FRONTEND_EXACT or path.startswith(_FRONTEND_PREFIXES)


class _DesktopCSPMiddleware:
    """Replace default-src 'none' with a permissive-for-self CSP on the
    served frontend. API responses keep the middleware's default.

    Starlette constructs middlewares as ``cls(app=app)``, so the first
    parameter must be named ``app``.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not _is_frontend_path(scope.get("path", "")):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message.get("type") == "http.response.start":
                headers = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() != b"content-security-policy"
                ]
                headers.append((b"content-security-policy", _DESKTOP_CSP.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


# Must be added AFTER app.main's middleware additions so it wraps them
# (last added is outermost in Starlette).
app.add_middleware(_DesktopCSPMiddleware)


# ---------------------------------------------------------------------------
# API prefix rewrite.
#
# The frontend always calls /api/<endpoint> (see missionApi.ts, clearDApi.ts,
# authApi.ts). In development the Vite proxy strips the /api prefix before
# forwarding to the backend, so the backend only ever sees /<endpoint>.
# The frozen desktop app has no Vite proxy; the browser hits the backend
# directly and /api/mission/state would 404 because the backend serves
# /mission/state.
#
# This middleware applies the same rewrite the Vite proxy did.
# ---------------------------------------------------------------------------

class _APIPrefixRewriteMiddleware:
    """Strip a leading '/api' from the request path before routing.

    Mirrors frontend/vite.config.ts's proxy rewrite rule
    ``(path) => path.replace(/^\/api/, '')``.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                new_scope = dict(scope)
                new_scope["path"] = path[4:] or "/"
                # Starlette also stores raw_path; keep the two in sync.
                raw = scope.get("raw_path", b"")
                if raw.startswith(b"/api"):
                    new_scope["raw_path"] = raw[4:] or b"/"
                scope = new_scope
        await self.app(scope, receive, send)


app.add_middleware(_APIPrefixRewriteMiddleware)

_frontend = ROOT / "frontend_dist"
if _frontend.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve(port: int) -> None:
    import uvicorn

    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", access_log=False
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    server.run()


def _wait_ready(port: int, timeout_s: float = 30.0) -> bool:
    url = f"http://localhost:{port}/health"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    return False


def main() -> None:
    import webview

    env_port = int(os.environ.get("AEROGRID_PORT", "0"))
    port = env_port if env_port > 0 else _free_port()

    t = threading.Thread(target=_serve, args=(port,), daemon=True)
    t.start()

    if not _wait_ready(port):
        print("AeroGrid-XAI: server failed to start", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{port}/"
    webview.create_window(
        "AeroGrid-XAI",
        url,
        width=1440,
        height=900,
        min_size=(800, 600),
        text_select=True,
    )
    webview.start()


if __name__ == "__main__":
    main()
