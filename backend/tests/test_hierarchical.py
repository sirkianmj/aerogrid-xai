"""Tests for the hierarchical SMT decomposition.

Roadmap task:
    s3-4 Hierarchical decomposition (k=5-15 intra-cluster plus
    inter-cluster flow).
    Gate: SOUND composition - cluster partition has no shared variables.
"""

from __future__ import annotations

import pytest
import z3

from app.verification.hierarchical import (
    Cluster,
    ConstraintEntry,
    HierarchicalModel,
    HierarchicalResult,
)
from app.verification.pwl import pwl_approximate


def _r(value: str) -> z3.ArithRef:
    return z3.RealVal(value)


def _sum_le(v: dict[str, z3.ArithRef], names: list[str], bound: str) -> z3.BoolRef:
    terms: list[z3.ArithRef] = [v[names[0]]]
    for name in names[1:]:
        terms.append(v[name])
    total = terms[0]
    for term in terms[1:]:
        total = total + term
    return total <= _r(bound)


# construction invariants


def test_add_cluster_rejects_duplicate_name() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    with pytest.raises(ValueError):
        m.add_cluster(Cluster("a", frozenset({"y"})))


def test_add_cluster_rejects_shared_variable() -> None:
    """A true graph partition has no shared variables between clusters
    (Section 34.3)."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x", "y"})))
    with pytest.raises(ValueError):
        m.add_cluster(Cluster("b", frozenset({"y", "z"})))


def test_intra_constraint_rejects_spanning_variables() -> None:
    """An intra-cluster constraint that references variables from two
    clusters must be rejected; the decomposition is unsound otherwise."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    m.add_cluster(Cluster("b", frozenset({"y"})))
    with pytest.raises(ValueError):
        m.add_intra_cluster_constraint(
            ConstraintEntry(
                family_name="spanning",
                variables=frozenset({"x", "y"}),
                fn=lambda v: v["x"] + v["y"] <= _r("10"),
            )
        )


def test_intra_constraint_rejects_unknown_variable() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    with pytest.raises(ValueError):
        m.add_intra_cluster_constraint(
            ConstraintEntry(
                family_name="ghost",
                variables=frozenset({"x", "z"}),
                fn=lambda v: v["x"] + v["z"] <= _r("10"),
            )
        )


def test_intra_constraint_rejects_empty_variables() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    with pytest.raises(ValueError):
        m.add_intra_cluster_constraint(
            ConstraintEntry(
                family_name="empty",
                variables=frozenset(),
                fn=lambda v: z3.BoolVal(True),
            )
        )


def test_inter_constraint_rejects_cluster_variable() -> None:
    """An inter-cluster constraint must reference only flow variables,
    not variables that belong to a cluster."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    with pytest.raises(ValueError):
        m.add_inter_cluster_constraint(
            ConstraintEntry(
                family_name="bad_flow",
                variables=frozenset({"x"}),
                fn=lambda v: v["x"] >= _r("0"),
            )
        )


# soundness of composition


def test_all_clusters_sat_and_flow_sat_yields_sat() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("north", frozenset({"a", "b"})))
    m.add_cluster(Cluster("south", frozenset({"c", "d"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="north_sum",
            variables=frozenset({"a", "b"}),
            fn=lambda v: _sum_le(v, ["a", "b"], "10"),
        )
    )
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="south_sum",
            variables=frozenset({"c", "d"}),
            fn=lambda v: _sum_le(v, ["c", "d"], "20"),
        )
    )
    m.add_inter_cluster_constraint(
        ConstraintEntry(
            family_name="flow_balance",
            variables=frozenset({"flow_ns"}),
            fn=lambda v: v["flow_ns"] >= _r("0"),
        )
    )
    result = m.check()
    assert isinstance(result, HierarchicalResult)
    assert result.status == "sat"
    assert result.flow_status == "sat"
    assert len(result.cluster_results) == 2
    for cr in result.cluster_results:
        assert cr.status == "sat"


def test_one_cluster_unsat_yields_overall_unsat() -> None:
    """If any cluster is UNSAT, the whole system is UNSAT because the
    conjunction of the bucket satisfiabilities is necessary for joint
    satisfiability."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("north", frozenset({"a"})))
    m.add_cluster(Cluster("south", frozenset({"b"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="north_impossible",
            variables=frozenset({"a"}),
            fn=lambda v: z3.And(v["a"] >= _r("10"), v["a"] <= _r("5")),
        )
    )
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="south_trivial",
            variables=frozenset({"b"}),
            fn=lambda v: v["b"] >= _r("0"),
        )
    )
    result = m.check()
    assert result.status == "unsat"
    assert "north" in result.unsat_clusters
    assert "south" not in result.unsat_clusters


def test_flow_unsat_yields_overall_unsat() -> None:
    """If the flow subproblem is UNSAT, the whole system is UNSAT."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("only", frozenset({"x"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="cluster_trivial",
            variables=frozenset({"x"}),
            fn=lambda v: v["x"] >= _r("0"),
        )
    )
    m.add_inter_cluster_constraint(
        ConstraintEntry(
            family_name="flow_impossible",
            variables=frozenset({"f"}),
            fn=lambda v: z3.And(v["f"] >= _r("5"), v["f"] <= _r("1")),
        )
    )
    result = m.check()
    assert result.status == "unsat"
    assert result.flow_status == "unsat"
    assert result.unsat_clusters == ()


def test_two_disjoint_clusters_are_independent() -> None:
    """Cluster A's feasibility does not depend on cluster B's
    constraints, because the two variable sets are disjoint. This is
    the soundness property Section 34.3 relies on."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("a", frozenset({"x"})))
    m.add_cluster(Cluster("b", frozenset({"y"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="a_tight",
            variables=frozenset({"x"}),
            fn=lambda v: v["x"] == _r("3"),
        )
    )
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="b_loose",
            variables=frozenset({"y"}),
            fn=lambda v: v["y"] <= _r("100"),
        )
    )
    result = m.check()
    assert result.status == "sat"
    a_model = next(cr for cr in result.cluster_results if cr.cluster_name == "a").model
    b_model = next(cr for cr in result.cluster_results if cr.cluster_name == "b").model
    assert a_model["x"] == pytest.approx(3.0, rel=1e-9)
    assert b_model["y"] <= 100.0


def test_summary_format() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("only", frozenset({"x"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="x_pos",
            variables=frozenset({"x"}),
            fn=lambda v: v["x"] >= _r("0"),
        )
    )
    result = m.check()
    text = result.summary()
    assert "status: sat" in text
    assert "cluster only: sat" in text
    assert "flow: sat" in text


def test_epsilon_is_reported_in_result() -> None:
    m = HierarchicalModel()
    m.add_cluster(Cluster("only", frozenset({"x"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="x_any",
            variables=frozenset({"x"}),
            fn=lambda v: v["x"] >= _r("0"),
        )
    )
    approx = pwl_approximate(lambda t: t, (0.0, 10.0), 5, "dummy_family")
    m.add_epsilon_source(approx)
    result = m.check()
    assert len(result.epsilons) == 1
    assert result.epsilons[0][0] == "dummy_family"
    assert result.max_epsilon == pytest.approx(approx.epsilon, rel=1e-12)


def test_no_inter_constraints_still_solves() -> None:
    """A model with no inter-cluster constraints and no cluster
    variables yields SAT (trivially, since the flow subproblem is
    empty)."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("only", frozenset({"x"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="x_free",
            variables=frozenset({"x"}),
            fn=lambda v: v["x"] == v["x"],
        )
    )
    result = m.check()
    assert result.status == "sat"
    assert result.flow_status == "sat"


def test_recommended_k_band_is_documented() -> None:
    """The k in [5, 15] band is a performance guideline (Section 34.3),
    not a soundness requirement. It is exported as module constants so
    callers can size clusters correctly."""
    from app.verification.hierarchical import RECOMMENDED_K_MAX, RECOMMENDED_K_MIN

    assert RECOMMENDED_K_MIN == 5
    assert RECOMMENDED_K_MAX == 15


def test_multi_variable_within_cluster() -> None:
    """A cluster with many variables works correctly: constraints that
    reference subsets of the cluster's variables are still placed in
    that cluster."""
    m = HierarchicalModel()
    m.add_cluster(Cluster("big", frozenset({"a", "b", "c", "d", "e"})))
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="subset_ab",
            variables=frozenset({"a", "b"}),
            fn=lambda v: v["a"] + v["b"] <= _r("5"),
        )
    )
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="subset_cd",
            variables=frozenset({"c", "d"}),
            fn=lambda v: v["c"] + v["d"] <= _r("5"),
        )
    )
    m.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="single_e",
            variables=frozenset({"e"}),
            fn=lambda v: v["e"] >= _r("0"),
        )
    )
    result = m.check()
    assert result.status == "sat"
