"""AeroGrid-XAI FastAPI application entry point.

Exposes the health probe, the Prometheus metrics endpoint, and the
routers for the scientific modules. The Tier 1 decision router lives in
app.control.api; further routers are added as the platform grows.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.control.api import router as control_router
from app.design.api import router as design_router
from app.digital_twin.api import router as digital_twin_router
from app.discovery.api import router as discovery_router
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.mission.api import router as mission_router
from app.physics.api import router as physics_router
from app.saas.admin_routes import router as saas_admin_router
from app.saas.auth_routes import router as auth_router
from app.saas.billing_routes import router as saas_billing_router
from app.saas.routes import router as saas_router
from app.telemetry.api import router as telemetry_router
from app.tradespace.api import router as tradespace_router

app = FastAPI(
    title="AeroGrid-XAI API",
    version="0.1.0",
    description="Physics-aware, formally verified wireless energy platform.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Returns 'healthy' when the process is running."""
    return {"status": "healthy"}


app.include_router(control_router)
app.include_router(design_router)
app.include_router(physics_router)
app.include_router(digital_twin_router)
app.include_router(discovery_router)
app.include_router(mission_router)
app.include_router(telemetry_router)
app.include_router(tradespace_router)
app.include_router(saas_router)
app.include_router(auth_router)
app.include_router(saas_billing_router)
app.include_router(saas_admin_router)


# --- CORS -----------------------------------------------------------
# Dev default: the Vite dev server origin. In any non-development
# environment the operator must set AEROGRID_ALLOWED_ORIGINS to a
# comma-separated list; the process refuses to start otherwise. This is
# deliberate: shipping a wildcard origin is a common production
# mistake, and failing at startup is cheaper than discovering it in an
# incident.
def _allowed_origins() -> list[str]:
    raw = os.environ.get("AEROGRID_ALLOWED_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    env = os.environ.get("AEROGRID_ENV", "development")
    if env == "development":
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    raise RuntimeError(
        "AEROGRID_ALLOWED_ORIGINS must be set when AEROGRID_ENV is not 'development'"
    )


# --- Middleware order ------------------------------------------------
# In Starlette, the last middleware added is the outermost. The order
# below produces the stack (outer -> inner):
#
#     SecurityHeaders -> CORS -> RateLimit -> routes
#
# Consequences:
#   * Every response, including a 429 from the rate limiter or a CORS
#     preflight error, carries the security headers.
#   * CORS preflight is handled before the rate limiter counts it, so
#     an OPTIONS request does not consume a rate-limit slot.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    # We authenticate with a Bearer token in the Authorization header,
    # not a cookie. allow_credentials=False tells the browser not to
    # send cookies on cross-origin requests, which removes an entire
    # class of CSRF risk.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityHeadersMiddleware)

# The instrumentator must not count its own scrape endpoint, the
# health probe, or the OpenAPI schema. Without exclusions, every
# Prometheus scrape adds a sample to http_requests_total with
# handler="/metrics", and every health check adds one for "/health".
# Those series grow without bound over the process lifetime and would
# dominate the dashboard.
Instrumentator(
    excluded_handlers=["/metrics", "/health", "/openapi.json", "/docs", "/redoc"],
).instrument(app).expose(app, endpoint="/metrics")
