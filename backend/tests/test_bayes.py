"""Tests for recursive Bayesian parameter estimation.

Roadmap task s6-1: Bayesian parameter update (recursive estimation
for thermal params).
Gate: Posterior converges; uncertainty shrinks with data.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.refinement.bayes import (
    GaussianBelief,
    VectorGaussianBelief,
    numeric_sensitivity,
    recursive_bayes_update,
    update_sequence,
    vector_kalman_update,
)

# -- GaussianBelief validation ----------------------------------------------


def test_belief_rejects_non_finite_mean() -> None:
    with pytest.raises(ValueError, match="mean must be finite"):
        GaussianBelief(mean=float("nan"), variance=1.0)


def test_belief_rejects_non_positive_variance() -> None:
    with pytest.raises(ValueError, match="variance must be finite and positive"):
        GaussianBelief(mean=0.0, variance=0.0)
    with pytest.raises(ValueError, match="variance must be finite and positive"):
        GaussianBelief(mean=0.0, variance=-1.0)


def test_belief_std() -> None:
    b = GaussianBelief(mean=0.0, variance=4.0)
    assert b.std == pytest.approx(2.0)


# -- Scalar Kalman update: correctness --------------------------------------


def test_scalar_update_matches_hand_computation() -> None:
    """Verify the update against a worked example.

    Prior: N(0, 100), observation y = 5, h = 1, r^2 = 1.
    K = 100 * 1 / (1 * 100 + 1) = 100/101 ~= 0.990099
    mu' = 0 + 0.990099 * 5 = 4.950495
    sigma'^2 = (1 - 0.990099) * 100 = 0.990099
    """
    prior = GaussianBelief(mean=0.0, variance=100.0)
    posterior = recursive_bayes_update(
        prior, observation=5.0, observation_noise_variance=1.0, sensitivity=1.0
    )
    assert posterior.mean == pytest.approx(4.9504950495, rel=1e-9)
    assert posterior.variance == pytest.approx(0.9900990099, rel=1e-9)


def test_scalar_update_rejects_non_finite_observation() -> None:
    prior = GaussianBelief(mean=0.0, variance=1.0)
    with pytest.raises(ValueError, match="observation must be finite"):
        recursive_bayes_update(
            prior,
            observation=float("inf"),
            observation_noise_variance=1.0,
            sensitivity=1.0,
        )


def test_scalar_update_rejects_zero_noise_variance() -> None:
    prior = GaussianBelief(mean=0.0, variance=1.0)
    with pytest.raises(ValueError, match="observation_noise_variance"):
        recursive_bayes_update(
            prior,
            observation=1.0,
            observation_noise_variance=0.0,
            sensitivity=1.0,
        )


def test_scalar_update_rejects_non_finite_sensitivity() -> None:
    prior = GaussianBelief(mean=0.0, variance=1.0)
    with pytest.raises(ValueError, match="sensitivity must be finite"):
        recursive_bayes_update(
            prior,
            observation=1.0,
            observation_noise_variance=1.0,
            sensitivity=float("nan"),
        )


# -- Theorems: variance strictly shrinks ------------------------------------


def test_posterior_variance_strictly_less_than_prior() -> None:
    """For any nonzero sensitivity, posterior variance is strictly
    less than prior variance. This is a theorem."""
    prior = GaussianBelief(mean=0.0, variance=10.0)
    posterior = recursive_bayes_update(
        prior, observation=3.0, observation_noise_variance=0.5, sensitivity=1.0
    )
    assert posterior.variance < prior.variance


def test_posterior_variance_shrinks_monotonically_across_sequence() -> None:
    """The s6-1 gate, first form: uncertainty shrinks with data."""
    prior = GaussianBelief(mean=0.0, variance=100.0)
    true_theta = 0.005
    rng = np.random.default_rng(20261009)
    noise_std = 0.05
    observations = [true_theta + float(rng.normal(0.0, noise_std)) for _ in range(200)]
    history = update_sequence(prior, observations, noise_std**2, 1.0)
    for i in range(1, len(history)):
        assert history[i].variance < history[i - 1].variance, (
            f"Variance did not shrink at step {i}: "
            f"{history[i - 1].variance} -> {history[i].variance}"
        )


# -- Theorems: mean converges -----------------------------------------------


def test_posterior_mean_converges_to_true_parameter() -> None:
    """The s6-1 gate, second form: posterior converges.

    With n observations at h=1 and noise variance r^2, the posterior
    standard deviation is bounded by r / sqrt(n). After 1000
    observations with r = 0.05, the posterior std is <= 0.0016. The
    posterior mean should be within a few posterior stds of the true
    parameter with high probability.
    """
    prior = GaussianBelief(mean=0.0, variance=100.0)
    true_theta = 0.005
    rng = np.random.default_rng(20261009)
    noise_std = 0.05
    observations = [true_theta + float(rng.normal(0.0, noise_std)) for _ in range(1000)]
    history = update_sequence(prior, observations, noise_std**2, 1.0)
    final = history[-1]
    # The posterior std after 1000 obs is ~ r / sqrt(1000) ~ 0.0016.
    # The posterior mean should be within a few stds of the true value.
    assert abs(final.mean - true_theta) < 5.0 * final.std, (
        f"Posterior mean {final.mean} is not within 5 std of "
        f"true parameter {true_theta}; posterior std {final.std}"
    )


def test_posterior_std_matches_theoretical_bound() -> None:
    """For h=1 and n observations with observation variance r^2, the
    posterior variance should be approximately r^2 / n."""
    prior = GaussianBelief(mean=0.0, variance=1e6)
    n = 500
    noise_std = 0.1
    rng = np.random.default_rng(0)
    observations = [0.0 + float(rng.normal(0.0, noise_std)) for _ in range(n)]
    history = update_sequence(prior, observations, noise_std**2, 1.0)
    final = history[-1]
    theoretical = noise_std**2 / n
    # Allow a factor-of-2 window because the prior is wide but not
    # infinitely diffuse; the transient contributes.
    assert theoretical / 2.0 < final.variance < theoretical * 2.0


# -- Bias handling ----------------------------------------------------------


def test_posterior_shifts_toward_biased_observations() -> None:
    """If observations are systematically biased, the posterior mean
    shifts toward the bias, but the variance still shrinks."""
    prior = GaussianBelief(mean=0.0, variance=100.0)
    biased_true = 0.2  # observations generated around 0.2
    rng = np.random.default_rng(123)
    observations = [biased_true + float(rng.normal(0.0, 0.05)) for _ in range(200)]
    history = update_sequence(prior, observations, 0.05**2, 1.0)
    final = history[-1]
    assert final.mean > 0.15  # shifted toward 0.2
    assert final.variance < 0.001  # still shrunk


# -- Determinism ------------------------------------------------------------


def test_update_is_deterministic() -> None:
    prior = GaussianBelief(mean=1.0, variance=5.0)
    a = recursive_bayes_update(prior, 2.0, 0.5, 1.0)
    b = recursive_bayes_update(prior, 2.0, 0.5, 1.0)
    assert a == b


def test_sequence_is_deterministic() -> None:
    prior = GaussianBelief(mean=0.0, variance=1.0)
    obs = [1.0, 2.0, 3.0, 4.0, 5.0]
    a = update_sequence(prior, obs, 0.1, 1.0)
    b = update_sequence(prior, obs, 0.1, 1.0)
    assert a == b


# -- numeric_sensitivity ----------------------------------------------------


def test_numeric_sensitivity_linear_model() -> None:
    def model(theta: float) -> float:
        return 3.0 * theta + 1.0

    d = numeric_sensitivity(model, 5.0)
    assert d == pytest.approx(3.0, rel=1e-6)


def test_numeric_sensitivity_quadratic_model() -> None:
    def model(theta: float) -> float:
        return theta * theta

    d = numeric_sensitivity(model, 3.0)
    # d/dtheta (theta^2) = 2 theta = 6 at theta = 3.
    assert d == pytest.approx(6.0, rel=1e-4)


def test_numeric_sensitivity_rejects_non_callable() -> None:
    with pytest.raises(ValueError, match="must be callable"):
        numeric_sensitivity(42, 0.0)


def test_numeric_sensitivity_rejects_bad_step() -> None:
    def model(theta: float) -> float:
        return theta

    with pytest.raises(ValueError, match="step must be finite and positive"):
        numeric_sensitivity(model, 0.0, step=0.0)
    with pytest.raises(ValueError, match="step must be finite and positive"):
        numeric_sensitivity(model, 0.0, step=-1.0)


# -- Vector Kalman -----------------------------------------------------------


def test_vector_belief_rejects_bad_shapes() -> None:
    with pytest.raises(ValueError, match="1D"):
        VectorGaussianBelief(
            mean=np.array([[1.0, 2.0]]),
            covariance=np.eye(2),
        )


def test_vector_belief_rejects_non_symmetric_covariance() -> None:
    with pytest.raises(ValueError, match="symmetric"):
        VectorGaussianBelief(
            mean=np.array([0.0, 0.0]),
            covariance=np.array([[1.0, 0.5], [0.2, 1.0]]),
        )


def test_vector_belief_rejects_non_positive_definite() -> None:
    with pytest.raises(ValueError, match="positive definite"):
        VectorGaussianBelief(
            mean=np.array([0.0, 0.0]),
            covariance=np.array([[1.0, 0.0], [0.0, -1.0]]),
        )


def test_vector_kalman_hand_computation() -> None:
    """Two independent scalar parameters observed directly.

    Prior: identity on both parameters.
    Observation noise: identity on both observations.
    Sensitivity: identity.
    Each parameter's posterior after one observation y_i should be
    the scalar Kalman update with prior (0, 1), observation y_i,
    noise 1, h = 1: posterior mean = y_i / 2, posterior var = 1/2.
    """
    prior = VectorGaussianBelief(
        mean=np.array([0.0, 0.0]),
        covariance=np.eye(2),
    )
    posterior = vector_kalman_update(
        prior,
        observation=np.array([1.0, 2.0]),
        observation_noise_covariance=np.eye(2),
        sensitivity_matrix=np.eye(2),
    )
    assert posterior.mean[0] == pytest.approx(0.5, rel=1e-9)
    assert posterior.mean[1] == pytest.approx(1.0, rel=1e-9)
    assert posterior.covariance[0, 0] == pytest.approx(0.5, rel=1e-9)
    assert posterior.covariance[1, 1] == pytest.approx(0.5, rel=1e-9)
    assert posterior.covariance[0, 1] == pytest.approx(0.0, abs=1e-12)


def test_vector_kalman_rejects_bad_sensitivity_shape() -> None:
    prior = VectorGaussianBelief(
        mean=np.array([0.0, 0.0]),
        covariance=np.eye(2),
    )
    with pytest.raises(ValueError, match="sensitivity_matrix shape"):
        vector_kalman_update(
            prior,
            observation=np.array([1.0, 2.0, 3.0]),
            observation_noise_covariance=np.eye(3),
            sensitivity_matrix=np.eye(2),
        )


def test_vector_kalman_variance_shrinks() -> None:
    prior = VectorGaussianBelief(
        mean=np.array([0.0, 0.0]),
        covariance=np.eye(2) * 10.0,
    )
    posterior = vector_kalman_update(
        prior,
        observation=np.array([1.0, 1.0]),
        observation_noise_covariance=np.eye(2),
        sensitivity_matrix=np.eye(2),
    )
    # Trace of posterior covariance should be less than trace of prior.
    assert np.trace(posterior.covariance) < np.trace(prior.covariance)


def test_vector_kalman_converges_over_many_observations() -> None:
    """Feed 500 observations of two independent parameters and
    verify the posterior mean converges to the true values."""
    rng = np.random.default_rng(20261009)
    true_theta = np.array([0.005, 0.02])
    noise_std = 0.01
    prior = VectorGaussianBelief(
        mean=np.zeros(2),
        covariance=np.eye(2) * 1.0,
    )
    current = prior
    for _ in range(500):
        y = true_theta + rng.normal(0.0, noise_std, size=2)
        current = vector_kalman_update(
            current,
            observation=y,
            observation_noise_covariance=np.eye(2) * noise_std**2,
            sensitivity_matrix=np.eye(2),
        )
    # After 500 obs, posterior std ~ 0.01 / sqrt(500) ~ 4.5e-4.
    assert abs(current.mean[0] - true_theta[0]) < 5.0e-3
    assert abs(current.mean[1] - true_theta[1]) < 5.0e-3
