"""Xidian microwave power beaming - TRL 4-5 (Section 6).

Validates the cascade composition reproduces both figures:
  * 20.8% on-target DC-to-DC at >100 m to a stationary target
  * 3-5% end-to-end wall-plug-to-battery for the moving-drone case

Error bound: on-target reproduced within 5% relative error.
End-to-end must fall inside the reported 3-5% band.

Epistemic categories: the 20.8% and 3-5% values are [PHYSICAL
MEASUREMENT]. The intermediate cascade values are [ESTIMATED MODEL]
parameters.
"""

from __future__ import annotations

import math

from app.physics.benchmarks import BENCHMARKS
from app.physics.link_budget import (
    XIDIAN_DUAL_REPORT,
    DualEfficiencyReport,
)


def _xidian_figures() -> dict[str, float]:
    """Return the Xidian figures keyed by lowercased label.

    Lowercasing lets the tests match on stable substrings without
    depending on the exact capitalization of the source labels.
    """
    xidian = next(b for b in BENCHMARKS if "Xidian" in b.name)
    return {label.lower(): value for label, value, _units in xidian.reported_figures}


def test_table_carries_20_8_percent_figure() -> None:
    figures = _xidian_figures()
    on_target = next(v for k, v in figures.items() if "on-target" in k)
    assert math.isclose(on_target, 0.208, rel_tol=1e-12), on_target


def test_table_carries_3_to_5_percent_band() -> None:
    figures = _xidian_figures()
    overall = next(v for k, v in figures.items() if "overall" in k)
    assert 0.03 <= overall <= 0.05, overall


def test_cascade_reproduces_on_target_within_5_percent() -> None:
    """Given the three published stage factors (beam collection 0.880,
    DC-to-RF 0.50, RF-to-DC 0.47), the product must reproduce 0.208
    within 5% relative error. This is the specific s0-8/s9-2 claim."""
    beam_collection = 0.880
    dc_to_rf = 0.50
    rf_to_dc = 0.47
    predicted = beam_collection * dc_to_rf * rf_to_dc
    reported = 0.208
    error = abs(predicted - reported) / reported
    assert error < 0.05, f"on-target error {error:.4f} exceeds 5%"


def test_cascade_end_to_end_lands_in_reported_band() -> None:
    """Extending the on-target value with wall-plug-to-DC, tracking
    loss, and battery-charge factors must land inside 3-5%."""
    on_target = 0.208
    wall_plug_to_dc = 0.75
    tracking_loss = 0.40
    battery = 0.70
    predicted = on_target * wall_plug_to_dc * tracking_loss * battery
    assert 0.03 <= predicted <= 0.05, f"end-to-end prediction {predicted:.4f} outside 3-5% band"


def test_dual_report_pairs_both_figures() -> None:
    """The DualEfficiencyReport object must carry both figures so that
    reporting one without the other is structurally impossible."""
    r: DualEfficiencyReport = XIDIAN_DUAL_REPORT
    assert math.isclose(r.favorable_value, 0.208, rel_tol=1e-12)
    assert 0.03 <= r.unfavorable_value <= 0.05
    summary = r.summary()
    assert "20.80%" in summary
    assert "Xidian" in summary
