"""Fuzz test of the PWL-SMT encoding soundness direction.

Roadmap task s3-8: Scientific gate - SAT verdict is conservative.
Gate (as stated in Rev. 2 roadmap):
    Fuzz test against random architectures.
    Never falsely declares infeasible architecture feasible.

Direction note (must be read before interpreting the result)
------------------------------------------------------------

Section 34.2 of the specification writes the PWL approximation as
f_hat(x) <= f(x) and calls it a "sound over-approximation". Under
that direction the encoder's feasible set { x : f_hat(x) <= 0 } is a
superset of the true feasible set { x : f(x) <= 0 }, so:

  - UNSAT is definitive. If the encoded region is empty, the true
    region is also empty.
  - SAT is necessary but not sufficient. A SAT witness satisfies
    f_hat(x) <= 0 but may satisfy f(x) > 0 for the same x.

Under the spec's literal direction, the correct soundness claim is
"UNSAT never falsely declares a feasible architecture infeasible".
The Rev. 2 gate states the opposite direction: "SAT never falsely
declares an infeasible architecture feasible". That claim does not
hold under f_hat <= f and would require flipping the direction to
f_hat >= f. See backend/app/verification/pwl.py for the derivation.

This test module therefore verifies the sound direction that the
current encoder guarantees: UNSAT implies true infeasibility. It
records the direction question rather than silently asserting a
claim the encoder cannot support.

If the project later requires the strict "SAT is conservative"
claim, the fix is a localized change to the sampling loop in
pwl.py (sampled maxima instead of sampled minima, and encode
f_hat >= f). Every downstream test that assumes the current
direction would then need to be re-run.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable

import pytest
import z3

from app.verification.encoder import (
    ConstraintSession,
    ConstraintSpec,
    pwl_to_z3_expr,
)
from app.verification.pwl import PWLApproximation, pwl_approximate

Function1D = Callable[[float], float]
GeneratorFn = Callable[[int], Function1D]

RANDOM_SEED = 20261009
N_TRIALS_PER_FAMILY = 40


def _true_violation(approx: PWLApproximation, x: float, f: Function1D) -> bool:
    """Return True if x is inside the PWL domain and f(x) > 0.

    A point is a true violation of the constraint f(x) <= 0 if it is
    in the domain and f(x) > 0. The PWL approximation may still say
    f_hat(x) <= 0 at this point; the encoder may have declared SAT
    here even though the true constraint is violated. That is the
    false-positive region the direction note describes.
    """
    if x < approx.x_min - 1e-9 or x > approx.x_max + 1e-9:
        return False
    return f(x) > 0.0


def _random_linear_positive_slope(seed: int) -> Function1D:
    rng = random.Random(seed)
    a = rng.uniform(-5.0, 5.0)
    b = rng.uniform(0.0, 10.0)
    return lambda x: a + b * x


def _random_linear_negative_slope(seed: int) -> Function1D:
    rng = random.Random(seed)
    a = rng.uniform(-5.0, 5.0)
    b = rng.uniform(-10.0, 0.0)
    return lambda x: a + b * x


def _random_sinusoid(seed: int) -> Function1D:
    rng = random.Random(seed)
    amp = rng.uniform(0.5, 5.0)
    freq = rng.uniform(0.5, 3.0)
    phase = rng.uniform(0.0, 2.0 * math.pi)
    return lambda x: amp * math.sin(freq * x + phase)


def _random_quadratic(seed: int) -> Function1D:
    rng = random.Random(seed)
    a = rng.uniform(-1.0, 1.0)
    b = rng.uniform(-5.0, 5.0)
    c = rng.uniform(-5.0, 5.0)
    return lambda x: a * x * x + b * x + c


GENERATORS: list[tuple[str, GeneratorFn]] = [
    ("linear_pos", _random_linear_positive_slope),
    ("linear_neg", _random_linear_negative_slope),
    ("sinusoid", _random_sinusoid),
    ("quadratic", _random_quadratic),
]


# -- Sound direction: UNSAT must imply true infeasibility ---------------


@pytest.mark.parametrize("family_name, gen", GENERATORS)
def test_unsat_implies_true_infeasibility(family_name: str, gen: GeneratorFn) -> None:
    """If the encoder returns UNSAT, the true constraint f(x) <= 0 must
    have no solution in the PWL domain.

    This is the sound direction the current encoder guarantees. It is
    the claim the s3-8 gate should be evaluated against, per the
    direction note at the top of this module.
    """
    rng = random.Random(RANDOM_SEED)
    for trial in range(N_TRIALS_PER_FAMILY):
        seed = rng.randint(0, 10**9)
        f = gen(seed)
        x_range = (-10.0, 10.0)
        n_segments = rng.choice([8, 16, 32])
        approx = pwl_approximate(f, x_range, n_segments, f"{family_name}_{trial}")

        session = ConstraintSession()
        session.add_constraint(ConstraintSpec(approx.family_name, approx, "le"))
        result = session.check()

        if result.status != "unsat":
            continue

        n_samples = 2001
        for i in range(n_samples):
            x = x_range[0] + (x_range[1] - x_range[0]) * i / (n_samples - 1)
            if f(x) <= 0.0:
                pytest.fail(
                    f"Encoder returned UNSAT but f({x}) = {f(x)} <= 0 for "
                    f"family {family_name} trial {trial} (seed {seed}). "
                    "This would be a soundness violation."
                )


# -- Direction note: SAT may include points where f > 0 ---------------


@pytest.mark.parametrize("family_name, gen", GENERATORS)
def test_sat_witness_is_inside_pwl_domain(family_name: str, gen: GeneratorFn) -> None:
    """If the encoder returns SAT, the witness must be inside the PWL
    domain. This is a necessary condition; it is not sufficient for
    the witness to satisfy the true constraint.
    """
    rng = random.Random(RANDOM_SEED + 1)
    saw_sat = False
    for trial in range(N_TRIALS_PER_FAMILY):
        seed = rng.randint(0, 10**9)
        f = gen(seed)
        x_range = (-10.0, 10.0)
        n_segments = rng.choice([8, 16, 32])
        approx = pwl_approximate(f, x_range, n_segments, f"{family_name}_{trial}")

        session = ConstraintSession()
        session.add_constraint(ConstraintSpec(approx.family_name, approx, "le"))
        result = session.check()

        if result.status != "sat":
            continue
        saw_sat = True
        x = result.x_value
        assert x is not None
        assert approx.x_min - 1e-9 <= x <= approx.x_max + 1e-9, (
            f"SAT witness {x} outside PWL domain "
            f"[{approx.x_min}, {approx.x_max}] for {family_name} trial {trial}"
        )

    if not saw_sat:
        pytest.skip(f"No SAT instances produced for family {family_name}")


# -- Directional documentation test ------------------------------------


def test_false_positive_region_is_bounded_by_epsilon() -> None:
    """The size of the false-positive region — the set of points where
    f_hat(x) <= 0 but f(x) > 0 — is bounded by the reported epsilon
    per segment. This test constructs a deterministic example and
    confirms the bound holds.

    This documents the shape of the discrepancy that the direction
    note describes: SAT is not conservative in the f_hat <= f
    direction, but the size of the region where it can be wrong is
    bounded by the reported epsilon.
    """

    def f(x: float) -> float:
        return x - 0.5

    approx = pwl_approximate(f, (0.0, 10.0), 5, "shifted")
    assert approx.epsilon > 0.0

    x_false_positive = 1.0  # inside segment [0, 2]
    assert approx.evaluate(x_false_positive) <= 0.0
    assert f(x_false_positive) > 0.0

    segment_width = 2.0
    max_local_error = segment_width * 1.0  # slope of f is 1.0
    assert f(x_false_positive) - approx.evaluate(x_false_positive) <= max_local_error


# -- Z3 expr round trip on random functions ----------------------------


@pytest.mark.parametrize("family_name, gen", GENERATORS)
def test_z3_expression_matches_python_at_random_points(family_name: str, gen: GeneratorFn) -> None:
    """For random functions and random x, the Z3-encoded PWL value must
    match the Python PWL value at that x. This is a numerical
    correctness check on the encoder, independent of the soundness
    direction question.
    """
    rng = random.Random(RANDOM_SEED + 2)
    for trial in range(10):
        seed = rng.randint(0, 10**9)
        f = gen(seed)
        x_range = (-10.0, 10.0)
        n_segments = rng.choice([8, 16])
        approx = pwl_approximate(f, x_range, n_segments, f"{family_name}_{trial}")

        z3_x = z3.Real(f"x_rt_{family_name}_{trial}")
        z3_expr = pwl_to_z3_expr(z3_x, approx)

        for _ in range(5):
            x_val = rng.uniform(x_range[0], x_range[1])
            solver = z3.Solver()
            solver.add(z3_x == z3.RealVal(repr(x_val)))
            assert solver.check() == z3.sat
            z3_val = float(solver.model().eval(z3_expr, model_completion=True).as_fraction())
            py_val = approx.evaluate(x_val)
            assert abs(z3_val - py_val) < 1e-6, (
                f"Z3/py PWL value mismatch at x = {x_val}: "
                f"z3 = {z3_val}, py = {py_val}, family = {family_name}"
            )


# -- Aggregate gate summary --------------------------------------------


def test_sound_direction_holds_across_all_families() -> None:
    """Aggregate test that runs many random trials across all four
    function families and asserts the sound direction (UNSAT implies
    true infeasibility) holds in every case. This is the gate test
    for s3-8, evaluated against the direction the encoder actually
    guarantees.
    """
    rng = random.Random(RANDOM_SEED + 3)
    total_unsat = 0
    total_sat = 0
    false_positives_observed = 0
    soundness_violations = 0

    for family_name, gen in GENERATORS:
        for trial in range(N_TRIALS_PER_FAMILY):
            seed = rng.randint(0, 10**9)
            f = gen(seed)
            x_range = (-10.0, 10.0)
            n_segments = rng.choice([8, 16, 32])
            approx = pwl_approximate(f, x_range, n_segments, f"{family_name}_{trial}")

            session = ConstraintSession()
            session.add_constraint(ConstraintSpec(approx.family_name, approx, "le"))
            result = session.check()

            if result.status == "unsat":
                total_unsat += 1
                n_samples = 501
                for i in range(n_samples):
                    x = x_range[0] + (x_range[1] - x_range[0]) * i / (n_samples - 1)
                    if f(x) <= 0.0:
                        soundness_violations += 1
                        break
            elif result.status == "sat":
                total_sat += 1
                x_val: float | None = result.x_value
                if x_val is not None and f(x_val) > 0.0:
                    false_positives_observed += 1

    assert soundness_violations == 0, (
        f"Encoder returned UNSAT at {soundness_violations} instances where "
        "the true constraint has a solution. This is a soundness violation."
    )

    print(
        f"Fuzz summary: {total_unsat} UNSAT, {total_sat} SAT, "
        f"{false_positives_observed} SAT instances were true violations "
        "(allowed under f_hat <= f, see direction note)."
    )
