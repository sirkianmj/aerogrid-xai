"""Build Notebook 04 - PWL error convergence.

Run once from the repo root:
    python scripts/build_notebook_04.py

Generates: notebooks/04_pwl_error_convergence.ipynb
"""

from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
CELLS = []


def md(text: str) -> None:
    CELLS.append(nbf.v4.new_markdown_cell(text))


def code(text: str) -> None:
    CELLS.append(nbf.v4.new_code_cell(text))


md("""
# Notebook 04 - PWL Error Convergence

**Sprint:** S3 (Formal Verification & Discovery)
**Roadmap task:** s3-6
**Specification reference:** Section 34.2 (Error tracking).

## Scientific gate

> epsilon decreases monotonically with n_segments; logged.

## What this notebook does

1. Sweeps the number of PWL segments from 1 to 256 for four
   reference functions: exponential decay, quadratic, square root,
   and the PLC efficiency model eta_plc(T).
2. Records the reported epsilon for each (function, n_segments)
   pair.
3. Plots epsilon vs. n_segments on a log-log axis.
4. Asserts non-increasing epsilon for every function in the sweep.

## Theoretical basis for monotonicity

For a fixed partition, each segment is replaced by a constant equal
to the sampled minimum on that segment. Refining the partition
replaces each segment [a, b] by two segments [a, c] and [c, b] whose
sampled minima are at least as large as the sampled minimum on
[a, b], because the sample set is denser on each subinterval. So
f_hat_new(x) >= f_hat_old(x) pointwise, hence f(x) - f_hat_new(x)
<= f(x) - f_hat_old(x) pointwise, hence epsilon_new <= epsilon_old.
This notebook confirms the monotonicity numerically and logs the
values, which is what the roadmap gate requires.
""")

md("## Setup")

code("""
%matplotlib inline

import sys
from pathlib import Path

repo_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(repo_root / "backend"))

import math

import matplotlib.pyplot as plt

from app.physics.receiver import eta_plc
from app.verification.pwl import pwl_approximate

print("Setup complete.")
""")

md("""
## Section 1 - Reference functions

Four smooth functions are used. The eta_plc(T) function is the one
that actually enters Stage B of CLEAR-D; the other three are controls
spanning a range of curvatures and singularity behaviours.
""")

code("""
def exp_decay(x):
    return float(math.exp(-x))


def quadratic(x):
    return float(x * x)


def sqrt_f(x):
    return float(math.sqrt(max(x, 1e-12)))


def eta_plc_wrapped(x):
    return float(eta_plc(x))


FUNCTIONS = {
    "exp(-x) on [0, 5]": (exp_decay, (0.0, 5.0)),
    "x^2 on [0, 10]": (quadratic, (0.0, 10.0)),
    "sqrt(x) on [0.01, 4]": (sqrt_f, (0.01, 4.0)),
    "eta_plc(T) on [280, 350] K": (eta_plc_wrapped, (280.0, 350.0)),
}

for name, (_, rng) in FUNCTIONS.items():
    print(f"{name}: domain {rng}")
""")

md("""
## Section 2 - Sweep epsilon vs. segments

For each function, sweep n_segments from 1 to 256 (powers of two) and
record the reported epsilon. The table is printed so the sweep is
logged as the gate requires.
""")

code("""
SEGMENTS = [1, 2, 4, 8, 16, 32, 64, 128, 256]

results = {}
for name, (f, rng) in FUNCTIONS.items():
    epsilons = []
    for n in SEGMENTS:
        approx = pwl_approximate(f, rng, n, name)
        epsilons.append(approx.epsilon)
    results[name] = epsilons

header = "function".ljust(28) + " ".join(f"{n:>10d}" for n in SEGMENTS)
print(header)
for name, eps in results.items():
    row = " ".join(f"{e:>10.3e}" for e in eps)
    print(f"{name:<28s} {row}")
""")

md("""
## Section 3 - Log-log plot

On a log-log axis, the expected slope for a smooth function under
uniform refinement is approximately -2, because the sampled minimum
on a segment of width h differs from the true minimum by O(h^2) for
a smooth function. The plotted lines should show slope close to -2
for smooth functions and flatter behaviour near the square-root
singularity.
""")

code("""
fig, ax = plt.subplots(figsize=(10, 6))
for name, eps in results.items():
    ax.loglog(SEGMENTS, eps, marker="o", linewidth=2, label=name)

ax.set_xlabel("n_segments")
ax.set_ylabel("epsilon = max |f - f_hat|")
ax.set_title("PWL approximation error vs. segment count")
ax.grid(True, which="both", alpha=0.3)
ax.legend(loc="best", fontsize=9)
plt.tight_layout()
plt.show()

print("Log-log plot rendered.")
""")

md("""
## Section 4 - Gate assertion

The gate is: epsilon decreases monotonically with n_segments. In
practice the correct statement is non-increasing, because a finite
sample grid can only weakly improve the bound. We assert
non-increasing with a small numerical tolerance, and additionally
confirm that the final epsilon is strictly smaller than the first
for every function in the sweep.
""")

code("""
TOL = 1e-9
for name, eps in results.items():
    for i in range(1, len(eps)):
        delta = eps[i] - eps[i - 1]
        assert delta <= TOL, (
            f"epsilon increased for {name} at n={SEGMENTS[i]}: "
            f"{eps[i - 1]:.3e} -> {eps[i]:.3e}"
        )
    assert eps[-1] < eps[0], (
        f"Final epsilon not smaller than initial for {name}: "
        f"{eps[0]:.3e} -> {eps[-1]:.3e}"
    )

print("Monotonic non-increase: PASS for all four functions.")
print("Final < initial:        PASS for all four functions.")
""")

md("""
## Section 5 - Summary

The s3-6 gate is satisfied: epsilon decreases monotonically with
n_segments for every function in the sweep, and the per-function
epsilon tables are logged above. This closes the loop on the Stage B
error-tracking requirement from Section 34.2: any epsilon used in a
verification result is now backed by a numerical convergence
demonstration on the actual functions Stage B will encode.
""")

code("""
print("Notebook 04 - PWL error convergence")
print("=" * 60)
for name, eps in results.items():
    ratio = eps[0] / max(eps[-1], 1e-30)
    print(
        f"{name:<28s}: eps(1) = {eps[0]:.3e}, "
        f"eps(256) = {eps[-1]:.3e}, ratio = {ratio:.1f}x"
    )
print()
print("ALL GATES PASS")
""")

NB["cells"] = CELLS
NB["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (aerogrid)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/04_pwl_error_convergence.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(NB, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(CELLS)}")
