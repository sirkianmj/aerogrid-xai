"""Tests for the regulatory constraint encoding.

Roadmap task:
    s3-5 Regulatory constraint encoding (ANSI Z136.1 MPE + FCC Part 18).
    Gate: MPE-violating architecture -> UNSAT by construction.
"""

from __future__ import annotations

import pytest
import z3

from app.verification.hierarchical import Cluster, HierarchicalModel
from app.verification.regulatory import (
    RF_LIMIT_GENERAL_POPULATION,
    LaserMPE,
    laser_constraint,
    laser_mpe,
    rf_constraint,
)

# laser_mpe: table lookup


def test_laser_mpe_1064_025s() -> None:
    mpe = laser_mpe(1064.0, 0.25)
    assert isinstance(mpe, LaserMPE)
    assert mpe.mpe_mw_per_cm2 == pytest.approx(2.55, rel=1e-9)
    assert mpe.mpe_w_per_m2() == pytest.approx(25.5, rel=1e-9)


def test_laser_mpe_1064_10s() -> None:
    mpe = laser_mpe(1064.0, 10.0)
    assert mpe.mpe_mw_per_cm2 == pytest.approx(1.0, rel=1e-9)
    assert mpe.mpe_w_per_m2() == pytest.approx(10.0, rel=1e-9)


def test_laser_mpe_520_025s() -> None:
    mpe = laser_mpe(520.0, 0.25)
    assert mpe.mpe_mw_per_cm2 == pytest.approx(2.55, rel=1e-9)


def test_laser_mpe_default_duration_is_025s() -> None:
    default = laser_mpe(1064.0)
    explicit = laser_mpe(1064.0, 0.25)
    assert default.mpe_mw_per_cm2 == explicit.mpe_mw_per_cm2


def test_laser_mpe_rejects_unsupported_wavelength() -> None:
    with pytest.raises(ValueError):
        laser_mpe(532.0, 0.25)
    with pytest.raises(ValueError):
        laser_mpe(1550.0, 0.25)


def test_laser_mpe_rejects_unsupported_duration() -> None:
    with pytest.raises(ValueError):
        laser_mpe(1064.0, 1.0)
    with pytest.raises(ValueError):
        laser_mpe(1064.0, 100.0)


def test_laser_mpe_source_is_populated() -> None:
    for wl in (1064.0, 520.0):
        for dur in (0.25, 10.0):
            mpe = laser_mpe(wl, dur)
            assert mpe.source, f"Missing source for ({wl}, {dur})"


def test_laser_mpe_intensity_limit_alias() -> None:
    mpe = laser_mpe(1064.0, 0.25)
    assert mpe.intensity_limit_w_per_m2() == mpe.mpe_w_per_m2()


# RF limit


def test_rf_limit_is_one_mw_per_cm2() -> None:
    assert RF_LIMIT_GENERAL_POPULATION.limit_mw_per_cm2 == pytest.approx(1.0)
    assert RF_LIMIT_GENERAL_POPULATION.limit_w_per_m2() == pytest.approx(10.0)


def test_rf_limit_source_mentions_fcc_and_icnirp() -> None:
    source = RF_LIMIT_GENERAL_POPULATION.source
    assert "FCC" in source
    assert "ICNIRP" in source


# laser_constraint in a HierarchicalModel


def test_laser_constraint_sat_at_low_intensity() -> None:
    model = HierarchicalModel()
    model.add_cluster(Cluster("beam", frozenset({"intensity"})))
    model.add_intra_cluster_constraint(laser_constraint("mpe_1064", "intensity", 1064.0))
    model.add_intra_cluster_constraint(
        # Add a lower bound on intensity so the cluster is not trivially
        # unbounded below; any positive intensity satisfies MPE at 25.5 W/m^2.
        __import__("app.verification.hierarchical", fromlist=["ConstraintEntry"]).ConstraintEntry(
            family_name="intensity_floor",
            variables=frozenset({"intensity"}),
            fn=lambda v: v["intensity"] >= z3.RealVal("1.0"),
        )
    )
    result = model.check()
    assert result.status == "sat"


def test_laser_constraint_unsat_when_intensity_forced_above_mpe() -> None:
    """The gate: an architecture that requires beam intensity above the
    MPE must be UNSAT by construction."""
    model = HierarchicalModel()
    model.add_cluster(Cluster("beam", frozenset({"intensity"})))
    model.add_intra_cluster_constraint(laser_constraint("mpe_1064", "intensity", 1064.0))
    from app.verification.hierarchical import ConstraintEntry

    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="intensity_required",
            variables=frozenset({"intensity"}),
            fn=lambda v: v["intensity"] >= z3.RealVal("100.0"),
        )
    )
    result = model.check()
    assert result.status == "unsat"
    assert "beam" in result.unsat_clusters


def test_laser_constraint_safety_margin_halves_limit() -> None:
    """With safety_margin=2, the encoded limit is half the raw MPE, so
    an intensity that satisfies the raw MPE may violate the margined
    constraint."""
    model = HierarchicalModel()
    model.add_cluster(Cluster("beam", frozenset({"intensity"})))
    model.add_intra_cluster_constraint(
        laser_constraint("mpe_margin", "intensity", 1064.0, safety_margin=2.0)
    )
    from app.verification.hierarchical import ConstraintEntry

    # 20 W/m^2 is below the raw 25.5 W/m^2 MPE but above the margined
    # 12.75 W/m^2 limit.
    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="intensity_20",
            variables=frozenset({"intensity"}),
            fn=lambda v: v["intensity"] >= z3.RealVal("20.0"),
        )
    )
    result = model.check()
    assert result.status == "unsat"


def test_laser_constraint_rejects_zero_margin() -> None:
    with pytest.raises(ValueError):
        laser_constraint("m", "intensity", 1064.0, safety_margin=0.0)
    with pytest.raises(ValueError):
        laser_constraint("m", "intensity", 1064.0, safety_margin=-1.0)


# rf_constraint


def test_rf_constraint_sat_at_low_power_density() -> None:
    model = HierarchicalModel()
    model.add_cluster(Cluster("rf", frozenset({"power_density"})))
    model.add_intra_cluster_constraint(rf_constraint("fcc_1310", "power_density"))
    from app.verification.hierarchical import ConstraintEntry

    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="floor",
            variables=frozenset({"power_density"}),
            fn=lambda v: v["power_density"] >= z3.RealVal("0.5"),
        )
    )
    result = model.check()
    assert result.status == "sat"


def test_rf_constraint_unsat_above_fcc_limit() -> None:
    model = HierarchicalModel()
    model.add_cluster(Cluster("rf", frozenset({"power_density"})))
    model.add_intra_cluster_constraint(rf_constraint("fcc_1310", "power_density"))
    from app.verification.hierarchical import ConstraintEntry

    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="demand",
            variables=frozenset({"power_density"}),
            fn=lambda v: v["power_density"] >= z3.RealVal("50.0"),
        )
    )
    result = model.check()
    assert result.status == "unsat"


def test_rf_constraint_rejects_zero_margin() -> None:
    with pytest.raises(ValueError):
        rf_constraint("m", "power_density", safety_margin=0.0)


# integration: laser + RF in one architecture


def test_joint_laser_and_rf_constraints_are_independent_clusters() -> None:
    """Laser intensity and RF power density are in different physical
    regions of the receiver, so they form two independent clusters.
    Each must satisfy its own MPE; the joint system is SAT only if
    both do."""
    model = HierarchicalModel()
    model.add_cluster(Cluster("laser_zone", frozenset({"laser_intensity"})))
    model.add_cluster(Cluster("rf_zone", frozenset({"rf_power_density"})))
    model.add_intra_cluster_constraint(laser_constraint("mpe_laser", "laser_intensity", 1064.0))
    model.add_intra_cluster_constraint(rf_constraint("mpe_rf", "rf_power_density"))
    from app.verification.hierarchical import ConstraintEntry

    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="laser_floor",
            variables=frozenset({"laser_intensity"}),
            fn=lambda v: v["laser_intensity"] >= z3.RealVal("5.0"),
        )
    )
    model.add_intra_cluster_constraint(
        ConstraintEntry(
            family_name="rf_floor",
            variables=frozenset({"rf_power_density"}),
            fn=lambda v: v["rf_power_density"] >= z3.RealVal("0.5"),
        )
    )
    result = model.check()
    assert result.status == "sat"
    assert len(result.cluster_results) == 2
