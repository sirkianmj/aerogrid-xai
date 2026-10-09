"""Digital-twin state comparison and discrepancy tracking.

Roadmap task s6-3: Digital Twin state comparison (predicted vs.
observed).
Gate: Discrepancy logged; triggers update when > threshold.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 37.1 (Physics Model Refinement) and Section 24.1
    (Digital Twin Composition).

Role
----

The Digital Twin maintains a predicted state from the physics
models. Operational measurements arrive as observed values for the
same fields. This module:

  1. Records every (field, predicted, observed) triple as a
     DiscrepancyRecord with absolute and relative error.
  2. Marks a record as "triggered" when the error exceeds the
     field's configured threshold.
  3. Exposes an aggregate trigger signal that the closed loop uses
     to decide when to invoke the Bayesian update (s6-1) and PWL
     tightening (s6-2).

Threshold semantics
-------------------

A field's threshold is either absolute (error > threshold) or
relative (error / max(|predicted|, eps) > threshold) or both, if
both are supplied. The predicate is "exceeds at least one provided
threshold"; a field with no threshold configured never triggers.

Determinism
-----------

All operations are pure functions of the inputs. The history is
append-only and read back as a tuple, preserving insertion order.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

EPS = 1e-12


@dataclass(frozen=True)
class FieldThreshold:
    """Threshold configuration for one state field.

    Attributes:
        absolute: Absolute error threshold. If None, absolute error
            is not checked.
        relative: Relative error threshold (fraction of predicted
            magnitude). If None, relative error is not checked.

    At least one of the two must be provided. A field with no
    threshold never triggers.
    """

    absolute: float | None = None
    relative: float | None = None

    def __post_init__(self) -> None:
        if self.absolute is None and self.relative is None:
            raise ValueError("at least one of absolute or relative must be provided")
        if self.absolute is not None and (not math.isfinite(self.absolute) or self.absolute < 0.0):
            raise ValueError(f"absolute must be finite and non-negative; got {self.absolute}")
        if self.relative is not None and (not math.isfinite(self.relative) or self.relative < 0.0):
            raise ValueError(f"relative must be finite and non-negative; got {self.relative}")


@dataclass(frozen=True)
class DiscrepancyRecord:
    """One discrepancy observation.

    Attributes:
        field_name: The state field.
        predicted: Model-predicted value.
        observed: Operational measurement.
        absolute_error: |observed - predicted|.
        relative_error: absolute_error / max(|predicted|, EPS).
        triggered: True if the record exceeded the field's threshold.
        step: Zero-based sequence number.
    """

    field_name: str
    predicted: float
    observed: float
    absolute_error: float
    relative_error: float
    triggered: bool
    step: int


class DigitalTwinMonitor:
    """Track predicted-versus-observed discrepancies field by field.

    Usage:

        monitor = DigitalTwinMonitor({
            "temperature_k": FieldThreshold(absolute=2.0),
            "efficiency": FieldThreshold(relative=0.05),
        })
        record = monitor.observe("temperature_k", predicted=320.0, observed=323.5)
        if record.triggered:
            ...  # invoke refinement
    """

    def __init__(self, thresholds: Mapping[str, FieldThreshold]) -> None:
        self._thresholds: dict[str, FieldThreshold] = dict(thresholds)
        for name, t in self._thresholds.items():
            if not name:
                raise ValueError("threshold field names must be non-empty")
            if not isinstance(t, FieldThreshold):
                raise ValueError(
                    f"thresholds[{name!r}] must be a FieldThreshold; got {type(t).__name__}"
                )
        self._history: list[DiscrepancyRecord] = []

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._thresholds))

    def threshold(self, field_name: str) -> FieldThreshold | None:
        return self._thresholds.get(field_name)

    def history(self) -> tuple[DiscrepancyRecord, ...]:
        return tuple(self._history)

    def _evaluate_threshold(
        self,
        threshold: FieldThreshold,
        absolute_error: float,
        relative_error: float,
    ) -> bool:
        abs_exceeded = threshold.absolute is not None and absolute_error > threshold.absolute
        rel_exceeded = threshold.relative is not None and relative_error > threshold.relative
        return abs_exceeded or rel_exceeded

    def observe(self, field_name: str, predicted: float, observed: float) -> DiscrepancyRecord:
        """Record one discrepancy observation.

        Raises:
            ValueError on non-finite inputs or unknown field.
        """
        if not field_name:
            raise ValueError("field_name must be non-empty")
        if not (math.isfinite(predicted) and math.isfinite(observed)):
            raise ValueError(
                f"predicted and observed must be finite; got "
                f"predicted={predicted}, observed={observed}"
            )
        if field_name not in self._thresholds:
            raise ValueError(
                f"unknown field {field_name!r}; known fields: {list(self._thresholds)}"
            )

        absolute_error = abs(observed - predicted)
        relative_error = absolute_error / max(abs(predicted), EPS)
        threshold = self._thresholds[field_name]
        triggered = self._evaluate_threshold(threshold, absolute_error, relative_error)

        record = DiscrepancyRecord(
            field_name=field_name,
            predicted=float(predicted),
            observed=float(observed),
            absolute_error=float(absolute_error),
            relative_error=float(relative_error),
            triggered=triggered,
            step=len(self._history),
        )
        self._history.append(record)
        return record

    def triggered_fields(self) -> tuple[str, ...]:
        """Return field names with at least one triggered record in
        the current history."""
        triggered = {r.field_name for r in self._history if r.triggered}
        return tuple(sorted(triggered))

    def should_refine(self) -> bool:
        """True if any field has triggered at any point in the history."""
        return any(r.triggered for r in self._history)

    def latest(self, field_name: str) -> DiscrepancyRecord | None:
        """Return the most recent record for a field, or None."""
        for record in reversed(self._history):
            if record.field_name == field_name:
                return record
        return None

    def clear(self) -> None:
        """Clear the record history. Thresholds are preserved."""
        self._history.clear()
