"""Security headers are present on every response.

These are HTTP-layer mitigations, not authorization. The tests pin
which headers are set and which are deliberately not set (HSTS in
development).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_all_responses_have_the_standard_headers() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    h = r.headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in h["Permissions-Policy"]
    assert h["Cross-Origin-Opener-Policy"] == "same-origin"
    assert h["Cross-Origin-Resource-Policy"] == "same-origin"


def test_api_routes_get_strict_csp() -> None:
    r = client.get("/health")
    csp = r.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "base-uri 'none'" in csp


def test_docs_routes_get_relaxed_csp() -> None:
    """Swagger UI needs inline scripts and a CDN. The relaxed CSP is
    scoped to /docs, /redoc, and /openapi.json only."""
    r = client.get("/docs")
    csp = r.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in csp
    assert "'unsafe-inline'" in csp


def test_hsts_absent_in_development() -> None:
    """HSTS on localhost pins the scheme for a year. Not acceptable in
    a dev environment."""
    r = client.get("/health")
    assert "Strict-Transport-Security" not in r.headers


def test_headers_also_present_on_error_responses() -> None:
    """404 responses go through the same middleware; they must carry
    the headers too."""
    r = client.get("/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in r.headers
