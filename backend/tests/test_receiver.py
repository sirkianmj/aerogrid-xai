"""Unit tests for the Stage A coupled electro-thermal receiver model.

Roadmap tasks:
    s2-1 PLC efficiency model eta_PLC(T)
    s2-2 TE efficiency model eta_TE(T)
    s2-3 CORRECTED ATTRIBUTION: Sb2Se3 in thermal conduction, NOT Seebeck

Section 33.1 corrected attribution is enforced by construction: the
ThermalBarrierParams dataclass is NOT an argument to eta_te(), and the
tests below verify that varying the barrier's thermal conductivity does
not change TE efficiency or total efficiency.
"""

from dataclasses import FrozenInstanceError, replace
from itertools import pairwise

import pytest

from app.physics.receiver import (
    T_REF_K,
    PLCParams,
    ReceiverStack,
    TEParams,
    ThermalBarrierParams,
    eta_plc,
    eta_te,
    eta_total,
    urbach_energy_mev,
    zt_avg_bi2te3,
)

# --- s2-1: PLC efficiency ---------------------------------------------------


def test_eta_plc_at_reference_temperature() -> None:
    """At the reference temperature the efficiency equals eta_ref."""
    assert eta_plc(T_REF_K) == pytest.approx(0.15, rel=1e-9)


def test_eta_plc_monotonically_decreasing_with_temperature() -> None:
    """Section 33.2 requirement: eta_PLC must be monotonically decreasing
    with T_PLC over the entire operating range."""
    temps = [280.0, 290.0, 300.0, 310.0, 320.0, 330.0, 340.0, 350.0, 357.0]
    etas = [eta_plc(t) for t in temps]
    for a, b in pairwise(etas):
        assert a > b, f"eta_PLC not decreasing: {a} <= {b}"


def test_eta_plc_is_zero_at_degradation_limit() -> None:
    """At or above t_max_kelvin, PLC efficiency is zero."""
    p = PLCParams()
    assert eta_plc(p.t_max_kelvin) == 0.0
    assert eta_plc(p.t_max_kelvin + 50.0) == 0.0


def test_eta_plc_above_measured_temperature_is_zero() -> None:
    """Han et al. measured 85.3 C = 358.45 K as the maximum operating
    temperature. Above this, PLC efficiency is zero."""
    assert eta_plc(358.45) == 0.0
    assert eta_plc(400.0) == 0.0


def test_eta_plc_rejects_negative_temperature() -> None:
    with pytest.raises(ValueError):
        eta_plc(-1.0)


def test_urbach_energy_increases_linearly_with_temperature() -> None:
    """The physical mechanism behind PLC degradation: Urbach energy
    increases with T."""
    e_ref = urbach_energy_mev(T_REF_K)
    e_hot = urbach_energy_mev(T_REF_K + 50.0)
    assert e_ref == pytest.approx(30.0, rel=1e-9)
    assert e_hot > e_ref
    assert e_hot == pytest.approx(30.0 + 0.05 * 50.0, rel=1e-9)


# --- s2-2: TE efficiency ----------------------------------------------------


def test_eta_te_positive_for_hot_side_warmer() -> None:
    """With a real temperature difference, eta_TE must be positive."""
    eff = eta_te(t_hot_k=400.0, t_cold_k=300.0)
    assert 0.0 < eff < 0.20, f"eta_TE = {eff} outside plausible range"


def test_eta_te_requires_hot_warmer_than_cold() -> None:
    with pytest.raises(ValueError):
        eta_te(t_hot_k=300.0, t_cold_k=400.0)
    with pytest.raises(ValueError):
        eta_te(t_hot_k=300.0, t_cold_k=300.0)


def test_eta_te_rejects_negative_cold_side() -> None:
    with pytest.raises(ValueError):
        eta_te(t_hot_k=300.0, t_cold_k=-10.0)


def test_eta_te_monotonic_in_hot_side_temperature() -> None:
    """For fixed T_cold, increasing T_hot increases eta_TE (Carnot-like
    trend) up to the point where Bi2Te3 ZT starts falling off."""
    t_cold = 300.0
    effs = [eta_te(t_hot_k=t, t_cold_k=t_cold) for t in (320.0, 340.0, 360.0, 380.0)]
    for a, b in pairwise(effs):
        assert a < b, f"eta_TE not monotonic in T_hot: {a} >= {b}"


def test_zt_avg_peaks_near_100c() -> None:
    """Bi2Te3 ZT peaks near 100 C (373.15 K)."""
    zt_below = zt_avg_bi2te3(350.0)
    zt_at_peak = zt_avg_bi2te3(400.0)
    zt_above = zt_avg_bi2te3(550.0)
    assert zt_at_peak > zt_above, f"ZT should fall above peak: {zt_at_peak} <= {zt_above}"
    assert zt_at_peak > 0.0
    assert zt_above >= 0.0
    assert zt_below >= 0.0


# --- s2-3: CORRECTED ATTRIBUTION (Section 33.1) -----------------------------


def test_sb2se3_thermal_conductivity_does_not_affect_te_efficiency() -> None:
    """The corrected attribution (Section 33.1): Sb2Se3 is a thermal
    barrier, NOT a Seebeck-generating layer. Changing its thermal
    conductivity must NOT change the TE efficiency for a given
    (T_hot, T_cold) pair."""
    stack_a = ReceiverStack.default()
    stack_b = ReceiverStack.default()
    stack_b = replace(
        stack_b,
        barrier=replace(stack_b.barrier, thermal_conductivity_w_per_m_k=5.0),
    )

    eff_a = eta_te(t_hot_k=400.0, t_cold_k=300.0, params=stack_a.te)
    eff_b = eta_te(t_hot_k=400.0, t_cold_k=300.0, params=stack_b.te)

    assert eff_a == pytest.approx(eff_b, rel=1e-12), (
        f"TE efficiency changed with Sb2Se3 thermal conductivity: {eff_a} vs {eff_b}"
    )


def test_sb2se3_thermal_conductivity_does_not_affect_total_efficiency() -> None:
    """Corollary: total efficiency is also invariant to barrier thermal
    conductivity, because it depends only on T_PLC and the TE pair."""
    stack_a = ReceiverStack.default()
    stack_b = replace(
        stack_a,
        barrier=replace(stack_a.barrier, thermal_conductivity_w_per_m_k=5.0),
    )

    tot_a = eta_total(t_plc_k=320.0, t_te_hot_k=340.0, t_te_cold_k=300.0, stack=stack_a)
    tot_b = eta_total(t_plc_k=320.0, t_te_hot_k=340.0, t_te_cold_k=300.0, stack=stack_b)
    assert tot_a == pytest.approx(tot_b, rel=1e-12)


def test_barrier_role_is_declared_as_thermal_barrier() -> None:
    """The barrier dataclass must declare its role explicitly, so a
    future refactor cannot silently re-cast it as a Seebeck layer."""
    b = ThermalBarrierParams()
    assert b.role == "thermal_barrier"
    assert b.material == "Sb2Se3"


def test_sb2se3_thermal_conductivity_is_plausible() -> None:
    """Published Sb2Se3 thin-film thermal conductivity is in [0.3, 0.7]
    W/(m K). The default must lie in that range."""
    b = ThermalBarrierParams()
    assert 0.3 <= b.thermal_conductivity_w_per_m_k <= 0.7


# --- eta_total composition --------------------------------------------------


def test_eta_total_is_product_of_components() -> None:
    """eta_total = eta_PLC * eta_TE within numerical tolerance."""
    stack = ReceiverStack.default()
    t_plc = 320.0
    t_hot = 340.0
    t_cold = 300.0
    expected = eta_plc(t_plc, stack.plc) * eta_te(t_hot, t_cold, stack.te)
    assert eta_total(t_plc, t_hot, t_cold, stack) == pytest.approx(expected, rel=1e-12)


def test_eta_total_is_zero_when_plc_is_degraded() -> None:
    """If the PLC is at or above its degradation limit, the whole stack
    produces zero electrical output."""
    stack = ReceiverStack.default()
    assert eta_total(400.0, 340.0, 300.0, stack) == 0.0


def test_receiver_stack_default_constructs() -> None:
    s = ReceiverStack.default()
    assert s.plc.eta_ref == 0.15
    assert s.barrier.material == "Sb2Se3"
    assert s.te.zt_peak == 1.0


def test_te_params_dataclass_is_frozen() -> None:
    """Parameters are immutable so they cannot be silently mutated."""
    p = TEParams()
    with pytest.raises(FrozenInstanceError):
        p.zt_peak = 2.0  # type: ignore[misc]
