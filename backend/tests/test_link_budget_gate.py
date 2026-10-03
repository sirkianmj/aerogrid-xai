"""Sprint 0 task s0-9 - Scientific gate: cascaded link budget verified.

Roadmap gate:
    End-to-end efficiency = product of stages; BOTH 20.8% and 3-5% reported.

This suite is intentionally separate from test_link_budget.py. It is the
formal gate suite for s0-9 and contains:

- Per-stage isolated unit tests (transmitter, beam, receiver, battery)
- A parametrized product-of-stages test
- A canonical cascade order test
- A dual-reporting invariant test
"""

import math

import pytest

from app.physics.link_budget import (
    CANONICAL_STAGES,
    XIDIAN_DUAL_REPORT,
    DualEfficiencyReport,
    LinkBudget,
    Stage,
    build_canonical_link_budget,
)


# --- Per-stage isolated unit tests -----------------------------------------

def test_transmitter_stage_isolated() -> None:
    """Stage 1: electrical-to-optical or electrical-to-RF conversion."""
    tx = Stage("transmitter", 0.50, source="[ESTIMATED MODEL]")
    assert tx.name == "transmitter"
    assert math.isclose(tx.efficiency, 0.50, rel_tol=1e-12)
    with pytest.raises(ValueError):
        Stage("transmitter", 1.01)
    with pytest.raises(ValueError):
        Stage("transmitter", -0.01)


def test_beam_stage_isolated() -> None:
    """Stage 2: beam transmission and spillover efficiency."""
    beam = Stage("beam", 0.880, source="[PHYSICAL MEASUREMENT] Xidian")
    assert beam.name == "beam"
    assert math.isclose(beam.efficiency, 0.880, rel_tol=1e-12)
    with pytest.raises(ValueError):
        Stage("beam", 1.01)
    with pytest.raises(ValueError):
        Stage("beam", -0.01)


def test_receiver_stage_isolated() -> None:
    """Stage 3: receiver capture and conversion to DC."""
    rx = Stage("receiver", 0.47, source="[ESTIMATED MODEL]")
    assert rx.name == "receiver"
    assert math.isclose(rx.efficiency, 0.47, rel_tol=1e-12)
    with pytest.raises(ValueError):
        Stage("receiver", 1.01)
    with pytest.raises(ValueError):
        Stage("receiver", -0.01)


def test_battery_stage_isolated() -> None:
    """Stage 4: battery charging efficiency."""
    batt = Stage("battery", 0.70, source="[ESTIMATED MODEL]")
    assert batt.name == "battery"
    assert math.isclose(batt.efficiency, 0.70, rel_tol=1e-12)
    with pytest.raises(ValueError):
        Stage("battery", 1.01)
    with pytest.raises(ValueError):
        Stage("battery", -0.01)


# --- Canonical cascade order ------------------------------------------------

def test_canonical_stages_constant() -> None:
    """The canonical cascade order is fixed by Section 8.4."""
    assert CANONICAL_STAGES == ("transmitter", "beam", "receiver", "battery")


def test_canonical_link_budget_stage_order() -> None:
    lb = build_canonical_link_budget(
        input_power_w=1000.0,
        transmitter_eff=0.50,
        beam_eff=0.88,
        receiver_eff=0.47,
        battery_eff=0.70,
    )
    names = tuple(s.name for s in lb.stages)
    assert names == CANONICAL_STAGES


# --- Formal product-of-stages test ------------------------------------------

@pytest.mark.parametrize(
    "tx,beam,rx,batt",
    [
        (0.50, 0.88, 0.47, 0.70),
        (0.75, 0.90, 0.80, 0.95),
        (0.30, 0.50, 0.40, 0.60),
        (1.00, 1.00, 1.00, 1.00),
        (0.10, 0.10, 0.10, 0.10),
    ],
)
def test_end_to_end_equals_product_of_stages(
    tx: float, beam: float, rx: float, batt: float
) -> None:
    """The end-to-end efficiency must equal the product of the four stages,
    to within floating-point tolerance. No stage may be collapsed."""
    lb = build_canonical_link_budget(
        input_power_w=1000.0,
        transmitter_eff=tx,
        beam_eff=beam,
        receiver_eff=rx,
        battery_eff=batt,
    )
    expected = tx * beam * rx * batt
    assert math.isclose(lb.end_to_end_efficiency, expected, rel_tol=1e-12)
    assert math.isclose(lb.output_power_w, 1000.0 * expected, rel_tol=1e-12)


def test_canonical_builder_prevents_collapse() -> None:
    """A collapsed single-stage LinkBudget can be constructed directly, but
    the canonical builder always produces exactly four distinct stages."""
    collapsed = LinkBudget(
        input_power_w=1000.0,
        stages=(Stage("everything", 0.5),),
    )
    assert math.isclose(collapsed.end_to_end_efficiency, 0.5, rel_tol=1e-12)

    full = build_canonical_link_budget(
        input_power_w=1000.0,
        transmitter_eff=0.5,
        beam_eff=1.0,
        receiver_eff=1.0,
        battery_eff=1.0,
    )
    assert math.isclose(full.end_to_end_efficiency, 0.5, rel_tol=1e-12)
    assert len(full.stages) == 4
    assert tuple(s.name for s in full.stages) == CANONICAL_STAGES


# --- Dual-reporting invariant (Section 6) -----------------------------------

def test_dual_report_construction_valid() -> None:
    r = DualEfficiencyReport(
        favorable_label="on-target",
        favorable_value=0.208,
        unfavorable_label="end-to-end",
        unfavorable_value=0.04,
        source="test",
    )
    assert r.favorable_value > r.unfavorable_value


def test_dual_report_rejects_favorable_below_unfavorable() -> None:
    with pytest.raises(ValueError):
        DualEfficiencyReport(
            favorable_label="a",
            favorable_value=0.04,
            unfavorable_label="b",
            unfavorable_value=0.208,
            source="test",
        )


def test_dual_report_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        DualEfficiencyReport("a", 1.5, "b", 0.04, "test")
    with pytest.raises(ValueError):
        DualEfficiencyReport("a", 0.208, "b", -0.1, "test")


def test_xidian_dual_report_both_figures_present() -> None:
    """The Xidian dual report must carry BOTH figures. Reporting the
    favorable figure alone is a Section 6 violation."""
    r = XIDIAN_DUAL_REPORT
    assert math.isclose(r.favorable_value, 0.208, rel_tol=1e-12)
    assert 0.03 <= r.unfavorable_value <= 0.05
    summary = r.summary()
    assert "20.80%" in summary
    assert "4.00%" in summary
    assert "Xidian" in summary


def test_dual_report_summary_format() -> None:
    """Both figures must appear in the summary text so no caller can
    accidentally report the favorable figure alone."""
    summary = XIDIAN_DUAL_REPORT.summary()
    assert "on-target DC-to-DC" in summary
    assert "end-to-end wall-plug-to-battery" in summary
