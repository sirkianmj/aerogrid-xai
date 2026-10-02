"""AeroGrid-XAI FastAPI application entry point.

Phase 0: minimal health endpoint. The scientific modules (physics,
formal verification, XAI) are added in later phases.
"""

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="AeroGrid-XAI API",
    version="0.1.0",
    description="Physics-aware, formally verified platform for space-to-air wireless energy transfer.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe. Returns 'healthy' when the process is running."""
    return {"status": "healthy"}


Instrumentator().instrument(app).expose(app, endpoint="/metrics")
