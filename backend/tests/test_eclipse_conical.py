"""Cross-validation of the eclipse models.

Roadmap task:
    s1-4 Eclipse period detection - "Validated against published eclipse
    times". We do not have access to CelesTrak's published eclipse
    predictions in this environment, so we validate the cylindrical
    model against the more conservative conical (finite-Sun) model of
    Vallado. The two models must agree on the vast majority of samples;
    disagreement is confined to the umbra-penumbra transition region.
"""

from datetime import timedelta
from pathlib import Path

import pytest
from skyfield.api import load  # type: ignore[import-untyped]

from app.physics.orbital import Satellite

FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"
TS = load.timescale()


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


def test_conical_umbra_is_subset_of_cylindrical(iss: Satellite) -> None:
    """The conical umbra is a strict subset of the cylindrical shadow:
    every conical-umbra sample is also cylindrical-umbra, but not
    necessarily the reverse (there is a thin penumbra shell where the
    cylindrical model says eclipse but the conical model does not)."""
    t0 = iss.epoch_utc
    n = 288
    subset_violations = 0
    for i in range(n):
        t = TS.from_datetime(t0 + timedelta(minutes=5 * i))
        if iss.is_in_eclipse_conical(t) and not iss.is_in_eclipse(t):
            subset_violations += 1
    assert subset_violations == 0, (
        f"Conical umbra not a subset of cylindrical: {subset_violations} violations in {n} samples"
    )


def test_cylindrical_and_conical_agree_above_95_percent(iss: Satellite) -> None:
    """Over 24 hours, the two eclipse models agree on at least 95% of
    samples. Disagreement occurs only in the penumbra shell."""
    t0 = iss.epoch_utc
    n = 288
    agree = 0
    for i in range(n):
        t = TS.from_datetime(t0 + timedelta(minutes=5 * i))
        if iss.is_in_eclipse(t) == iss.is_in_eclipse_conical(t):
            agree += 1
    fraction = agree / n
    assert fraction >= 0.95, f"Model agreement {fraction:.4f} below 0.95 threshold"


def test_eclipse_fraction_is_consistent_between_models(iss: Satellite) -> None:
    """The eclipse fraction computed from either model should be within
    5 percentage points of the other."""
    t0 = iss.epoch_utc
    n = 288
    cyl_count = 0
    con_count = 0
    for i in range(n):
        t = TS.from_datetime(t0 + timedelta(minutes=5 * i))
        if iss.is_in_eclipse(t):
            cyl_count += 1
        if iss.is_in_eclipse_conical(t):
            con_count += 1
    cyl_frac = cyl_count / n
    con_frac = con_count / n
    assert abs(cyl_frac - con_frac) < 0.05, (
        f"Eclipse fractions diverge: cylindrical {cyl_frac:.3f} vs conical {con_frac:.3f}"
    )


def test_conical_umbra_is_deterministic(iss: Satellite) -> None:
    t = TS.from_datetime(iss.epoch_utc)
    assert iss.is_in_eclipse_conical(t) == iss.is_in_eclipse_conical(t)
