"""Overview Energy airborne laser - TRL 5 (Section 6).

Laser beamed from a moving Cessna Caravan at ~5,000 m to fixed ground
solar panels in Pennsylvania.

This is a **ground-receiver architecture analog**, not a
satellite-to-mobile-UAV demonstration. The suite does NOT attempt a
numeric reproduction; the specification itself states this is a
"crawl" phase, not a validated architecture. The validation is that
the scope note carries the disclaimer and the TRL tag matches.

Epistemic categories: the 5,000 m altitude is [PHYSICAL MEASUREMENT].
There is no efficiency figure to validate.
"""

from __future__ import annotations

import math

from app.physics.benchmarks import BENCHMARKS


def test_table_carries_5000m_altitude() -> None:
    ov = next(b for b in BENCHMARKS if "Overview" in b.name)
    altitude = next(v for _k, v, _u in ov.reported_figures if "altitude" in _k.lower())
    assert math.isclose(altitude, 5000.0, rel_tol=1e-12), altitude


def test_scope_note_disclaims_satellite_to_uav_analogy() -> None:
    """The scope note must state that this is a ground-receiver
    architecture analog, not satellite-to-mobile-UAV."""
    ov = next(b for b in BENCHMARKS if "Overview" in b.name)
    note = ov.scope_note.lower()
    assert "ground-receiver" in note or "ground receiver" in note, ov.scope_note
    assert "not" in note, ov.scope_note


def test_trl_tag_is_5() -> None:
    ov = next(b for b in BENCHMARKS if "Overview" in b.name)
    assert ov.trl == 5, f"Overview Energy TRL {ov.trl}; expected 5"
