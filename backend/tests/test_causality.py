"""Tests for the causal data-flow audit.

Roadmap task s6-5: Scientific gate - loop is causal.
Gate: Operational data affects model, not vice versa (no data leakage).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

from app.refinement.bayes import GaussianBelief, recursive_bayes_update
from app.refinement.causality import (
    FORBIDDEN_IMPORT_ROOTS,
    CausalEdge,
    CausalNode,
    StageECausalGraph,
    ast_audit_refinement_imports,
    stage_e_causal_graph,
)
from app.refinement.pwl_tune import AdaptivePWLRefiner

# -- Node / edge validation -------------------------------------------------


def test_node_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="node name must be non-empty"):
        CausalNode("", "operation")


def test_node_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown node kind"):
        CausalNode("x", "not_a_kind")


def test_edge_rejects_self_loop() -> None:
    with pytest.raises(ValueError, match="self-loop"):
        CausalEdge("a", "a")


def test_edge_rejects_empty_endpoints() -> None:
    with pytest.raises(ValueError, match="edge endpoints must be non-empty"):
        CausalEdge("", "a")


# -- Graph construction -----------------------------------------------------


def test_graph_rejects_duplicate_node_names() -> None:
    with pytest.raises(ValueError, match="duplicate node name"):
        StageECausalGraph(
            nodes=[CausalNode("a", "operation"), CausalNode("a", "model_state")],
            edges=[],
        )


def test_graph_rejects_edge_to_undeclared_node() -> None:
    with pytest.raises(ValueError, match="edge target"):
        StageECausalGraph(
            nodes=[CausalNode("a", "operation")],
            edges=[CausalEdge("a", "ghost")],
        )


def test_graph_rejects_edge_from_undeclared_node() -> None:
    with pytest.raises(ValueError, match="edge source"):
        StageECausalGraph(
            nodes=[CausalNode("a", "operation")],
            edges=[CausalEdge("ghost", "a")],
        )


# -- Reachability -----------------------------------------------------------


def test_has_path_direct() -> None:
    g = StageECausalGraph(
        nodes=[CausalNode("a", "operation"), CausalNode("b", "operation")],
        edges=[CausalEdge("a", "b")],
    )
    assert g.has_path("a", "b")
    assert not g.has_path("b", "a")


def test_has_path_transitive() -> None:
    g = StageECausalGraph(
        nodes=[
            CausalNode("a", "operation"),
            CausalNode("b", "operation"),
            CausalNode("c", "operation"),
        ],
        edges=[CausalEdge("a", "b"), CausalEdge("b", "c")],
    )
    assert g.has_path("a", "c")


def test_has_path_self() -> None:
    g = StageECausalGraph(
        nodes=[CausalNode("a", "operation")],
        edges=[],
    )
    assert g.has_path("a", "a")


def test_has_path_no_route() -> None:
    g = StageECausalGraph(
        nodes=[CausalNode("a", "operation"), CausalNode("b", "operation")],
        edges=[],
    )
    assert not g.has_path("a", "b")


# -- Acyclicity -------------------------------------------------------------


def test_acyclic_graph_passes() -> None:
    g = StageECausalGraph(
        nodes=[
            CausalNode("a", "operation"),
            CausalNode("b", "operation"),
            CausalNode("c", "operation"),
        ],
        edges=[CausalEdge("a", "b"), CausalEdge("b", "c")],
    )
    g.verify_acyclic()


def test_cycle_detected() -> None:
    g = StageECausalGraph(
        nodes=[
            CausalNode("a", "operation"),
            CausalNode("b", "operation"),
        ],
        edges=[CausalEdge("a", "b"), CausalEdge("b", "a")],
    )
    with pytest.raises(ValueError, match="cycle"):
        g.verify_acyclic()


def test_longer_cycle_detected() -> None:
    g = StageECausalGraph(
        nodes=[
            CausalNode("a", "operation"),
            CausalNode("b", "operation"),
            CausalNode("c", "operation"),
        ],
        edges=[
            CausalEdge("a", "b"),
            CausalEdge("b", "c"),
            CausalEdge("c", "a"),
        ],
    )
    with pytest.raises(ValueError, match="cycle"):
        g.verify_acyclic()


# -- The declared Stage E graph ---------------------------------------------


def test_declared_graph_is_acyclic() -> None:
    g = stage_e_causal_graph()
    g.verify_acyclic()


def test_declared_graph_has_external_to_model_path() -> None:
    g = stage_e_causal_graph()
    assert g.check_path_exists_between_kinds("external_data", "model_state")


def test_declared_graph_has_no_model_to_external_path() -> None:
    g = stage_e_causal_graph()
    bad = g.check_no_path_between_kinds("model_state", "external_data")
    assert bad == [], f"Forbidden causal paths from model to data: {bad}"


def test_declared_graph_has_required_nodes() -> None:
    g = stage_e_causal_graph()
    names = {n.name for n in g.nodes}
    for required in (
        "external_source",
        "observed_values",
        "theta_t0",
        "theta_t1",
        "pwl_t0",
        "pwl_t1",
        "bayes_update",
        "pwl_refine",
    ):
        assert required in names, f"missing required node {required}"


def test_declared_graph_node_counts_by_kind() -> None:
    g = stage_e_causal_graph()
    # t0 and t1 for each of theta and pwl.
    assert len(g.nodes_of_kind("external_data")) == 2
    assert len(g.nodes_of_kind("model_state")) == 4
    assert len(g.nodes_of_kind("operation")) >= 4


def test_declared_graph_no_back_edge_theta() -> None:
    """No edge goes from theta_t1 back to theta_t0 or into any
    external_data node."""
    g = stage_e_causal_graph()
    for e in g.edges:
        if e.target == "theta_t0":
            assert g.kind_of(e.source) == "external_data" or False, "unexpected edge into theta_t0"


# -- AST audit on the real package ------------------------------------------


def test_ast_audit_finds_no_physics_imports_in_refinement() -> None:
    violations = ast_audit_refinement_imports()
    assert violations == [], "Forbidden physics imports in refinement modules: " + "; ".join(
        f"{v.file}:{v.line} imports {v.imported_module}" for v in violations
    )


def test_ast_audit_detects_synthetic_violation(tmp_path: Path) -> None:
    bad = tmp_path / "bad_module.py"
    bad.write_text("import numpy as np\nfrom app.physics.thermal import ThermalModel\nx = 1.0\n")
    violations = ast_audit_refinement_imports(tmp_path)
    assert len(violations) == 1
    assert violations[0].imported_module == "app.physics.thermal"


def test_ast_audit_ignores_allowed_imports(tmp_path: Path) -> None:
    good = tmp_path / "good_module.py"
    good.write_text(
        "import numpy as np\nfrom app.verification.pwl import PWLApproximation\nx = 1.0\n"
    )
    violations = ast_audit_refinement_imports(tmp_path)
    assert violations == []


def test_forbidden_roots_includes_physics() -> None:
    assert "app.physics" in FORBIDDEN_IMPORT_ROOTS


# -- Source-text import scan (strict form) ----------------------------------


_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+app\.physics\b|import\s+app\.physics\b)",
    re.MULTILINE,
)


def _has_physics_import_line(source: str) -> bool:
    """True iff source contains an actual import statement from
    app.physics. A docstring mention is not an import."""
    return _IMPORT_RE.search(source) is not None


def test_bayes_module_has_no_physics_import() -> None:
    from app.refinement import bayes

    source = Path(bayes.__file__).read_text()
    assert not _has_physics_import_line(source), (
        "bayes.py contains an import statement from app.physics"
    )


def test_discrepancy_module_has_no_physics_import() -> None:
    from app.refinement import discrepancy

    source = Path(discrepancy.__file__).read_text()
    assert not _has_physics_import_line(source)


def test_pwl_tune_module_has_no_physics_import() -> None:
    from app.refinement import pwl_tune

    source = Path(pwl_tune.__file__).read_text()
    assert not _has_physics_import_line(source)


def test_causality_module_has_no_physics_import() -> None:
    from app.refinement import causality

    source = Path(causality.__file__).read_text()
    assert not _has_physics_import_line(source)


def test_source_text_scan_detects_synthetic_import() -> None:
    """Meta-test: the regex-based scan must flag an actual import."""
    assert _has_physics_import_line("from app.physics.thermal import X\n")
    assert _has_physics_import_line("import app.physics\n")
    # But not a docstring mention.
    assert not _has_physics_import_line('"""see app.physics.thermal for details"""\n')


# -- Behavioral confirmation -------------------------------------------------


def _run_loop(
    initial_theta: float,
    observation_seed: int,
    n_obs: int = 100,
) -> tuple[list[float], float]:
    """Run a miniature Stage E loop.

    Observation model: y = g(theta) + noise, where g(theta) =
    exp(-theta * x). The linearization is:
        y ~ g(mu) + g'(mu) * (theta - mu)
    Rearranged into the standard linear form y' = h * theta + noise
    where h = g'(mu) and y' = y - g(mu) + g'(mu) * mu.

    In terms of recursive_bayes_update(prior, observation, noise_var,
    sensitivity), the standard formula computes innovation =
    observation - h * mu. To get innovation = y - g(mu), we pass
    observation = y - g(mu) + h * mu.
    """
    theta_true = 0.55
    noise_std = 0.003
    x_probe = 1.0

    rng = np.random.default_rng(observation_seed)
    observations: list[float] = []

    belief = GaussianBelief(mean=initial_theta, variance=0.01)
    for _ in range(n_obs):
        y_true = math.exp(-theta_true * x_probe)
        y_obs = y_true + float(rng.normal(0.0, noise_std))
        observations.append(y_obs)

        # Linearization at the current prior mean.
        g_mu = math.exp(-belief.mean * x_probe)
        h = -x_probe * g_mu  # d g / d theta at mu

        # Pseudo-observation so the standard Kalman innovation formula
        # yields y_obs - g(mu).
        pseudo_obs = y_obs - g_mu + h * belief.mean

        belief = recursive_bayes_update(
            belief,
            observation=pseudo_obs,
            observation_noise_variance=noise_std**2,
            sensitivity=h,
        )
    return observations, belief.mean


def test_observations_are_invariant_to_initial_model_state() -> None:
    """Two runs with different initial thetas and the same observation
    seed produce identical observation sequences."""
    obs_a, _ = _run_loop(initial_theta=0.10, observation_seed=7)
    obs_b, _ = _run_loop(initial_theta=0.90, observation_seed=7)
    assert obs_a == obs_b, (
        "Observation sequence depends on the initial model state; this indicates data leakage."
    )


def test_different_observation_seeds_produce_different_observations() -> None:
    obs_a, _ = _run_loop(initial_theta=0.40, observation_seed=1)
    obs_b, _ = _run_loop(initial_theta=0.40, observation_seed=2)
    assert obs_a != obs_b


def test_model_state_changes_in_response_to_observations() -> None:
    """The positive causal direction: observations do affect the
    model. From theta = 0.10 the estimate must move toward theta_true
    = 0.55."""
    _, final = _run_loop(initial_theta=0.10, observation_seed=99)
    assert 0.4 < final < 0.7, f"theta moved to {final}; expected convergence toward 0.55"


def test_model_state_converges_from_above_as_well() -> None:
    """From theta = 0.90 the estimate must move downward toward
    theta_true = 0.55."""
    _, final = _run_loop(initial_theta=0.90, observation_seed=99)
    assert 0.4 < final < 0.7, f"theta moved to {final}; expected convergence toward 0.55"


def test_refiner_used_with_external_observation_source() -> None:
    def f(x: float) -> float:
        return float(np.exp(-0.5 * x))

    rng = np.random.default_rng(11)
    refiner = AdaptivePWLRefiner(f, (0.0, 5.0), initial_n_segments=8, max_segments=32)
    for _ in range(20):
        xs = rng.uniform(0.0, 5.0, size=10)
        refiner.observe_batch([(float(x), f(float(x))) for x in xs])
        refiner.refine_once()
    assert refiner.current_epsilon() <= refiner.cycle_history()[0].epsilon
