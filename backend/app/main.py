"""AeroGrid-XAI FastAPI application entry point.

Exposes the health probe, the Prometheus metrics endpoint, and the
routers for the scientific modules. The Tier 1 decision router lives in
app.control.api; further routers are added as the platform grows.
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.control.api import router as control_router
from app.digital_twin.api import router as digital_twin_router
from app.discovery.api import router as discovery_router
from app.mission.api import router as mission_router
from app.physics.api import router as physics_router
from app.saas.admin_routes import router as saas_admin_router
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
app.include_router(physics_router)
app.include_router(digital_twin_router)
app.include_router(discovery_router)
app.include_router(mission_router)
app.include_router(telemetry_router)
app.include_router(tradespace_router)
app.include_router(saas_router)
app.include_router(saas_billing_router)
app.include_router(saas_admin_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
