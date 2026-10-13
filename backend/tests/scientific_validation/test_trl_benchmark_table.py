"""Cross-benchmark invariants for the TRL-tagged table (Section 6).

Asserts that the table carries all five sources named by the roadmap
(s9-2), that every entry has a TRL in [1, 9], a non-empty scope note,
a non-empty citation, and at least one reported figure. Every entry's
figures are classified as Section 21 [PHYSICAL MEASUREMENT].
"""

from __future__ import annotations

from app.physics.benchmarks import BENCHMARKS

EXPECTED_ORGANIZATIONS = {
    "PowerLight ground-to-air laser to UAV": "PowerLight",
    "Xidian microwave to moving drone": "Xidian",
    "Overview Energy airborne laser to ground": "Overview Energy",
    "DARPA POWER laser record": "DARPA",
    "Han et al. perovskite-thermoelectric tandem laser receiver": "Han",
}


def test_all_five_named_sources_are_present() -> None:
    names = {b.name for b in BENCHMARKS}
    for expected in EXPECTED_ORGANIZATIONS:
        assert expected in names, f"missing benchmark: {expected!r}"


def test_every_benchmark_has_trl_in_range() -> None:
    for b in BENCHMARKS:
        assert 1 <= b.trl <= 9, f"{b.name}: TRL {b.trl} out of range"


def test_every_benchmark_has_scope_note_and_citation() -> None:
    for b in BENCHMARKS:
        assert b.scope_note.strip(), f"{b.name}: empty scope note"
        assert b.citation.strip(), f"{b.name}: empty citation"


def test_every_benchmark_has_at_least_one_figure() -> None:
    for b in BENCHMARKS:
        assert len(b.reported_figures) >= 1, f"{b.name}: no reported figures"


def test_xidian_carries_both_efficiency_figures() -> None:
    """Specification Section 6: the Xidian 20.8% and 3-5% figures must
    both be reported. Reporting the favorable figure alone is a
    specification violation. This test fails if the table ever loses
    the 3-5% entry."""
    xidian = next(b for b in BENCHMARKS if "Xidian" in b.name)
    labels = [label.lower() for label, _value, _units in xidian.reported_figures]
    assert any("on-target" in lab for lab in labels), labels
    assert any("overall" in lab for lab in labels), labels


def test_han_et_al_is_trl_3_component() -> None:
    """Han et al. is a bench-mounted component (TRL 3), not a flight
    test. If its TRL ever changes, its scope must be re-audited."""
    han = next(b for b in BENCHMARKS if "Han" in b.name)
    assert han.trl == 3, f"Han et al. TRL {han.trl}; expected 3"


def test_overview_scope_disclaims_satellite_to_uav() -> None:
    """Section 6 explicitly warns that Overview Energy is a
    ground-receiver analog, not a satellite-to-mobile-UAV validation."""
    ov = next(b for b in BENCHMARKS if "Overview" in b.name)
    note = ov.scope_note.lower()
    assert "not" in note and ("satellite" in note or "mobile" in note), ov.scope_note


def test_powerlight_scope_names_single_transmitter() -> None:
    """PowerLight is a single ground transmitter, single cooperative
    target. The scope note must preserve that narrow claim."""
    pl = next(b for b in BENCHMARKS if "PowerLight" in b.name)
    note = pl.scope_note.lower()
    assert "single" in note, pl.scope_note


def test_darpa_scope_names_fixed_ground_to_ground() -> None:
    """DARPA POWER is a fixed-to-fixed demonstration. It does not
    validate airborne dynamics."""
    darpa = next(b for b in BENCHMARKS if "DARPA" in b.name)
    note = darpa.scope_note.lower()
    assert "fixed" in note, darpa.scope_note
