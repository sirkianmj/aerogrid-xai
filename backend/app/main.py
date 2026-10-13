"""AeroGrid-XAI FastAPI application entry point.

Exposes the health probe, the Prometheus metrics endpoint, and the
routers for the scientific modules. The Tier 1 decision router lives in
app.control.api; further routers are added as the platform grows.
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.control.api import router as control_router
from app.physics.api import router as physics_router

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

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
