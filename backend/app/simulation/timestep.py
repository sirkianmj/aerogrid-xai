"""Time-stepping simulation of a mission.

Runs :func:`app.mission.state.compute_mission_state` at successive UTC
instants and returns a time series. This is the backend for the Step 5
simulation view: power delivered over time, thermal margins, eclipse
intervals, cumulative energy.

Every sample carries the Section 21 epistemic tag ``simulation_result``.
A simulation result is the output of the Digital Twin running validated
or estimated physics models -- not a physical measurement, not a formal
verification verdict.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.mission.state import MissionConfig, compute_mission_state

MAX_SAMPLES = 100
PresetKind = Literal["10min", "1hour", "1pass", "custom"]


@dataclass(frozen=True)
class UavSnapshot:
    uav_id: int
    received_power_w: float
    delivered_power_w: float
    receiver_efficiency: float
    thermal_headroom_c: float
    relay_hop_index: int = -1
    thermal_runaway: bool = False


@dataclass(frozen=True)
class SimSample:
    t_utc: str
    elapsed_s: float
    received_power_w: float
    delivered_power_w: float
    cumulative_energy_j: float
    atmospheric_transmittance: float
    satellite_elevation_deg: float
    link_status: str
    uavs: tuple[UavSnapshot, ...]
    epistemic_tag: str = "simulation_result"


@dataclass(frozen=True)
class SimResult:
    samples: tuple[SimSample, ...]
    duration_s: float
    step_s: float
    n_samples: int
    preset: str
    config_summary: dict[str, object]
    warnings: tuple[str, ...]
    epistemic_tag: str = "simulation_result"


def _resolve_anchor(cfg: MissionConfig) -> datetime:
    """Return the default mission time from compute_mission_state."""
    initial = compute_mission_state(cfg, t_utc=None)
    return datetime.fromisoformat(initial.t_utc)


def _window_bounds(preset: PresetKind, duration_s: float) -> tuple[timedelta, timedelta]:
    if preset == "10min":
        return timedelta(minutes=-5), timedelta(minutes=5)
    if preset == "1hour":
        return timedelta(minutes=-30), timedelta(minutes=30)
    if preset == "1pass":
        return timedelta(minutes=-5), timedelta(minutes=5)
    return timedelta(0), timedelta(seconds=duration_s)


def run_simulation(
    cfg: MissionConfig,
    *,
    preset: PresetKind = "1hour",
    duration_s: float = 3600.0,
    step_s: float = 60.0,
) -> SimResult:
    """Run a time-stepping simulation of the mission.

    Determinism: identical (cfg, preset, duration_s, step_s) produces
    identical samples, because compute_mission_state is deterministic.
    """
    anchor = _resolve_anchor(cfg)
    before, after = _window_bounds(preset, duration_s)
    start = anchor + before
    end = anchor + after
    total_s = (end - start).total_seconds()
    if total_s <= 0:
        raise ValueError(f"simulation window has non-positive duration: {total_s}")

    n_samples = max(2, int(total_s / step_s) + 1)
    actual_step = total_s / (n_samples - 1)
    warnings: list[str] = []

    if n_samples > MAX_SAMPLES:
        actual_step = total_s / (MAX_SAMPLES - 1)
        n_samples = MAX_SAMPLES
        warnings.append(
            f"requested step {step_s:.1f}s would yield {int(total_s / step_s) + 1} samples; "
            f"coarsened to {actual_step:.1f}s to keep n_samples <= {MAX_SAMPLES}"
        )

    samples: list[SimSample] = []
    cumulative_j = 0.0
    prev_power_w = 0.0
    for i in range(n_samples):
        t = start + timedelta(seconds=i * actual_step)
        # A per-sample failure (e.g., SGP4 drift out of plausible altitude)
        # must not abort the whole series: the user needs the samples that
        # did succeed, plus a warning naming the failure. Catch broad,
        # record the reason, continue.
        try:
            state = compute_mission_state(cfg, t_utc=t)
        except Exception as exc:
            warnings.append(f"sample {i} failed at {t.isoformat()}: {exc}")
            continue

        if not state.satellite.valid:
            warnings.append(
                f"sample {i}: satellite state invalid -- {state.satellite.invalid_reason}"
            )

        power_w = sum(u.delivered_power_w for u in state.uavs)
        received_w = sum(u.received_power_w for u in state.uavs)

        if i > 0:
            cumulative_j += 0.5 * (prev_power_w + power_w) * actual_step
        prev_power_w = power_w

        samples.append(
            SimSample(
                t_utc=t.isoformat(),
                elapsed_s=(t - start).total_seconds(),
                received_power_w=received_w,
                delivered_power_w=power_w,
                cumulative_energy_j=cumulative_j,
                atmospheric_transmittance=state.atmosphere.transmittance,
                satellite_elevation_deg=state.transmission.elevation_deg,
                link_status=state.transmission.modality,
                uavs=tuple(
                    UavSnapshot(
                        uav_id=u.uav_id,
                        received_power_w=u.received_power_w,
                        delivered_power_w=u.delivered_power_w,
                        receiver_efficiency=u.receiver_efficiency,
                        thermal_headroom_c=u.thermal_headroom_c,
                        relay_hop_index=getattr(u, "relay_hop_index", -1),
                        thermal_runaway=getattr(u, "thermal_runaway", False),
                    )
                    for u in state.uavs
                ),
            )
        )

    config_summary: dict[str, object] = {
        "seed": cfg.seed,
        "satellite_key": cfg.satellite_key,
        "n_uavs": cfg.n_uavs,
        "transmitter_power_w": cfg.transmitter_power_w,
        "wavelength_nm": cfg.wavelength_nm,
        "visibility_km": cfg.visibility_km,
        "cloud_factor": cfg.cloud_factor,
    }

    return SimResult(
        samples=tuple(samples),
        duration_s=total_s,
        step_s=actual_step,
        n_samples=len(samples),
        preset=preset,
        config_summary=config_summary,
        warnings=tuple(warnings),
    )
