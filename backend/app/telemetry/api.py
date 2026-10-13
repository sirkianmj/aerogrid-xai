"""WebSocket endpoint for live telemetry.

Pushes one snapshot per interval over a WebSocket. Each snapshot carries
the orbital state of one catalog satellite and the current Digital Twin
thermal state at a fixed demo condition set.

Endpoint
--------

    WS /telemetry/stream?satellite=<key>&interval_seconds=<seconds>

The first snapshot is sent immediately on connect; subsequent snapshots
follow every ``interval_seconds``. Both query parameters have documented
defaults and bounds. A client that requests an unknown satellite or an
out-of-range interval is closed with a specific WebSocket close code
before any snapshot is sent.

Time anchor
-----------

SGP4/SDP4 propagation is only valid for weeks around a TLE epoch. The
packaged catalog TLEs have fixed epochs, so using wall-clock time would
produce physically meaningless positions.

To keep the demo honest, the stream propagates each satellite at

    TLE epoch + (wall_clock_now - connection_start)

so the satellite moves in real time from a valid near-epoch position.
The snapshot's ``time_utc`` field is the propagated time, not the wall
clock, so the frontend displays what was actually computed. A
production deployment that ingests current TLEs would anchor on wall
clock directly.

Epistemic category
------------------

Every value in a snapshot is a model output, not a measurement. The
snapshot carries epistemic_tag = "simulation_result" per Section 21.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.physics.catalog import get_satellite, list_satellite_keys
from app.physics.orbital import classify_orbit
from app.physics.thermal import default_model

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

DEFAULT_INTERVAL_SECONDS = 2.0
"""Default push interval. Chosen so a panel shows movement without
overwhelming the client with hundreds of updates per second."""

MIN_INTERVAL_SECONDS = 0.1
"""Below this the server would push faster than SGP4 propagation plus
JSON serialization can run, and would saturate a single uvicorn worker."""

MAX_INTERVAL_SECONDS = 60.0
"""Above this the connection is effectively idle; a client that wants
slower updates should poll the REST endpoints instead."""

# WebSocket close codes used by this endpoint. 4000-4999 are reserved
# for application use by RFC 6455.
CLOSE_BAD_SATELLITE = 4404
CLOSE_BAD_INTERVAL = 4400

# Thermal state is computed once per connection at the fixed demo
# conditions. Recomputing the runaway boundary on every tick would spend
# tens of milliseconds per snapshot on a bisection that cannot change
# between ticks. If the demo conditions become caller-configurable, this
# moves into the loop.
_DEMO_INCIDENT_W = 20.0
_DEMO_AIRFLOW_M_PER_S = 5.0
_DEMO_AMBIENT_K = 298.15


class ThermalSnapshotModel(BaseModel):
    t_plc_k: float
    t_plc_c: float
    t_te_k: float
    t_te_c: float
    thermal_runaway_power_w: float
    safety_margin_w: float


class OrbitalSnapshotModel(BaseModel):
    lat_deg: float
    lon_deg: float
    alt_m: float
    speed_km_s: float
    in_eclipse: bool


class SatelliteSnapshotModel(BaseModel):
    key: str
    name: str
    orbit_class: str


class TelemetrySnapshot(BaseModel):
    """One telemetry push. Field names match the frontend's expectations."""

    epistemic_tag: str = "simulation_result"
    sequence: int
    time_utc: str
    satellite: SatelliteSnapshotModel
    orbital: OrbitalSnapshotModel
    thermal: ThermalSnapshotModel


def _compute_thermal_snapshot() -> ThermalSnapshotModel:
    """Compute the fixed demo thermal state. Raises RuntimeError on a
    broken model."""
    model = default_model()
    runaway_w = model.thermal_runaway_boundary(
        v_m_per_s=_DEMO_AIRFLOW_M_PER_S,
        t_amb_k=_DEMO_AMBIENT_K,
    )
    ss = model.steady_state(
        p_incident_w=_DEMO_INCIDENT_W,
        v_m_per_s=_DEMO_AIRFLOW_M_PER_S,
        t_amb_k=_DEMO_AMBIENT_K,
    )
    if ss is None:
        raise RuntimeError("no steady state at the demo conditions")
    t_plc, t_te = ss
    return ThermalSnapshotModel(
        t_plc_k=t_plc,
        t_plc_c=t_plc - 273.15,
        t_te_k=t_te,
        t_te_c=t_te - 273.15,
        thermal_runaway_power_w=runaway_w,
        safety_margin_w=runaway_w - _DEMO_INCIDENT_W,
    )


def _build_snapshot(
    sequence: int,
    satellite_key: str,
    sample_time: datetime,
    thermal: ThermalSnapshotModel,
) -> dict[str, Any]:
    """Build one snapshot dict ready for JSON serialization."""
    sat = get_satellite(satellite_key)
    state = sat.at_utc(sample_time)
    in_eclipse = sat.is_in_eclipse_utc(sample_time)
    return {
        "epistemic_tag": "simulation_result",
        "sequence": sequence,
        "time_utc": state.time_utc.isoformat(),
        "satellite": {
            "key": satellite_key,
            "name": sat.name,
            "orbit_class": classify_orbit(state.alt_km),
        },
        "orbital": {
            "lat_deg": state.lat_deg,
            "lon_deg": state.lon_deg,
            "alt_m": state.alt_m,
            "speed_km_s": state.speed_km_s,
            "in_eclipse": in_eclipse,
        },
        "thermal": thermal.model_dump(),
    }


@router.websocket("/stream")
async def telemetry_stream(
    websocket: WebSocket,
    satellite: str = "vanguard_r3",
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
) -> None:
    """Push telemetry snapshots at the requested interval.

    Query parameters:
        satellite:        catalog key (default vanguard_r3)
        interval_seconds: push interval in seconds, in
                          [MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS]

    Close codes:
        4404 unknown satellite
        4400 out-of-range interval, or a broken thermal model
    """
    if satellite not in list_satellite_keys():
        await websocket.close(code=CLOSE_BAD_SATELLITE)
        return
    if not (MIN_INTERVAL_SECONDS <= interval_seconds <= MAX_INTERVAL_SECONDS):
        await websocket.close(code=CLOSE_BAD_INTERVAL)
        return

    try:
        thermal = _compute_thermal_snapshot()
    except RuntimeError:
        await websocket.close(code=CLOSE_BAD_INTERVAL)
        return

    await websocket.accept()

    sat = get_satellite(satellite)
    tle_epoch = sat.epoch_utc
    connection_start = datetime.now(UTC)

    sequence = 0
    try:
        while True:
            elapsed = datetime.now(UTC) - connection_start
            sample_time = tle_epoch + elapsed
            snapshot = _build_snapshot(sequence, satellite, sample_time, thermal)
            await websocket.send_json(snapshot)
            sequence += 1
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        return
    except RuntimeError:
        # The client closed between send_json and sleep; nothing to do.
        return
