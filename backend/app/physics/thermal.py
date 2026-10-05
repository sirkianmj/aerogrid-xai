"""Stage A - Two-node lumped thermal model.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6), Sections
    33.3 and 33.4.

Two thermal nodes are modeled:

    Node 1 - the CsPbBr3 PLC (perovskite laser cell)
        Absorbs the unconverted fraction of the incident laser power as
        heat. Loses heat to the ambient via convection and radiation,
        and conducts heat to the TE node through the Sb2Se3 barrier.

    Node 2 - the Bi2Te3 TE (thermoelectric layer)
        Receives heat by conduction from the PLC through the barrier.
        Converts a fraction (eta_TE) to electricity and dissipates the
        remainder to the ambient.

Corrected attribution (Section 33.1): the Sb2Se3 layer appears in the
CONDUCTION term between node 1 and node 2 (via ``barrier_resistance_k_per_w``).
It does NOT appear in the TE efficiency (see app.physics.receiver).

Radiative loss (Stefan-Boltzmann) is included for completeness. At the
temperatures and airspeeds of interest, radiation is typically a small
fraction of convective cooling, but its inclusion is required by the
specification and its magnitude is asserted in the tests.

Epistemic tags (Section 21):
    [MEASURED]   physical constant
    [VALIDATED]  published/peer-reviewed value
    [ESTIMATED]  engineering first-principles estimate, not measured
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import root

from app.physics.receiver import (
    SIGMA_SB_W_PER_M2_K4,
    ReceiverStack,
    eta_plc,
    eta_te,
)

# --- Parameters ------------------------------------------------------------


@dataclass(frozen=True)
class ThermalParams:
    """Lumped thermal parameters for the receiver stack.

    All values carry a Section 21 epistemic tag in the docstring. All
    units are SI (m, K, W, J, kg, s).
    """

    area_m2: float = 0.01
    """[ESTIMATED] 100 cm^2 receiver aperture, typical small-UAV."""
    thickness_plc_m: float = 5e-7
    """[ESTIMATED] 500 nm CsPbBr3 film."""
    thickness_te_m: float = 1e-6
    """[ESTIMATED] 1 um Bi2Te3 film."""
    rho_plc_kg_per_m3: float = 4500.0
    """[VALIDATED] CsPbBr3 density ~ 4.5 g/cm^3."""
    rho_te_kg_per_m3: float = 7700.0
    """[VALIDATED] Bi2Te3 density ~ 7.7 g/cm^3."""
    cp_plc_j_per_kg_k: float = 300.0
    """[ESTIMATED] CsPbBr3 specific heat ~ 0.3 J/(g K)."""
    cp_te_j_per_kg_k: float = 155.0
    """[VALIDATED] Bi2Te3 specific heat at 300 K ~ 0.155 J/(g K)."""

    barrier_thickness_m: float = 1e-3
    """[ESTIMATED] Effective composite thickness of the Sb2Se3 barrier
    and its interfaces."""
    barrier_conductivity_w_per_m_k: float = 0.5
    """[VALIDATED] Sb2Se3 thin-film thermal conductivity, 0.3-0.7
    W/(m K) published range, 0.5 midpoint."""
    barrier_effective_area_fraction: float = 0.02
    """[ESTIMATED] Fraction of the receiver area over which the barrier
    carries heat. The spec describes Sb2Se3 as nanocrystals embedded at
    the top interface, which implies a finite contact area rather than a
    full-coverage film."""
    barrier_contact_resistance_k_m2_per_w: float = 1e-3
    """[ESTIMATED] Thermal interface contact resistance, a typical value
    for a solid-solid interface with no thermal paste."""

    h_natural_w_per_m2_k: float = 5.0
    """[VALIDATED] Natural convection coefficient for a small flat plate
    in air, 3-8 W/(m^2 K) range, 5 midpoint."""
    c_forced_w_per_m2_k_per_sqrt_m_per_s: float = 6.0
    """[ESTIMATED] Coefficient for the forced-convection enhancement
    term h_forced = c * sqrt(v). At v = 5 m/s this gives
    h(5) = 5 + 6*sqrt(5) ~ 18.4 W/(m^2 K), consistent with a small UAV
    airframe in cruise. The value is a calibration choice: published
    forced-convection correlations for small flat plates in air at 5 m/s
    span roughly 16-28 W/(m^2 K), so 18.4 is inside the plausible band.
    A published correlation should be cited here before any commercial
    deployment; the current value is marked [ESTIMATED] for that reason."""

    emissivity: float = 0.9
    """[ESTIMATED] Broadband infrared emissivity of a coated perovskite
    surface, 0.8-0.95 range, 0.9 midpoint."""


# --- Reference conditions (used in tests and notebooks) --------------------

REFERENCE_P_INCIDENT_W = 20.0
REFERENCE_V_AIRFLOW_M_PER_S = 5.0
REFERENCE_T_AMBIENT_K = 298.15
"""Reference conditions for the Han et al. degradation regime check:
20 W incident on a 100 cm^2 receiver (0.2 W/cm^2) with 5 m/s airflow at
25 C (standard laboratory ambient). At these conditions the model must
reproduce a T_PLC in the 80-90 C range reported by Han et al. The
choice of 25 C rather than 15 C reflects the standard lab ambient under
which the Han measurements were taken; the model parameters themselves
are not adjusted to force agreement."""


# --- Model -----------------------------------------------------------------


@dataclass(frozen=True)
class ThermalSnapshot:
    """A state of the two-node model at a point in time."""

    time_s: float
    t_plc_k: float
    t_te_k: float

    @property
    def t_plc_c(self) -> float:
        return self.t_plc_k - 273.15

    @property
    def t_te_c(self) -> float:
        return self.t_te_k - 273.15


class ThermalModel:
    """Two-node lumped thermal model of the receiver stack.

    Node 1 - the PLC.
    Node 2 - the TE layer.
    The Sb2Se3 barrier sits between them.
    """

    def __init__(
        self,
        receiver: ReceiverStack | None = None,
        params: ThermalParams | None = None,
    ) -> None:
        self.receiver = receiver or ReceiverStack.default()
        self.params = params or ThermalParams()

    # --- Geometry and derived parameters -----------------------------------

    @property
    def capacitance_plc_j_per_k(self) -> float:
        """Thermal capacitance of the PLC node, J/K.

        C = rho * cp * A * t
        """
        p = self.params
        return p.rho_plc_kg_per_m3 * p.cp_plc_j_per_kg_k * p.area_m2 * p.thickness_plc_m

    @property
    def capacitance_te_j_per_k(self) -> float:
        """Thermal capacitance of the TE node, J/K."""
        p = self.params
        return p.rho_te_kg_per_m3 * p.cp_te_j_per_kg_k * p.area_m2 * p.thickness_te_m

    @property
    def barrier_resistance_k_per_w(self) -> float:
        """Effective lumped thermal resistance between PLC and TE, K/W.

        Combines bulk conduction through the Sb2Se3 barrier and contact
        resistance at the interfaces, over the effective contact area:

            R = t_b / (k_b * A_eff) + R_contact / A_eff

        This is the term that carries the Sb2Se3 layer's thermal role
        (Section 33.1). It does NOT appear in eta_te.
        """
        p = self.params
        a_eff = p.area_m2 * p.barrier_effective_area_fraction
        if a_eff <= 0.0:
            raise ValueError(f"Barrier effective area must be positive; got {a_eff}")
        r_bulk = p.barrier_thickness_m / (p.barrier_conductivity_w_per_m_k * a_eff)
        r_contact = p.barrier_contact_resistance_k_m2_per_w / a_eff
        return r_bulk + r_contact

    # --- Convection --------------------------------------------------------

    def convection_coefficient_w_per_m2_k(self, v_m_per_s: float) -> float:
        """Convection coefficient as a function of airflow speed.

        h(v) = h_natural + c_forced * sqrt(v)

        Negative v raises an error; zero v reduces to natural convection.
        """
        if v_m_per_s < 0.0:
            raise ValueError(f"Airflow speed must be >= 0; got {v_m_per_s}")
        p = self.params
        return p.h_natural_w_per_m2_k + p.c_forced_w_per_m2_k_per_sqrt_m_per_s * math.sqrt(
            v_m_per_s
        )

    # --- Heat fluxes -------------------------------------------------------

    def heat_absorbed_plc_w(self, p_incident_w: float, t_plc_k: float) -> float:
        """Heat deposited at the PLC node, W.

        The fraction of the incident power not converted to electricity
        becomes heat:

            Q_in_plc = P_incident * (1 - eta_PLC(T_plc))
        """
        if p_incident_w < 0.0:
            raise ValueError(f"Incident power must be >= 0; got {p_incident_w}")
        eta = eta_plc(t_plc_k, self.receiver.plc)
        return p_incident_w * (1.0 - eta)

    def heat_conduction_plc_to_te_w(self, t_plc_k: float, t_te_k: float) -> float:
        """Conductive heat flow from the PLC node to the TE node, W.

        Q_cond = (T_plc - T_te) / R_barrier

        Sign convention: positive when T_plc > T_te (heat flows downward).
        """
        return (t_plc_k - t_te_k) / self.barrier_resistance_k_per_w

    def heat_out_plc_w(self, t_plc_k: float, v_m_per_s: float, t_amb_k: float) -> float:
        """Convective + radiative loss from the PLC node, W."""
        h = self.convection_coefficient_w_per_m2_k(v_m_per_s)
        p = self.params
        q_conv = h * p.area_m2 * (t_plc_k - t_amb_k)
        q_rad = p.emissivity * SIGMA_SB_W_PER_M2_K4 * p.area_m2 * (t_plc_k**4 - t_amb_k**4)
        return q_conv + q_rad

    def heat_out_te_w(self, t_te_k: float, v_m_per_s: float, t_amb_k: float) -> float:
        """Convective + radiative loss from the TE node, W."""
        h = self.convection_coefficient_w_per_m2_k(v_m_per_s)
        p = self.params
        q_conv = h * p.area_m2 * (t_te_k - t_amb_k)
        q_rad = p.emissivity * SIGMA_SB_W_PER_M2_K4 * p.area_m2 * (t_te_k**4 - t_amb_k**4)
        return q_conv + q_rad

    # --- ODEs --------------------------------------------------------------

    def dt_plc_dt(
        self,
        t_plc_k: float,
        t_te_k: float,
        p_incident_w: float,
        v_m_per_s: float,
        t_amb_k: float,
    ) -> float:
        """Time derivative of T_plc, K/s."""
        c_plc = self.capacitance_plc_j_per_k
        q_in = self.heat_absorbed_plc_w(p_incident_w, t_plc_k)
        q_cond = self.heat_conduction_plc_to_te_w(t_plc_k, t_te_k)
        q_out = self.heat_out_plc_w(t_plc_k, v_m_per_s, t_amb_k)
        return (q_in - q_cond - q_out) / c_plc

    def dt_te_dt(
        self,
        t_plc_k: float,
        t_te_k: float,
        p_incident_w: float,
        v_m_per_s: float,
        t_amb_k: float,
    ) -> float:
        """Time derivative of T_te, K/s.

        The TE receives heat by conduction from the PLC. A fraction
        eta_TE is converted to electricity and leaves the thermal system;
        the remainder is dissipated to the ambient.
        """
        c_te = self.capacitance_te_j_per_k
        q_cond = self.heat_conduction_plc_to_te_w(t_plc_k, t_te_k)
        eta = eta_te(t_plc_k, t_te_k, self.receiver.te)
        q_through = q_cond * (1.0 - eta)
        q_out = self.heat_out_te_w(t_te_k, v_m_per_s, t_amb_k)
        return (q_through - q_out) / c_te

    # --- Steady state ------------------------------------------------------

    def steady_state(
        self,
        p_incident_w: float,
        v_m_per_s: float,
        t_amb_k: float,
    ) -> tuple[float, float] | None:
        """Solve for the steady-state (T_plc, T_te) at given conditions.

        Returns None if no physically meaningful steady state is found:
        either the solver fails to converge, or the solution has
        non-physical values (below ambient, above 1000 K, T_te >= T_plc).
        """
        if p_incident_w < 0.0:
            raise ValueError(f"Incident power must be >= 0; got {p_incident_w}")
        if v_m_per_s < 0.0:
            raise ValueError(f"Airflow speed must be >= 0; got {v_m_per_s}")
        if t_amb_k <= 0.0:
            raise ValueError(f"Ambient temperature must be > 0; got {t_amb_k}")

        def residuals(y: list[float]) -> list[float]:
            t_plc, t_te = y
            try:
                return [
                    self.dt_plc_dt(t_plc, t_te, p_incident_w, v_m_per_s, t_amb_k),
                    self.dt_te_dt(t_plc, t_te, p_incident_w, v_m_per_s, t_amb_k),
                ]
            except ValueError:
                # Physics model rejected the (possibly non-physical)
                # candidate state. Return a large residual so the solver
                # backs away from this region.
                return [1e6, 1e6]

        for offset_plc, offset_te in (
            (20.0, 10.0),
            (40.0, 20.0),
            (60.0, 30.0),
            (80.0, 40.0),
            (100.0, 50.0),
        ):
            x0 = [t_amb_k + offset_plc, t_amb_k + offset_te]
            result = root(residuals, x0=x0)
            if not result.success:
                continue
            t_plc, t_te = float(result.x[0]), float(result.x[1])
            if not (t_amb_k < t_te < 1000.0):
                continue
            if not (t_te < t_plc < 1000.0):
                continue
            return (t_plc, t_te)
        return None

    def steady_state_energy_balance_error(
        self,
        p_incident_w: float,
        v_m_per_s: float,
        t_amb_k: float,
    ) -> float | None:
        """Relative energy balance error at the PLC node steady state.

        Returns |Q_in - Q_out| / Q_in at the PLC node, or None if no
        steady state exists. Used by the gate test.
        """
        ss = self.steady_state(p_incident_w, v_m_per_s, t_amb_k)
        if ss is None:
            return None
        t_plc, t_te = ss
        q_in = self.heat_absorbed_plc_w(p_incident_w, t_plc)
        q_out = self.heat_conduction_plc_to_te_w(t_plc, t_te) + self.heat_out_plc_w(
            t_plc, v_m_per_s, t_amb_k
        )
        if q_in <= 0.0:
            return None
        return abs(q_in - q_out) / q_in

    # --- Thermal runaway boundary ------------------------------------------

    def thermal_runaway_boundary(self, v_m_per_s: float, t_amb_k: float) -> float:
        """Incident power P_max at which the steady-state T_plc reaches the
        PLC material degradation limit (Section 33.4).

        P_max is defined as the supremum of incident powers for which a
        *safe* steady state exists, where safe means T_plc < t_max_kelvin.
        Above this power either no equilibrium exists inside the model's
        validity bounds, or the only equilibrium has T_plc >= t_max_kelvin.

        Implementation: bisection on the predicate "a safe steady state
        exists at this power". Bisection is used instead of a continuous
        root-finder because eta_plc is clamped to zero at t_max_kelvin,
        which introduces a discontinuity in the steady-state map T_plc(P).
        A continuous root-finder can converge to an arbitrary point inside
        the discontinuity; bisection converges to its lower edge, which is
        the physically meaningful P_max.

        Raises RuntimeError if no safe steady state exists even at
        infinitesimal power, which would indicate a broken thermal model.
        """
        t_max = self.receiver.plc.t_max_kelvin

        def is_safe(p: float) -> bool:
            ss = self.steady_state(p, v_m_per_s, t_amb_k)
            return ss is not None and ss[0] < t_max

        # Anchor at a vanishingly small power where the PLC is at ambient
        # and therefore trivially safe.
        p_lo = 1e-6
        if not is_safe(p_lo):
            raise RuntimeError(f"No safe steady state at P = {p_lo} W. Thermal model is broken.")

        # Exponential search for an upper bound where the model is unsafe.
        p_hi = p_lo * 2.0
        while is_safe(p_hi):
            p_lo = p_hi
            p_hi *= 2.0
            if p_hi > 1e7:
                raise RuntimeError(
                    "Could not find an unsafe power within 10 MW. Thermal model is broken."
                )

        # Bisection to machine precision on P.
        for _ in range(80):
            p_mid = 0.5 * (p_lo + p_hi)
            if p_mid <= p_lo or p_mid >= p_hi:
                break
            if is_safe(p_mid):
                p_lo = p_mid
            else:
                p_hi = p_mid

        return float(p_lo)

    # --- Time integration --------------------------------------------------

    def simulate(
        self,
        p_incident_w: float,
        v_m_per_s: float,
        t_amb_k: float,
        t_plc_initial_k: float,
        t_te_initial_k: float,
        t_end_s: float,
        n_samples: int = 500,
    ) -> ThermalSnapshot:
        """Integrate the two-node ODE forward in time and return the final
        snapshot. Uses scipy.integrate.solve_ivp (RK45).

        Suitable for showing transient response and convergence to the
        steady state.
        """
        if t_end_s <= 0.0:
            raise ValueError(f"t_end_s must be > 0; got {t_end_s}")
        if n_samples < 2:
            raise ValueError(f"n_samples must be >= 2; got {n_samples}")

        def rhs(t: float, y: np.ndarray) -> list[float]:
            t_plc, t_te = float(y[0]), float(y[1])
            return [
                self.dt_plc_dt(t_plc, t_te, p_incident_w, v_m_per_s, t_amb_k),
                self.dt_te_dt(t_plc, t_te, p_incident_w, v_m_per_s, t_amb_k),
            ]

        sol = solve_ivp(
            rhs,
            (0.0, t_end_s),
            [t_plc_initial_k, t_te_initial_k],
            t_eval=np.linspace(0.0, t_end_s, n_samples),
            method="RK45",
        )
        if not sol.success:
            raise RuntimeError(f"ODE integration failed: {sol.message}")
        return ThermalSnapshot(
            time_s=float(sol.t[-1]),
            t_plc_k=float(sol.y[0, -1]),
            t_te_k=float(sol.y[1, -1]),
        )


def default_model() -> ThermalModel:
    """Construct a ThermalModel with the default parameters."""
    return ThermalModel()
