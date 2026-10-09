"""Recursive Bayesian estimation of physics model parameters.

Roadmap task s6-1: Bayesian parameter update (recursive estimation
for thermal params).
Gate: Posterior converges; uncertainty shrinks with data.

Reference:
    AeroGrid-XAI Final Comprehensive Specification (Rev. 6),
    Section 37.1 (Physics Model Refinement). Operational data -
    measured receiver temperature, measured efficiency, measured
    received power - is compared against Stage A's predictions and
    parameter discrepancies are used to update the Stage A
    parameters via recursive Bayesian estimation.

Method
------

For a scalar parameter theta with Gaussian prior N(mu, sigma^2) and
a linear-Gaussian observation y = h * theta + epsilon with
epsilon ~ N(0, r^2), the posterior after one observation is again
Gaussian:

    K   = sigma^2 * h / (h^2 * sigma^2 + r^2)      (Kalman gain)
    mu' = mu + K * (y - h * mu)
    s'^2 = (1 - K * h) * sigma^2

The observation sensitivity h = d y / d theta is either supplied by
the caller (if known analytically) or computed numerically from a
physics model callback.

For a vector of parameters theta ~ N(mu, Sigma) with observation
y = H theta + epsilon, epsilon ~ N(0, R):

    K   = Sigma H^T (H Sigma H^T + R)^{-1}
    mu' = mu + K (y - H mu)
    Sigma' = (I - K H) Sigma

This is the standard Kalman filter update and is exact for the
linear-Gaussian case. When the underlying physics is nonlinear, the
caller linearizes the model and supplies H; that is an EKF and is
documented as such at the call site.

Determinism
-----------

All updates are pure functions of the inputs. Given the same prior
and the same sequence of observations, the posterior is bit-identical
across runs. This supports the s6-5 gate, which requires the
refinement loop to be causal and reproducible.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class GaussianBelief:
    """A scalar Gaussian belief: mean and variance.

    Attributes:
        mean: Posterior mean.
        variance: Posterior variance. Must be > 0.
    """

    mean: float
    variance: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.mean):
            raise ValueError(f"mean must be finite; got {self.mean}")
        if not math.isfinite(self.variance) or self.variance <= 0.0:
            raise ValueError(f"variance must be finite and positive; got {self.variance}")

    @property
    def std(self) -> float:
        return math.sqrt(self.variance)


def recursive_bayes_update(
    prior: GaussianBelief,
    observation: float,
    observation_noise_variance: float,
    sensitivity: float,
) -> GaussianBelief:
    """Update a scalar Gaussian belief with one linear-Gaussian observation.

    Args:
        prior: Current belief about theta.
        observation: The observed value y.
        observation_noise_variance: r^2 in the observation model
            y = h * theta + epsilon, epsilon ~ N(0, r^2). Must be > 0.
        sensitivity: h = d y / d theta. May be negative; only h^2
            enters the covariance update.

    Returns:
        Posterior GaussianBelief.

    Raises:
        ValueError on non-finite inputs or non-positive noise variance.

    Note:
        The posterior variance is strictly less than the prior
        variance whenever h != 0. This is a theorem, not an
        empirical property, and is verified by a test.
    """
    if not math.isfinite(observation):
        raise ValueError(f"observation must be finite; got {observation}")
    if not math.isfinite(observation_noise_variance) or observation_noise_variance <= 0.0:
        raise ValueError(
            f"observation_noise_variance must be finite and positive; "
            f"got {observation_noise_variance}"
        )
    if not math.isfinite(sensitivity):
        raise ValueError(f"sensitivity must be finite; got {sensitivity}")

    h = sensitivity
    r2 = observation_noise_variance
    sigma2 = prior.variance
    mu = prior.mean

    innovation = observation - h * mu
    innovation_variance = h * h * sigma2 + r2
    kalman_gain = sigma2 * h / innovation_variance

    posterior_mean = mu + kalman_gain * innovation
    posterior_variance = (1.0 - kalman_gain * h) * sigma2

    return GaussianBelief(mean=posterior_mean, variance=posterior_variance)


def numeric_sensitivity(
    model: object,
    prior_mean: float,
    step: float = 1e-6,
) -> float:
    """Estimate d(model_output)/d(theta) by central difference.

    Args:
        model: A callable theta -> y.
        prior_mean: The point around which to linearize.
        step: Finite-difference step. Must be > 0.

    Returns:
        Numeric estimate of the derivative at prior_mean.

    The caller is responsible for ensuring the step is small enough
    for the model's curvature and large enough to avoid floating-point
    cancellation. For the thermal model in app.physics.thermal, a
    step of 1e-6 is well within both bounds for the parameter ranges
    documented in ThermalParams.
    """
    if not math.isfinite(prior_mean):
        raise ValueError(f"prior_mean must be finite; got {prior_mean}")
    if not math.isfinite(step) or step <= 0.0:
        raise ValueError(f"step must be finite and positive; got {step}")
    if not callable(model):
        raise ValueError("model must be callable")

    y_plus = float(model(prior_mean + step))
    y_minus = float(model(prior_mean - step))
    return (y_plus - y_minus) / (2.0 * step)


@dataclass(frozen=True)
class VectorGaussianBelief:
    """A multivariate Gaussian belief over k parameters.

    Attributes:
        mean: Posterior mean vector, shape (k,).
        covariance: Posterior covariance matrix, shape (k, k).
            Must be symmetric positive definite.
    """

    mean: np.ndarray
    covariance: np.ndarray

    def __post_init__(self) -> None:
        m = np.asarray(self.mean, dtype=float)
        c = np.asarray(self.covariance, dtype=float)
        if m.ndim != 1:
            raise ValueError(f"mean must be 1D; got shape {m.shape}")
        if c.shape != (m.shape[0], m.shape[0]):
            raise ValueError(
                f"covariance shape {c.shape} inconsistent with mean length {m.shape[0]}"
            )
        if not np.all(np.isfinite(m)):
            raise ValueError("mean must be finite")
        if not np.all(np.isfinite(c)):
            raise ValueError("covariance must be finite")
        # Symmetry check.
        if not np.allclose(c, c.T, atol=1e-12):
            raise ValueError("covariance must be symmetric")
        # Positive-definiteness via Cholesky.
        try:
            np.linalg.cholesky(c)
        except np.linalg.LinAlgError as exc:
            raise ValueError("covariance must be positive definite") from exc


def vector_kalman_update(
    prior: VectorGaussianBelief,
    observation: np.ndarray,
    observation_noise_covariance: np.ndarray,
    sensitivity_matrix: np.ndarray,
) -> VectorGaussianBelief:
    """One step of the vector Kalman filter update.

    Args:
        prior: Prior belief over theta, dimension k.
        observation: Observation vector y, dimension m.
        observation_noise_covariance: R, shape (m, m), positive
            definite.
        sensitivity_matrix: H = d y / d theta, shape (m, k).

    Returns:
        Posterior VectorGaussianBelief.

    Raises:
        ValueError on shape mismatch or singular innovation matrix.
    """
    mu = np.asarray(prior.mean, dtype=float)
    sigma = np.asarray(prior.covariance, dtype=float)
    y = np.asarray(observation, dtype=float)
    r = np.asarray(observation_noise_covariance, dtype=float)
    h = np.asarray(sensitivity_matrix, dtype=float)

    k = mu.shape[0]
    m = y.shape[0]

    if h.shape != (m, k):
        raise ValueError(
            f"sensitivity_matrix shape {h.shape} inconsistent with "
            f"observation length {m} and parameter length {k}"
        )
    if r.shape != (m, m):
        raise ValueError(f"observation_noise_covariance shape {r.shape} must be ({m}, {m})")

    innovation = y - h @ mu
    innovation_cov = h @ sigma @ h.T + r

    try:
        innovation_cov_inv = np.linalg.inv(innovation_cov)
    except np.linalg.LinAlgError as exc:
        raise ValueError("innovation covariance is singular") from exc

    kalman_gain = sigma @ h.T @ innovation_cov_inv

    posterior_mean = mu + kalman_gain @ innovation
    identity = np.eye(k)
    posterior_cov = (identity - kalman_gain @ h) @ sigma

    # Re-symmetrize to suppress numerical asymmetry.
    posterior_cov = 0.5 * (posterior_cov + posterior_cov.T)

    return VectorGaussianBelief(mean=posterior_mean, covariance=posterior_cov)


def update_sequence(
    prior: GaussianBelief,
    observations: Sequence[float],
    observation_noise_variance: float,
    sensitivity: float,
) -> tuple[GaussianBelief, ...]:
    """Apply recursive_bayes_update across a sequence of observations.

    Returns the belief after each observation, in order. The initial
    prior is not included.
    """
    history: list[GaussianBelief] = []
    current = prior
    for y in observations:
        current = recursive_bayes_update(current, y, observation_noise_variance, sensitivity)
        history.append(current)
    return tuple(history)
