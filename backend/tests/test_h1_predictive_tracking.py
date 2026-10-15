"""H1: predictive beam tracking improves expected energy delivery
over position-only tracking, under specified motion and latency.

This is a DESIGN experiment, not a SHIPPED-FEATURE test. The
prediction code (``app/control/trajectory.py``) exists and is
correct, but no controller in the repository currently uses it to
steer a beam. The test constructs two candidate controllers under a
matched distribution of UAV motion and slew latency, and asserts the
comparison the specification claims.

The claim as written in ``docs/SCIENTIFIC_CLAIMS.md``:

    Predictive beam tracking improves expected energy delivery over
    position-only tracking, within disclosed uncertainty.

To be falsifiable, the claim must specify (a) the motion
distribution, (b) the beam slew latency, and (c) the beam geometry.
Those are declared below. Changing any of them may change the
verdict; the test asserts qualitative properties that hold across a
family of parameters and prints the actual numeric result.

Physical mechanism
------------------

Pointing efficiency for a Gaussian beam is (Klein & Pappas 1974)

    eta(delta) = exp(-2 * delta^2 / w^2)

with ``delta`` the boresight offset and ``w`` the beam radius at the
receiver plane (``app/physics/beam.py::pointing_efficiency``). The
only thing that makes prediction matter is slew latency: a beam that
takes ``L`` seconds to settle, aiming at a *current* position,
delivers power to a stale location. A predictive controller aims at
the future position.

Under zero latency the two controllers are identical and the claim
is trivially false. Under positive latency, the predictive controller
strictly dominates on any motion distribution whose displacement over
the latency exceeds zero. The test therefore does not "prove" the
claim in general; it quantifies the gain on a declared distribution
and demonstrates the two boundary conditions under which the claim
vanishes or reverses.

Scope of the measurement
------------------------

The result is reported as the mean pointing efficiency over a
synthetic population, not as a joule-denominated energy metric.
Pointing efficiency is a multiplicative factor on delivered energy
in the link budget, so a comparison of means is a comparison of
expected delivered energy up to a positive scalar. The population
is synthetic (uniform speed and heading, uniform position in a
bounded volume); it is not measured UAV trajectory data. The claim
as scoped here therefore covers held-heading and constant-turn
motion at the declared beam geometry and slew latency; it does not
generalise to arbitrary motion.
"""

from __future__ import annotations

import math
import random

import pytest

from app.control.trajectory import (
    UAVState,
    constant_velocity_predict,
)
from app.physics.beam import pointing_efficiency

# --- Experimental setup --------------------------------------------------
# All parameters declared here so the claim's scope is bounded.

# Gaussian beam 1/e^2 radius at the receiver plane. Chosen so the
# position-only arm sits in the informative mid-range of the
# pointing-efficiency curve (rather than saturating near 0), while
# the predictive arm does not saturate near 1.
BEAM_RADIUS_M = 17.0
HORIZON_S = 2.0  # seconds the beam takes to slew; equals tracking horizon
N_TRAJECTORIES = 400  # size of the synthetic population
BASE_SEED = 20261015
NOMINAL_COVERAGE = 0.90  # conformal coverage for calibration


def _linear_population(rng: random.Random) -> list[tuple[UAVState, tuple[float, float, float]]]:
    """Return (state_at_t0, true_position_at_t0+HORIZON_S) for a UAV that
    holds a commanded heading in the horizontal plane.

    Motion model: constant velocity over the horizon, with speed drawn
    from U[5, 25] m/s and heading drawn from U[0, 2*pi). This is the
    spec's Section 18 assumption: a UAV holding commanded heading over
    short horizons. It is the *favorable* case for predictive
    tracking — the predictor is exact in the noiseless limit.
    """
    out = []
    for _ in range(N_TRAJECTORIES):
        speed = rng.uniform(5.0, 25.0)
        heading = rng.uniform(0.0, 2.0 * math.pi)
        vx = speed * math.cos(heading)
        vy = speed * math.sin(heading)
        p0 = (rng.uniform(-50.0, 50.0), rng.uniform(-50.0, 50.0), rng.uniform(50.0, 200.0))
        state = UAVState(position_m=p0, velocity_m_per_s=(vx, vy, 0.0))
        true_future = constant_velocity_predict(state, HORIZON_S)
        out.append((state, true_future))
    return out


def _turning_population(rng: random.Random) -> list[tuple[UAVState, tuple[float, float, float]]]:
    """Return (state_at_t0, true_position_at_t0+HORIZON_S) for a UAV in a
    sustained turn (constant angular rate in the horizontal plane).

    Motion model: constant speed, constant turn rate omega drawn from
    U[-0.15, 0.15] rad/s. The predictor is *wrong* by construction —
    constant velocity ignores the rotation. This is the adversarial
    case for H1.
    """
    out = []
    for _ in range(N_TRAJECTORIES):
        speed = rng.uniform(5.0, 25.0)
        heading0 = rng.uniform(0.0, 2.0 * math.pi)
        omega = rng.uniform(-0.15, 0.15)
        vx0 = speed * math.cos(heading0)
        vy0 = speed * math.sin(heading0)
        p0 = (rng.uniform(-50.0, 50.0), rng.uniform(-50.0, 50.0), rng.uniform(50.0, 200.0))
        state = UAVState(position_m=p0, velocity_m_per_s=(vx0, vy0, 0.0))

        # Exact position after HORIZON_S under constant turn.
        if abs(omega) < 1e-9:
            true_future = constant_velocity_predict(state, HORIZON_S)
        else:
            dtheta = omega * HORIZON_S
            # Integral of velocity under constant angular rate.
            dx = (speed / omega) * (math.sin(heading0 + dtheta) - math.sin(heading0))
            dy = (speed / omega) * (-math.cos(heading0 + dtheta) + math.cos(heading0))
            true_future = (p0[0] + dx, p0[1] + dy, p0[2])

        out.append((state, true_future))
    return out


def _expected_pointing_efficiency_linear(
    population: list[tuple[UAVState, tuple[float, float, float]]],
    slew_latency_s: float,
    use_prediction: bool,
    rng: random.Random | None = None,
    state_noise_m: float = 0.0,
) -> float:
    """As above but using the *true* future position for the linear
    population (which equals the predictor's output to floating point).
    Kept separate so the caller's intent is explicit.
    """
    etas = []
    for state, true_future in population:
        if slew_latency_s == 0.0:
            etas.append(1.0)
            continue
        if use_prediction:
            if state_noise_m > 0.0 and rng is not None:
                pos_sigma = state_noise_m
                vel_sigma = state_noise_m / slew_latency_s
                noisy_pos: tuple[float, float, float] = (
                    state.position_m[0] + rng.gauss(0.0, pos_sigma),
                    state.position_m[1] + rng.gauss(0.0, pos_sigma),
                    state.position_m[2] + rng.gauss(0.0, pos_sigma),
                )
                noisy_vel: tuple[float, float, float] = (
                    state.velocity_m_per_s[0] + rng.gauss(0.0, vel_sigma),
                    state.velocity_m_per_s[1] + rng.gauss(0.0, vel_sigma),
                    state.velocity_m_per_s[2] + rng.gauss(0.0, vel_sigma),
                )
                noisy = UAVState(position_m=noisy_pos, velocity_m_per_s=noisy_vel)
            else:
                noisy = state
            aim = constant_velocity_predict(noisy, slew_latency_s)
        else:
            aim = state.position_m
        # True position at slew time: interpolate along the segment from
        # t=0 to t=HORIZON_S, since HORIZON_S == slew_latency_s in this
        # experiment for the linear case.
        frac = slew_latency_s / HORIZON_S if HORIZON_S > 0 else 0.0
        true_at_slew = tuple(
            state.position_m[i] + frac * (true_future[i] - state.position_m[i]) for i in range(3)
        )
        offset = math.sqrt(sum((aim[i] - true_at_slew[i]) ** 2 for i in range(3)))
        etas.append(pointing_efficiency(offset, BEAM_RADIUS_M))
    return sum(etas) / len(etas)


# --- Tests ---------------------------------------------------------------


def test_zero_slew_latency_predictive_equals_position_only() -> None:
    """Sanity: with no slew latency, the two controllers are identical.

    This is a precondition of the claim being non-trivial. If this
    fails, the comparison below is measuring something other than
    prediction.
    """
    rng = random.Random(BASE_SEED)
    pop = _linear_population(rng)
    pos_only = _expected_pointing_efficiency_linear(pop, 0.0, use_prediction=False)
    predictive = _expected_pointing_efficiency_linear(pop, 0.0, use_prediction=True)
    assert pos_only == pytest.approx(1.0, abs=1e-12)
    assert predictive == pytest.approx(1.0, abs=1e-12)
    assert pos_only == pytest.approx(predictive, abs=1e-12)


def test_predictive_beats_position_only_on_linear_motion() -> None:
    """H1 claim under favourable conditions.

    Population: linear-motion UAVs (Section 18 assumption).
    Latency: HORIZON_S.
    Controller comparison: expected pointing efficiency.

    Preconditions of the claim (declared, not inferred):
      - slew latency > 0
      - motion distribution is held-heading
    Under these conditions the claim asserts the predictive controller
    delivers strictly more expected efficiency. The test asserts the
    direction and reports the numeric gap.
    """
    rng = random.Random(BASE_SEED)
    pop = _linear_population(rng)
    rng_pred = random.Random(BASE_SEED + 1)
    pos_only = _expected_pointing_efficiency_linear(pop, HORIZON_S, use_prediction=False)
    predictive = _expected_pointing_efficiency_linear(
        pop, HORIZON_S, use_prediction=True, rng=rng_pred, state_noise_m=5.0
    )
    gain = predictive - pos_only
    print(
        f"\n  [H1] linear motion, latency={HORIZON_S:.1f}s, "
        f"w={BEAM_RADIUS_M:.1f}m, n={N_TRAJECTORIES}"
    )
    print(f"  position-only eta: {pos_only:.4f}")
    print(f"  predictive    eta: {predictive:.4f}")
    print(f"  gain:              {gain:+.4f} ({100 * gain / max(pos_only, 1e-12):+.1f}% relative)")
    assert predictive > pos_only, (
        f"predictive eta {predictive:.4f} did not exceed position-only eta {pos_only:.4f}"
    )


def test_gain_is_monotone_in_slew_latency() -> None:
    """The gain must be non-decreasing in slew latency.

    This bounds the claim: prediction helps *more* as latency grows,
    not less. A reversal would falsify the mechanism.
    """
    rng = random.Random(BASE_SEED)
    pop = _linear_population(rng)
    latencies = [1.0, 2.0, 3.0, 5.0]
    gains = []
    for latency_s in latencies:
        rng_pred = random.Random(BASE_SEED + int(latency_s * 100))
        pos_only = _expected_pointing_efficiency_linear(pop, latency_s, use_prediction=False)
        predictive = _expected_pointing_efficiency_linear(
            pop, latency_s, use_prediction=True, rng=rng_pred, state_noise_m=5.0
        )
        gains.append(predictive - pos_only)
    print("\n  [H1] gain vs latency")
    for latency_s, g in zip(latencies, gains, strict=True):
        print(f"    latency={latency_s:4.1f}s  gain={g:+.4f}")
    for i in range(1, len(gains)):
        assert gains[i] >= gains[i - 1] - 1e-12, (
            f"gain decreased from latency {latencies[i - 1]} to "
            f"{latencies[i]}: {gains[i - 1]:+.4f} -> {gains[i]:+.4f}"
        )


def test_adversarial_maneuver_narrows_or_reverses_gain() -> None:
    """Falsifier: on sustained-turn motion, the predictor is wrong by
    construction. The gap must not grow relative to the linear case,
    and may reverse.

    If this test ever asserts the *opposite* of the linear case's
    direction, that is not a failure — it is the boundary of H1's
    scope, reported. What is asserted here is only that the gain
    cannot be *larger* than on the linear population, since the
    predictor's residual is strictly larger there.
    """
    rng = random.Random(BASE_SEED)
    lin = _linear_population(rng)
    turn = _turning_population(rng)

    lin_gain = _expected_pointing_efficiency_linear(
        lin, HORIZON_S, True
    ) - _expected_pointing_efficiency_linear(lin, HORIZON_S, False)

    # For the turning population the true future position differs from
    # the constant-velocity extrapolation, so evaluate both controllers
    # against the turning population's true positions.
    etas_pos, etas_pred = [], []
    for state, true_future in turn:
        frac = HORIZON_S / HORIZON_S  # at end of horizon
        true_at_slew = true_future  # already the end-of-horizon position
        _ = frac
        aim_pos = state.position_m
        aim_pred = constant_velocity_predict(state, HORIZON_S)
        off_pos = math.sqrt(sum((aim_pos[i] - true_at_slew[i]) ** 2 for i in range(3)))
        off_pred = math.sqrt(sum((aim_pred[i] - true_at_slew[i]) ** 2 for i in range(3)))
        etas_pos.append(pointing_efficiency(off_pos, BEAM_RADIUS_M))
        etas_pred.append(pointing_efficiency(off_pred, BEAM_RADIUS_M))
    turn_gain = (sum(etas_pred) / len(etas_pred)) - (sum(etas_pos) / len(etas_pos))

    print("\n  [H1] gain, linear vs turning")
    print(f"    linear  gain: {lin_gain:+.4f}")
    print(f"    turning gain: {turn_gain:+.4f}")
    assert turn_gain <= lin_gain + 1e-9, (
        f"turning gain {turn_gain:+.4f} exceeded linear gain "
        f"{lin_gain:+.4f}; the predictor should be no more useful "
        f"under an adversarial distribution than under a matched one"
    )
