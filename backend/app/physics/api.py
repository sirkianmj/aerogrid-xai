"""HTTP endpoints for orbital mechanics.

The physics live in app.physics.orbital. This module exposes three read
endpoints so the frontend Globe can render satellite tracks:

  GET /orbital/satellites     list the available demo satellites
  GET /orbital/track          one satellite's geodetic track over a range
  GET /orbital/visibility     visibility windows from a ground site

All positions are computed at request time by SGP4/SDP4 propagation of
the packaged TLE. Nothing is cached across requests; the same query
returns the same answer because the TLE and the propagation are
deterministic.

The number of samples in a track response is capped at
``MAX_TRACK_POINTS``; a query that would exceed the cap is rejected with
400 rather than silently truncated.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.physics.catalog import get_satellite, list_satellite_keys
from app.physics.orbital import (
    GroundNode,
    classify_orbit,
    visibility_windows,
)

router = APIRouter(prefix="/orbital", tags=["orbital"])

MAX_TRACK_POINTS = 5_000
"""Upper bound on the number of points returned by /orbital/track.

A track query is (t_end - t_start) / step_seconds points. The cap
prevents a client from accidentally requesting millions of samples. At
5,000 points the JSON payload is on the order of a few hundred
kilobytes, which is appropriate for a single-page render.
"""


class SatelliteInfo(BaseModel):
    key: str
    name: str
    epoch_utc: datetime
    mean_motion_rev_per_day: float
    period_seconds: float
    orbit_class: str = Field(
        ...,
        description="LEO, MEO, GEO, or HEO, computed from the altitude at TLE epoch.",
    )


class SatelliteListResponse(BaseModel):
    satellites: list[SatelliteInfo]


class TrackPoint(BaseModel):
    time_utc: datetime
    lat_deg: float
    lon_deg: float
    alt_m: float
    speed_km_s: float
    in_eclipse: bool


class TrackResponse(BaseModel):
    key: str
    name: str
    t_start: datetime
    t_end: datetime
    step_seconds: float
    n_points: int
    points: list[TrackPoint]


class GroundSite(BaseModel):
    name: str
    lat_deg: float
    lon_deg: float
    alt_m: float


class VisibilityWindowModel(BaseModel):
    start_utc: datetime
    end_utc: datetime
    duration_seconds: float
    peak_elevation_deg: float
    peak_time_utc: datetime


class VisibilityResponse(BaseModel):
    key: str
    name: str
    ground: GroundSite
    min_elevation_deg: float
    t_start: datetime
    t_end: datetime
    n_windows: int
    windows: list[VisibilityWindowModel]


def _ensure_utc(dt: datetime) -> datetime:
    """Return dt as a timezone-aware UTC datetime."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


@router.get("/satellites", response_model=SatelliteListResponse)
async def list_satellites() -> SatelliteListResponse:
    """Return one entry per satellite in the packaged catalog."""
    infos: list[SatelliteInfo] = []
    for key in list_satellite_keys():
        sat = get_satellite(key)
        state_at_epoch = sat.at_utc(sat.epoch_utc)
        infos.append(
            SatelliteInfo(
                key=key,
                name=sat.name,
                epoch_utc=sat.epoch_utc,
                mean_motion_rev_per_day=sat.mean_motion_rev_per_day,
                period_seconds=sat.period_seconds,
                orbit_class=classify_orbit(state_at_epoch.alt_km),
            )
        )
    return SatelliteListResponse(satellites=infos)


@router.get("/track", response_model=TrackResponse)
async def track(
    satellite: str = Query(..., description="Catalog key, e.g. 'iss'."),
    t_start: datetime = Query(..., description="ISO 8601 start time."),
    t_end: datetime = Query(..., description="ISO 8601 end time."),
    step_seconds: float = Query(60.0, gt=0.0, description="Sampling interval in seconds."),
) -> TrackResponse:
    """Return the geodetic track of one satellite over a time range.

    Raises:
        HTTPException 404 if the satellite key is not in the catalog.
        HTTPException 400 if t_end <= t_start, or if the requested range
            and step would produce more than MAX_TRACK_POINTS samples.
    """
    try:
        sat = get_satellite(satellite)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"unknown satellite key: {satellite}",
        ) from exc

    t0 = _ensure_utc(t_start)
    t1 = _ensure_utc(t_end)
    if t1 <= t0:
        raise HTTPException(
            status_code=400,
            detail="t_end must be strictly after t_start",
        )

    duration_s = (t1 - t0).total_seconds()
    n_points = math.ceil(duration_s / step_seconds) + 1
    if n_points > MAX_TRACK_POINTS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"requested {n_points} points, above the {MAX_TRACK_POINTS} "
                f"cap; increase step_seconds or shorten the time range"
            ),
        )

    points: list[TrackPoint] = []
    for i in range(n_points):
        dt = t0 + __import__("datetime").timedelta(seconds=i * step_seconds)
        if dt > t1:
            break
        state = sat.at_utc(dt)
        points.append(
            TrackPoint(
                time_utc=state.time_utc,
                lat_deg=state.lat_deg,
                lon_deg=state.lon_deg,
                alt_m=state.alt_m,
                speed_km_s=state.speed_km_s,
                in_eclipse=sat.is_in_eclipse_utc(dt),
            )
        )

    return TrackResponse(
        key=satellite,
        name=sat.name,
        t_start=t0,
        t_end=t1,
        step_seconds=step_seconds,
        n_points=len(points),
        points=points,
    )


@router.get("/visibility", response_model=VisibilityResponse)
async def visibility(
    satellite: str = Query(..., description="Catalog key."),
    ground_lat_deg: float = Query(..., ge=-90.0, le=90.0),
    ground_lon_deg: float = Query(..., ge=-180.0, le=180.0),
    ground_alt_m: float = Query(0.0),
    t_start: datetime = Query(...),
    t_end: datetime = Query(...),
    step_seconds: float = Query(30.0, gt=0.0),
    min_elevation_deg: float = Query(5.0, ge=0.0, le=90.0),
) -> VisibilityResponse:
    """Return visibility windows for a satellite from a ground site.

    Raises:
        HTTPException 404 if the satellite key is not in the catalog.
        HTTPException 400 if t_end <= t_start or step_seconds <= 0.
    """
    try:
        sat = get_satellite(satellite)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"unknown satellite key: {satellite}",
        ) from exc

    t0 = _ensure_utc(t_start)
    t1 = _ensure_utc(t_end)
    if t1 <= t0:
        raise HTTPException(
            status_code=400,
            detail="t_end must be strictly after t_start",
        )

    node = GroundNode(
        name="ground",
        lat_deg=ground_lat_deg,
        lon_deg=ground_lon_deg,
        alt_m=ground_alt_m,
    )
    windows = visibility_windows(
        sat=sat,
        node=node,
        t_start=t0,
        t_end=t1,
        step_seconds=step_seconds,
        min_elevation_deg=min_elevation_deg,
    )

    return VisibilityResponse(
        key=satellite,
        name=sat.name,
        ground=GroundSite(
            name=node.name,
            lat_deg=node.lat_deg,
            lon_deg=node.lon_deg,
            alt_m=node.alt_m,
        ),
        min_elevation_deg=min_elevation_deg,
        t_start=t0,
        t_end=t1,
        n_windows=len(windows),
        windows=[
            VisibilityWindowModel(
                start_utc=w.start_utc,
                end_utc=w.end_utc,
                duration_seconds=w.duration_seconds,
                peak_elevation_deg=w.peak_elevation_deg,
                peak_time_utc=w.peak_time_utc,
            )
            for w in windows
        ],
    )
