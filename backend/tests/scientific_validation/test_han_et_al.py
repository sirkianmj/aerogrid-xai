"""Han et al. perovskite-thermoelectric tandem laser receiver - TRL 3.

Bench-mounted component test (Tsinghua / Civil Aviation University of
China). Champion power conversion efficiency 38.49% under 520 nm laser
at 1.2 W/cm^2; powered a stationary drone propeller blade. Not flight
tested.

This is a **component** efficiency, not a link efficiency. The suite
does not fold it into a system-level figure; it validates that the
value is preserved as a receiver conversion efficiency.

Known limit **P5**: the citation lacks a DOI. The suite asserts value
preservation in the table, not paper existence. See the README for the
carried-forward limitation.

Epistemic category: 38.49% is [PHYSICAL MEASUREMENT].
"""

from __future__ import annotations

import math

from app.physics.benchmarks import BENCHMARKS


def _han() -> dict[str, float]:
    han = next(b for b in BENCHMARKS if "Han" in b.name)
    return {label: value for label, value, _units in han.reported_figures}


def test_table_carries_38_49_percent() -> None:
    figures = _han()
    eta = next(v for k, v in figures.items() if "efficiency" in k.lower())
    assert math.isclose(eta, 0.3849, rel_tol=1e-12), eta


def test_table_carries_520nm_wavelength() -> None:
    figures = _han()
    wl = next(v for k, v in figures.items() if "wavelength" in k.lower())
    assert math.isclose(wl, 520.0, rel_tol=1e-12), wl


def test_table_carries_input_power_density() -> None:
    figures = _han()
    density = next(v for k, v in figures.items() if "density" in k.lower())
    assert math.isclose(density, 1.2, rel_tol=1e-12), density


def test_trl_tag_is_3_component() -> None:
    """TRL 3, not 5 or 6. The Han et al. device is bench-mounted; if the
    TRL ever shifts, this test forces a re-audit of the scope note."""
    han = next(b for b in BENCHMARKS if "Han" in b.name)
    assert han.trl == 3, f"Han et al. TRL {han.trl}; expected 3"


def test_scope_note_states_not_flight_tested() -> None:
    han = next(b for b in BENCHMARKS if "Han" in b.name)
    note = han.scope_note.lower()
    assert "not" in note and ("flight" in note or "bench" in note), han.scope_note


def test_38_49_is_receiver_not_link() -> None:
    """The 38.49% figure is a receiver conversion efficiency, not an
    end-to-end link efficiency. The suite classifies it accordingly and
    refuses to multiply it into a system-level claim."""
    figures = _han()
    label = next(k for k, _v in figures.items() if "efficiency" in k.lower())
    assert "power conversion" in label.lower() or "receiver" in label.lower(), label
