"""Tests for Digital Twin discrepancy tracking.

Roadmap task s6-3: Digital Twin state comparison (predicted vs. observed).
Gate: Discrepancy logged; triggers update when > threshold.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.refinement.discrepancy import (
    DigitalTwinMonitor,
    DiscrepancyRecord,
    FieldThreshold,
)

# -- FieldThreshold validation ----------------------------------------------


def test_threshold_requires_at_least_one_bound() -> None:
    with pytest.raises(ValueError, match="at least one of absolute or relative"):
        FieldThreshold()


def test_threshold_rejects_negative_absolute() -> None:
    with pytest.raises(ValueError, match="absolute must be finite and non-negative"):
        FieldThreshold(absolute=-0.5)


def test_threshold_rejects_negative_relative() -> None:
    with pytest.raises(ValueError, match="relative must be finite and non-negative"):
        FieldThreshold(relative=-0.1)


def test_threshold_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="absolute must be finite"):
        FieldThreshold(absolute=float("inf"))
    with pytest.raises(ValueError, match="relative must be finite"):
        FieldThreshold(relative=float("nan"))


def test_threshold_accepts_both() -> None:
    t = FieldThreshold(absolute=1.0, relative=0.05)
    assert t.absolute == 1.0
    assert t.relative == 0.05


# -- Monitor construction ---------------------------------------------------


def test_monitor_rejects_empty_field_name() -> None:
    with pytest.raises(ValueError, match="field names must be non-empty"):
        DigitalTwinMonitor({"": FieldThreshold(absolute=1.0)})


def test_monitor_rejects_bad_threshold_type() -> None:
    with pytest.raises(ValueError, match="must be a FieldThreshold"):
        DigitalTwinMonitor({"x": 1.0})  # type: ignore[dict-item]


def test_monitor_field_names_sorted() -> None:
    m = DigitalTwinMonitor(
        {
            "zeta": FieldThreshold(absolute=1.0),
            "alpha": FieldThreshold(absolute=1.0),
        }
    )
    assert m.field_names == ("alpha", "zeta")


def test_monitor_empty_history_initially() -> None:
    m = DigitalTwinMonitor({"x": FieldThreshold(absolute=1.0)})
    assert m.history() == ()
    assert m.triggered_fields() == ()
    assert not m.should_refine()


# -- observe ----------------------------------------------------------------


def test_observe_records_discrepancy() -> None:
    m = DigitalTwinMonitor({"temperature_k": FieldThreshold(absolute=2.0)})
    rec = m.observe("temperature_k", predicted=320.0, observed=321.0)
    assert rec.field_name == "temperature_k"
    assert rec.predicted == 320.0
    assert rec.observed == 321.0
    assert rec.absolute_error == pytest.approx(1.0)
    assert rec.relative_error == pytest.approx(1.0 / 320.0)
    assert rec.triggered is False


def test_observe_triggers_when_above_absolute() -> None:
    m = DigitalTwinMonitor({"temperature_k": FieldThreshold(absolute=2.0)})
    rec = m.observe("temperature_k", predicted=320.0, observed=323.5)
    assert rec.triggered is True
    assert m.should_refine()
    assert m.triggered_fields() == ("temperature_k",)


def test_observe_triggers_when_above_relative() -> None:
    m = DigitalTwinMonitor({"efficiency": FieldThreshold(relative=0.05)})
    # 0.5 -> 0.6 is 20 percent, above the 5 percent threshold.
    rec = m.observe("efficiency", predicted=0.5, observed=0.6)
    assert rec.triggered is True


def test_observe_does_not_trigger_below_relative() -> None:
    m = DigitalTwinMonitor({"efficiency": FieldThreshold(relative=0.05)})
    # 0.5 -> 0.52 is 4 percent, below 5 percent.
    rec = m.observe("efficiency", predicted=0.5, observed=0.52)
    assert rec.triggered is False


def test_observe_triggers_on_either_bound_when_both_configured() -> None:
    m = DigitalTwinMonitor(
        {
            "x": FieldThreshold(absolute=10.0, relative=0.01),
        }
    )
    # Fails absolute (20 > 10) but passes relative (0.005 < 0.01).
    rec = m.observe("x", predicted=4000.0, observed=4020.0)
    assert rec.absolute_error == pytest.approx(20.0)
    assert rec.relative_error == pytest.approx(0.005)
    assert rec.triggered is True
    # Fails relative (0.02 > 0.01) but passes absolute (5 < 10).
    rec2 = m.observe("x", predicted=250.0, observed=255.0)
    assert rec2.absolute_error == pytest.approx(5.0)
    assert rec2.relative_error == pytest.approx(0.02)
    assert rec2.triggered is True
    # Both bounds pass (abs 5 < 10, rel 0.005 < 0.01): no trigger.
    rec3 = m.observe("x", predicted=1000.0, observed=1005.0)
    assert rec3.triggered is False


def test_observe_rejects_unknown_field() -> None:
    m = DigitalTwinMonitor({"x": FieldThreshold(absolute=1.0)})
    with pytest.raises(ValueError, match="unknown field"):
        m.observe("y", predicted=0.0, observed=0.0)


def test_observe_rejects_non_finite() -> None:
    m = DigitalTwinMonitor({"x": FieldThreshold(absolute=1.0)})
    with pytest.raises(ValueError, match="must be finite"):
        m.observe("x", predicted=float("nan"), observed=0.0)
    with pytest.raises(ValueError, match="must be finite"):
        m.observe("x", predicted=0.0, observed=float("inf"))


def test_observe_rejects_empty_field_name() -> None:
    m = DigitalTwinMonitor({"x": FieldThreshold(absolute=1.0)})
    with pytest.raises(ValueError, match="field_name must be non-empty"):
        m.observe("", predicted=0.0, observed=0.0)


# -- History and step counter -----------------------------------------------


def test_history_grows_in_order() -> None:
    m = DigitalTwinMonitor(
        {
            "a": FieldThreshold(absolute=1.0),
            "b": FieldThreshold(absolute=1.0),
        }
    )
    m.observe("a", 0.0, 0.1)
    m.observe("b", 0.0, 0.1)
    m.observe("a", 0.0, 0.2)
    history = m.history()
    assert len(history) == 3
    assert [r.field_name for r in history] == ["a", "b", "a"]
    assert [r.step for r in history] == [0, 1, 2]


def test_triggered_fields_reflects_any_trigger() -> None:
    m = DigitalTwinMonitor(
        {
            "a": FieldThreshold(absolute=1.0),
            "b": FieldThreshold(absolute=1.0),
        }
    )
    m.observe("a", 0.0, 0.5)  # not triggered
    m.observe("b", 0.0, 2.0)  # triggered
    assert m.triggered_fields() == ("b",)


def test_latest_returns_most_recent() -> None:
    m = DigitalTwinMonitor({"a": FieldThreshold(absolute=1.0)})
    m.observe("a", 0.0, 0.1)
    m.observe("a", 0.0, 0.2)
    latest = m.latest("a")
    assert latest is not None
    assert latest.observed == pytest.approx(0.2)


def test_latest_none_for_missing_field() -> None:
    m = DigitalTwinMonitor({"a": FieldThreshold(absolute=1.0)})
    assert m.latest("a") is None


def test_clear_preserves_thresholds() -> None:
    m = DigitalTwinMonitor({"a": FieldThreshold(absolute=1.0)})
    m.observe("a", 0.0, 5.0)
    assert m.should_refine()
    m.clear()
    assert m.history() == ()
    assert not m.should_refine()
    # Threshold still works.
    rec = m.observe("a", 0.0, 5.0)
    assert rec.triggered is True


# -- Threshold accessor -----------------------------------------------------


def test_threshold_returns_none_for_missing() -> None:
    m = DigitalTwinMonitor({"a": FieldThreshold(absolute=1.0)})
    assert m.threshold("a") is not None
    assert m.threshold("b") is None


# -- Gate: discrepancy logged, update triggered -----------------------------


def test_gate_discrepancy_logged_and_trigger_on_threshold() -> None:
    """The s6-3 gate: discrepancies are logged, and exceeding a
    threshold raises the trigger that drives the closed loop."""
    monitor = DigitalTwinMonitor(
        {
            "receiver_efficiency": FieldThreshold(relative=0.05),
            "receiver_temperature_k": FieldThreshold(absolute=2.0),
        }
    )

    # Initial predictions are close: no trigger.
    rec_eff = monitor.observe("receiver_efficiency", predicted=0.20, observed=0.205)
    rec_temp = monitor.observe("receiver_temperature_k", predicted=340.0, observed=341.0)
    assert not rec_eff.triggered
    assert not rec_temp.triggered
    assert not monitor.should_refine()

    # Operational drift: temperature runs 3 K hotter than predicted.
    rec_drift = monitor.observe("receiver_temperature_k", predicted=340.0, observed=343.0)
    assert rec_drift.triggered is True
    assert monitor.should_refine()
    assert "receiver_temperature_k" in monitor.triggered_fields()

    # History is preserved.
    assert len(monitor.history()) == 3


def test_gate_zero_predicted_uses_eps_guard() -> None:
    """When predicted is exactly zero, relative error is defined
    against EPS rather than dividing by zero."""
    monitor = DigitalTwinMonitor({"x": FieldThreshold(relative=1.0)})
    rec = monitor.observe("x", predicted=0.0, observed=1e-6)
    # absolute=1e-6, EPS=1e-12, so relative=1e6, way over threshold.
    assert rec.triggered is True


def test_record_is_frozen() -> None:
    rec = DiscrepancyRecord(
        field_name="x",
        predicted=0.0,
        observed=1.0,
        absolute_error=1.0,
        relative_error=1.0,
        triggered=True,
        step=0,
    )
    with pytest.raises(FrozenInstanceError):
        rec.predicted = 2.0  # type: ignore[misc]
