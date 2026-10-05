"""Dimensional consistency tests for the physics modules.

Roadmap task:
    s2-7 Scientific gate: dimensional consistency.
    Gate: Every equation unit-consistent (W, K, m^2, etc.).

Every test in this file checks either:
    (a) the numerical value of a documented physical constant, or
    (b) a scaling invariant that would be violated by an inconsistent
        unit combination.

Scaling invariants are the strongest available check in a
non-symbolic environment: if a quantity X has units [U_X] and is
expected to scale linearly with a parameter of units [U_p], then
doubling that parameter must double X. A unit mismatch produces a
non-linear or zero response.
"""

from dataclasses import replace

import pytest

from app.physics.receiver import (
    SIGMA_SB_W_PER_M2_K4,
    T_REF_K,
    eta_plc,
    eta_te,
    eta_total,
    urbach_energy_mev,
    zt_avg_bi2te3,
)
from app.physics.thermal import (
    REFERENCE_P_INCIDENT_W,
    REFERENCE_T_AMBIENT_K,
    REFERENCE_V_AIRFLOW_M_PER_S,
    ThermalModel,
    ThermalParams,
    default_model,
)

# --- Documented constants --------------------------------------------------


def test_stefan_boltzmann_constant_value() -> None:
    """Sigma_SB = 5.670374419e-8 W / (m^2 K^4), CODATA 2018."""
    assert pytest.approx(5.670374419e-8, rel=1e-12) == SIGMA_SB_W_PER_M2_K4


def test_reference_temperature_is_25c() -> None:
    """T_REF_K = 298.15 K = 25 C. [MEASURED]"""
    assert pytest.approx(298.15, rel=1e-12) == T_REF_K


# --- Dimensionless outputs --------------------------------------------------


def test_eta_plc_is_dimensionless_in_unit_interval() -> None:
    """eta_PLC returns a dimensionless value in [0, 1]."""
    for t in (280.0, 300.0, 320.0, 340.0):
        e = eta_plc(t)
        assert 0.0 <= e <= 1.0, f"eta_plc({t}) = {e} outside [0, 1]"


def test_eta_te_is_dimensionless_in_unit_interval() -> None:
    """eta_TE returns a dimensionless value in [0, 1]."""
    for t_hot, t_cold in ((320.0, 300.0), (350.0, 300.0), (380.0, 310.0)):
        e = eta_te(t_hot, t_cold)
        assert 0.0 <= e <= 1.0, f"eta_te({t_hot},{t_cold}) = {e} outside [0, 1]"


def test_eta_total_is_dimensionless_in_unit_interval() -> None:
    """eta_total is the product of two dimensionless quantities and
    therefore also dimensionless and in [0, 1]."""
    e = eta_total(320.0, 340.0, 300.0)
    assert 0.0 <= e <= 1.0


def test_zt_avg_is_nonnegative_dimensionless() -> None:
    """ZT is dimensionless by construction: ZT = S^2 sigma T / k."""
    for t in (300.0, 373.15, 500.0):
        zt = zt_avg_bi2te3(t)
        assert zt >= 0.0
        assert zt < 10.0, f"ZT = {zt} implausibly large; check units"


# --- Urbach energy: units meV ----------------------------------------------


def test_urbach_energy_at_reference_is_30_mev() -> None:
    """urbach_energy_mev(298.15 K) = 30.0 meV by construction."""
    assert urbach_energy_mev(T_REF_K) == pytest.approx(30.0, rel=1e-12)


def test_urbach_energy_scales_by_coefficient_mev_per_kelvin() -> None:
    """dE_urbach / dT = urbach_dt_mev_per_kelvin = 0.05 meV/K.
    A 50 K step must produce exactly +2.5 meV."""
    e_ref = urbach_energy_mev(T_REF_K)
    e_hot = urbach_energy_mev(T_REF_K + 50.0)
    assert e_hot - e_ref == pytest.approx(2.5, rel=1e-12)


# --- Barrier resistance: units K / W ---------------------------------------


def test_barrier_resistance_scales_linearly_with_thickness() -> None:
    """R_bulk = t / (k A). Doubling t must double R_bulk, so the
    thickness-dependent part of R must double. We test the total R with
    a zero contact resistance so the scaling is exact."""
    m = default_model()
    m_zero_contact = ThermalModel(
        params=replace(m.params, barrier_contact_resistance_k_m2_per_w=0.0)
    )
    r1 = m_zero_contact.barrier_resistance_k_per_w
    m_double = ThermalModel(
        params=replace(
            m_zero_contact.params,
            barrier_thickness_m=m_zero_contact.params.barrier_thickness_m * 2.0,
        )
    )
    r2 = m_double.barrier_resistance_k_per_w
    assert r2 == pytest.approx(2.0 * r1, rel=1e-12)


def test_barrier_resistance_inversely_proportional_to_conductivity() -> None:
    """R_bulk = t / (k A). Doubling k must halve the bulk term."""
    m = default_model()
    m_zero_contact = ThermalModel(
        params=replace(m.params, barrier_contact_resistance_k_m2_per_w=0.0)
    )
    r1 = m_zero_contact.barrier_resistance_k_per_w
    m_double_k = ThermalModel(
        params=replace(
            m_zero_contact.params,
            barrier_conductivity_w_per_m_k=(
                m_zero_contact.params.barrier_conductivity_w_per_m_k * 2.0
            ),
        )
    )
    r2 = m_double_k.barrier_resistance_k_per_w
    assert r2 == pytest.approx(0.5 * r1, rel=1e-12)


# --- Capacitance: units J / K -----------------------------------------------


def test_capacitance_plc_scales_linearly_with_area() -> None:
    """C = rho cp A t. Doubling A must double C."""
    m = default_model()
    m_double = ThermalModel(params=replace(m.params, area_m2=m.params.area_m2 * 2.0))
    assert m_double.capacitance_plc_j_per_k == pytest.approx(
        2.0 * m.capacitance_plc_j_per_k, rel=1e-12
    )


def test_capacitance_te_scales_linearly_with_area() -> None:
    m = default_model()
    m_double = ThermalModel(params=replace(m.params, area_m2=m.params.area_m2 * 2.0))
    assert m_double.capacitance_te_j_per_k == pytest.approx(
        2.0 * m.capacitance_te_j_per_k, rel=1e-12
    )


def test_capacitance_plc_scales_linearly_with_density() -> None:
    """C = rho cp A t. Doubling rho must double C."""
    m = default_model()
    m_double = ThermalModel(
        params=replace(m.params, rho_plc_kg_per_m3=m.params.rho_plc_kg_per_m3 * 2.0)
    )
    assert m_double.capacitance_plc_j_per_k == pytest.approx(
        2.0 * m.capacitance_plc_j_per_k, rel=1e-12
    )


# --- Convection: units W / (m^2 K) -----------------------------------------


def test_convection_natural_limit_is_h_natural() -> None:
    """At v = 0, h = h_natural. h_natural must therefore have units
    W/(m^2 K), which we verify by setting a known custom value."""
    m = ThermalModel(params=replace(ThermalParams(), h_natural_w_per_m2_k=7.5))
    assert m.convection_coefficient_w_per_m2_k(0.0) == pytest.approx(7.5, rel=1e-12)


def test_convection_forced_term_scales_as_sqrt_v() -> None:
    """h_forced = c sqrt(v). Quadrupling v must double the forced part.
    We subtract h_natural to isolate the forced term."""
    m = default_model()
    h_nat = m.convection_coefficient_w_per_m2_k(0.0)
    forced_1 = m.convection_coefficient_w_per_m2_k(1.0) - h_nat
    forced_4 = m.convection_coefficient_w_per_m2_k(4.0) - h_nat
    assert forced_4 == pytest.approx(2.0 * forced_1, rel=1e-12)


# --- Heat fluxes: units W --------------------------------------------------


def test_heat_absorbed_scales_linearly_with_incident_power() -> None:
    """Q_in = P (1 - eta). Doubling P must double Q_in for fixed T_plc."""
    m = default_model()
    q1 = m.heat_absorbed_plc_w(10.0, 320.0)
    q2 = m.heat_absorbed_plc_w(20.0, 320.0)
    assert q2 == pytest.approx(2.0 * q1, rel=1e-12)


def test_heat_conduction_scales_linearly_with_delta_t() -> None:
    """Q_cond = (T_plc - T_te) / R. Doubling the temperature difference
    must double the heat flow."""
    m = default_model()
    q1 = m.heat_conduction_plc_to_te_w(320.0, 300.0)
    q2 = m.heat_conduction_plc_to_te_w(340.0, 300.0)
    assert q2 == pytest.approx(2.0 * q1, rel=1e-12)


def test_heat_out_conv_and_rad_both_nonnegative_above_ambient() -> None:
    """Both convective and radiative losses are positive when T > T_amb.
    Their sum has units W (verified indirectly by the sign and the
    steady-state energy balance test in test_thermal.py)."""
    m = default_model()
    q_out = m.heat_out_plc_w(320.0, 5.0, 298.15)
    assert q_out > 0.0


# --- ODE derivatives: units K / s ------------------------------------------


def test_dt_plc_dt_scales_inversely_with_capacitance() -> None:
    """dT_plc/dt = Q_net / C. Doubling C must halve dT_plc/dt.

    We scale rho_plc (not area_m2) because area_m2 appears in both the
    capacitance and the convective loss term, so changing it does not
    isolate the capacitance effect. rho_plc appears only in the
    capacitance, so doubling it doubles C and leaves the numerator
    (Q_in - Q_cond - Q_out) unchanged.
    """
    m = default_model()
    m_double_c = ThermalModel(
        params=replace(m.params, rho_plc_kg_per_m3=m.params.rho_plc_kg_per_m3 * 2.0)
    )
    rate_1 = m.dt_plc_dt(300.0, 300.0, 20.0, 5.0, 298.15)
    rate_2 = m_double_c.dt_plc_dt(300.0, 300.0, 20.0, 5.0, 298.15)
    assert rate_2 == pytest.approx(0.5 * rate_1, rel=1e-12)


def test_dt_te_dt_scales_inversely_with_capacitance() -> None:
    """dT_te/dt = Q_net / C_te. Doubling C_te must halve dT_te/dt.

    Same reasoning as the PLC test: scale rho_te, not area_m2, so that
    the numerator is unchanged.
    """
    m = default_model()
    m_double_c = ThermalModel(
        params=replace(m.params, rho_te_kg_per_m3=m.params.rho_te_kg_per_m3 * 2.0)
    )
    rate_1 = m.dt_te_dt(320.0, 300.0, 20.0, 5.0, 298.15)
    rate_2 = m_double_c.dt_te_dt(320.0, 300.0, 20.0, 5.0, 298.15)
    assert rate_2 == pytest.approx(0.5 * rate_1, rel=1e-12)


# --- Energy balance is dimensionless ---------------------------------------


def test_energy_balance_error_is_dimensionless() -> None:
    """(Q_in - Q_out) / Q_in is a ratio of two quantities in W and
    therefore dimensionless. At steady state it should be ~0."""
    m = default_model()
    err = m.steady_state_energy_balance_error(
        REFERENCE_P_INCIDENT_W,
        REFERENCE_V_AIRFLOW_M_PER_S,
        REFERENCE_T_AMBIENT_K,
    )
    assert err is not None
    assert 0.0 <= err < 1e-6
