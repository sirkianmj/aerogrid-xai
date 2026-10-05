"""Unit tests for the two-node lumped thermal model.

Roadmap tasks:
    s2-4 Two-node lumped thermal model (dT_PLC/dt, dT_TE/dt)
        Gate: Energy balance closes; steady state matches 80-90 C.
    s2-5 Thermal runaway boundary P_max(T_amb, v)
        Gate: Validated against Han et al. degradation regime.
"""

from dataclasses import replace

import pytest

from app.physics.receiver import PLCParams, ReceiverStack, ThermalBarrierParams
from app.physics.thermal import (
    REFERENCE_P_INCIDENT_W,
    REFERENCE_T_AMBIENT_K,
    REFERENCE_V_AIRFLOW_M_PER_S,
    ThermalModel,
    ThermalParams,
    default_model,
)

# --- s2-4: Capacitances and conductances ------------------------------------


def test_capacitance_plc_is_positive_and_plausible() -> None:
    m = default_model()
    c = m.capacitance_plc_j_per_k
    assert c > 0.0
    # rho=4500 * cp=300 * A=0.01 * t=5e-7 = 6.75e-3 J/K
    assert 1e-4 < c < 1e-1, f"PLC capacitance {c} J/K outside plausible range"


def test_capacitance_te_is_positive_and_plausible() -> None:
    m = default_model()
    c = m.capacitance_te_j_per_k
    # rho=7700 * cp=155 * A=0.01 * t=1e-6 = 1.19e-2 J/K
    assert c > 0.0
    assert 1e-4 < c < 1e-1, f"TE capacitance {c} J/K outside plausible range"


def test_barrier_resistance_is_positive() -> None:
    m = default_model()
    r = m.barrier_resistance_k_per_w
    assert r > 0.0
    # Expected order: ~10-100 K/W
    assert 1.0 < r < 500.0, f"Barrier resistance {r} K/W outside plausible range"


def test_barrier_resistance_zero_area_raises() -> None:
    bad_params = replace(ThermalParams(), barrier_effective_area_fraction=0.0)
    m = ThermalModel(params=bad_params)
    with pytest.raises(ValueError):
        _ = m.barrier_resistance_k_per_w


# --- Convection -------------------------------------------------------------


def test_convection_coefficient_increases_with_airflow() -> None:
    m = default_model()
    h0 = m.convection_coefficient_w_per_m2_k(0.0)
    h5 = m.convection_coefficient_w_per_m2_k(5.0)
    h20 = m.convection_coefficient_w_per_m2_k(20.0)
    assert h0 < h5 < h20
    assert h0 == pytest.approx(5.0, rel=1e-9)
    assert h5 == pytest.approx(5.0 + 6.0 * 5**0.5, rel=1e-9)


def test_convection_coefficient_rejects_negative_airflow() -> None:
    m = default_model()
    with pytest.raises(ValueError):
        m.convection_coefficient_w_per_m2_k(-1.0)


# --- ODE signs and magnitudes ----------------------------------------------


def test_dt_plc_dt_positive_when_hot_input_cold_node() -> None:
    """At t=0 with cold nodes and high input power, the PLC heats up."""
    m = default_model()
    rate = m.dt_plc_dt(
        t_plc_k=REFERENCE_T_AMBIENT_K,
        t_te_k=REFERENCE_T_AMBIENT_K,
        p_incident_w=REFERENCE_P_INCIDENT_W,
        v_m_per_s=REFERENCE_V_AIRFLOW_M_PER_S,
        t_amb_k=REFERENCE_T_AMBIENT_K,
    )
    assert rate > 0.0


def test_dt_plc_dt_negative_at_very_high_temperature() -> None:
    """If the PLC is above ambient and no power is coming in, it cools."""
    m = default_model()
    rate = m.dt_plc_dt(
        t_plc_k=REFERENCE_T_AMBIENT_K + 100.0,
        t_te_k=REFERENCE_T_AMBIENT_K + 50.0,
        p_incident_w=0.0,
        v_m_per_s=REFERENCE_V_AIRFLOW_M_PER_S,
        t_amb_k=REFERENCE_T_AMBIENT_K,
    )
    assert rate < 0.0


def test_heat_absorbed_plc_rejects_negative_power() -> None:
    m = default_model()
    with pytest.raises(ValueError):
        m.heat_absorbed_plc_w(-1.0, REFERENCE_T_AMBIENT_K)


# --- s2-4: Steady state and energy balance ----------------------------------


def test_steady_state_exists_at_reference_conditions() -> None:
    m = default_model()
    ss = m.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss is not None


def test_steady_state_t_te_is_below_t_plc() -> None:
    """Heat flows PLC -> TE only if T_plc > T_te."""
    m = default_model()
    ss = m.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss is not None
    t_plc, t_te = ss
    assert t_te < t_plc


def test_steady_state_energy_balance_closes() -> None:
    """At steady state, heat in equals heat out at the PLC node within
    a tight relative tolerance."""
    m = default_model()
    err = m.steady_state_energy_balance_error(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert err is not None
    assert err < 1e-6, f"Energy balance error {err:.2e} exceeds 1e-6"


def test_steady_state_reaches_han_degradation_regime() -> None:
    """Section 33.4 gate: at reference conditions the model must produce
    a PLC temperature in the 80-90 C range observed by Han et al."""
    m = default_model()
    ss = m.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss is not None
    t_plc_k, _ = ss
    t_plc_c = t_plc_k - 273.15
    assert 80.0 <= t_plc_c <= 90.0, f"T_plc = {t_plc_c:.2f} C outside the 80-90 C Han regime"


def test_steady_state_rejects_negative_power() -> None:
    m = default_model()
    with pytest.raises(ValueError):
        m.steady_state(-1.0, 5.0, 288.15)


def test_steady_state_rejects_zero_ambient() -> None:
    m = default_model()
    with pytest.raises(ValueError):
        m.steady_state(10.0, 5.0, 0.0)


# --- s2-3 continued: Sb2Se3 attribution in the thermal model ---------------


def test_sb2se3_conductivity_affects_thermal_gradient() -> None:
    """Corrected attribution (Section 33.1): changing the Sb2Se3 thermal
    conductivity changes the R_barrier, which changes the steady-state
    thermal gradient between the PLC and TE nodes."""
    default = default_model()
    low_k_barrier = ThermalModel(
        receiver=default.receiver,
        params=replace(
            default.params,
            barrier_conductivity_w_per_m_k=0.2,
        ),
    )
    high_k_barrier = ThermalModel(
        receiver=default.receiver,
        params=replace(
            default.params,
            barrier_conductivity_w_per_m_k=2.0,
        ),
    )

    ss_low = low_k_barrier.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    ss_high = high_k_barrier.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss_low is not None and ss_high is not None

    grad_low = ss_low[0] - ss_low[1]
    grad_high = ss_high[0] - ss_high[1]
    assert grad_low > grad_high, (
        f"Lower barrier k should give larger PLC-TE gradient: "
        f"low k gradient = {grad_low:.2f} K, high k gradient = {grad_high:.2f} K"
    )


def test_thermal_gradient_with_very_high_conductivity_tends_to_zero() -> None:
    """As k_barrier -> infinity, the barrier approaches a perfect thermal
    conductor and T_plc -> T_te."""
    default = default_model()
    perfect = ThermalModel(
        receiver=default.receiver,
        params=replace(
            default.params,
            barrier_conductivity_w_per_m_k=1e6,
            barrier_contact_resistance_k_m2_per_w=0.0,
        ),
    )
    ss = perfect.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss is not None
    t_plc, t_te = ss
    assert abs(t_plc - t_te) < 1.0, f"Gradient {t_plc - t_te:.3f} K not near zero"


# --- s2-5: Thermal runaway boundary -----------------------------------------


def test_thermal_runaway_boundary_is_positive_and_plausible() -> None:
    """At reference airflow and ambient, P_max must exist and be positive."""
    m = default_model()
    p_max = m.thermal_runaway_boundary(REFERENCE_V_AIRFLOW_M_PER_S, REFERENCE_T_AMBIENT_K)
    assert p_max > 0.0
    # Expected: tens of watts (reference is 20 W, which gives 80-90 C).
    assert 5.0 < p_max < 500.0, f"P_max = {p_max:.1f} W outside plausible range"


def test_thermal_runaway_boundary_increases_with_airflow() -> None:
    """Better cooling (higher v) raises the threshold."""
    m = default_model()
    p_low_v = m.thermal_runaway_boundary(1.0, REFERENCE_T_AMBIENT_K)
    p_high_v = m.thermal_runaway_boundary(20.0, REFERENCE_T_AMBIENT_K)
    assert p_high_v > p_low_v, (
        f"P_max should increase with airflow: v=1 -> {p_low_v:.1f} W, v=20 -> {p_high_v:.1f} W"
    )


def test_thermal_runaway_boundary_at_p_max_t_plc_is_below_limit() -> None:
    """At P_max, the steady-state PLC temperature is below the material
    degradation limit and close to it. Above P_max, the model must not
    produce a safe steady state.

    Because eta_plc is clamped to zero at t_max_kelvin, the steady-state
    map T_plc(P) is discontinuous at P_max: the lower-branch equilibrium
    terminates a small distance below t_max_kelvin and does not reach it
    exactly. We therefore assert T_plc(P_max) < t_max with a margin that
    reflects the size of this discontinuity, and separately assert that
    just above P_max no safe steady state exists.
    """
    m = default_model()
    v = REFERENCE_V_AIRFLOW_M_PER_S
    t_amb = REFERENCE_T_AMBIENT_K
    t_max = m.receiver.plc.t_max_kelvin

    p_max = m.thermal_runaway_boundary(v, t_amb)
    ss = m.steady_state(p_max, v, t_amb)
    assert ss is not None
    assert ss[0] < t_max, f"T_plc at P_max = {ss[0]:.3f} K must be below t_max = {t_max:.3f} K"
    assert t_max - ss[0] < 3.0, (
        f"T_plc at P_max = {ss[0]:.3f} K is more than 3 K below t_max = {t_max:.3f} K"
    )

    ss_above = m.steady_state(p_max * 1.01, v, t_amb)
    assert ss_above is None or ss_above[0] >= t_max, (
        f"A safe steady state was found at 1.01 * P_max: {ss_above}"
    )


def test_steady_state_well_above_p_max_exceeds_degradation_limit() -> None:
    """Far above P_max, the model still produces a hypothetical equilibrium
    (because eta_plc = 0 above t_max, so all incident power becomes heat,
    and the PLC/ambient system still has a fixed point inside the 1000 K
    bound enforced by steady_state). This test asserts that the equilibrium
    is above the material degradation limit, i.e. that the receiver is
    outside its safe operating regime. It does NOT assert that no
    equilibrium exists, because the model as documented does not enforce
    that."""
    m = default_model()
    p_max = m.thermal_runaway_boundary(REFERENCE_V_AIRFLOW_M_PER_S, REFERENCE_T_AMBIENT_K)
    ss = m.steady_state(p_max * 10.0, REFERENCE_V_AIRFLOW_M_PER_S, REFERENCE_T_AMBIENT_K)
    assert ss is not None, "Model should still produce an equilibrium above P_max"
    t_max = m.receiver.plc.t_max_kelvin
    assert ss[0] > t_max, f"T_plc {ss[0]:.3f} K should exceed t_max {t_max:.3f} K above P_max"


def test_thermal_runaway_boundary_is_lower_at_higher_ambient() -> None:
    """Hotter ambient reduces the margin and lowers P_max."""
    m = default_model()
    p_cool = m.thermal_runaway_boundary(REFERENCE_V_AIRFLOW_M_PER_S, REFERENCE_T_AMBIENT_K)
    p_hot = m.thermal_runaway_boundary(REFERENCE_V_AIRFLOW_M_PER_S, REFERENCE_T_AMBIENT_K + 20.0)
    assert p_hot < p_cool


# --- Simulate ----------------------------------------------------------------


def test_simulate_converges_toward_steady_state() -> None:
    """Starting from ambient and integrating for a long time should give
    temperatures close to the steady-state values."""
    m = default_model()
    ss = m.steady_state(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert ss is not None

    final = m.simulate(
        p_incident_w=REFERENCE_P_INCIDENT_W,
        v_m_per_s=REFERENCE_V_AIRFLOW_M_PER_S,
        t_amb_k=REFERENCE_T_AMBIENT_K,
        t_plc_initial_k=REFERENCE_T_AMBIENT_K,
        t_te_initial_k=REFERENCE_T_AMBIENT_K,
        t_end_s=60.0,
        n_samples=500,
    )
    assert abs(final.t_plc_k - ss[0]) < 1.0, (
        f"Simulated T_plc {final.t_plc_k:.2f} K did not converge to steady state {ss[0]:.2f} K"
    )
    assert abs(final.t_te_k - ss[1]) < 1.0


def test_simulate_rejects_zero_duration() -> None:
    m = default_model()
    with pytest.raises(ValueError):
        m.simulate(10.0, 5.0, 288.15, 288.15, 288.15, 0.0)


# --- Dimensional consistency (foundation for s2-7) -------------------------


def test_barrier_resistance_dimension() -> None:
    """R = t / (k * A) has units of K/W.
    t in m, k in W/(m K), A in m^2. So t/(k*A) = m / (W/(m K) * m^2)
    = m / (W m / K) = K / W. Correct.
    """
    m = default_model()
    r = m.barrier_resistance_k_per_w
    assert r > 0.0
    # Sanity: doubling thickness doubles resistance
    doubled = ThermalModel(
        params=replace(
            m.params,
            barrier_thickness_m=m.params.barrier_thickness_m * 2.0,
        )
    )
    assert doubled.barrier_resistance_k_per_w > r


def test_capacitance_scales_with_area() -> None:
    m = default_model()
    doubled = ThermalModel(params=replace(m.params, area_m2=m.params.area_m2 * 2.0))
    assert doubled.capacitance_plc_j_per_k == pytest.approx(
        2.0 * m.capacitance_plc_j_per_k, rel=1e-9
    )


# --- PLCHBarrier defaults sanity -------------------------------------------


def test_receiver_stack_default_matches_defaults() -> None:
    s = ReceiverStack.default()
    assert isinstance(s.plc, PLCParams)
    assert isinstance(s.barrier, ThermalBarrierParams)
    assert s.barrier.material == "Sb2Se3"
    assert s.barrier.role == "thermal_barrier"
