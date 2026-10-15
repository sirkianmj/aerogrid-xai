"""Adds defense-in-depth security headers to every response.

These are HTTP-layer mitigations, not authorization. They reduce the
impact of a cross-site scripting or clickjacking flaw if one is ever
introduced; they do not prevent either. The real defenses are the
Content-Type discipline of FastAPI (JSON responses only), the absence
of session cookies (we use Authorization: Bearer), and the CSP applied
below.

The CSP is split: /docs and /redoc serve FastAPI's auto-generated
Swagger UI, which requires inline styles/scripts and resources from
cdn.jsdelivr.net; every other response is JSON and gets a policy of
"default-src 'none'".

HSTS is only added outside development. HSTS on localhost is a
footgun: the browser pins the scheme for a year and there is no HTTPS
to fall back to.
"""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

_DOCS_CSP = (
    "default-src 'self' https://cdn.jsdelivr.net; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'"
)

_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects the security header set on every outgoing response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response: Response = await call_next(request)
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
        )
        headers["Cross-Origin-Opener-Policy"] = "same-origin"
        headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path in _DOCS_PATHS:
            headers["Content-Security-Policy"] = _DOCS_CSP
        else:
            headers["Content-Security-Policy"] = _API_CSP
        env = os.environ.get("AEROGRID_ENV", "development")
        if env != "development":
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
