"""Scientific gate s1-7: no hard-coded orbital positions.

Combines a static AST audit of app/physics/orbital.py with functional
tests that verify orbital state is a deterministic, time-varying function
of the SGP4 propagator and never a hard-coded constant.
"""

import ast
from datetime import timedelta
from pathlib import Path

import pytest

from app.physics.orbital import Satellite

FIXTURE = Path(__file__).parent / "fixtures" / "iss.tle"
ORBITAL_SOURCE = Path(__file__).parent.parent / "app" / "physics" / "orbital.py"


@pytest.fixture
def iss() -> Satellite:
    return Satellite.from_tle_file(FIXTURE)


def _attribute_name(target: ast.expr) -> str | None:
    """Return the attribute name if target is an ast.Attribute.

    Bare ast.Name targets (e.g. dataclass field declarations such as
    ``alt_m: float = 0.0``) return None. Only attribute targets like
    ``self.alt_m = 400_000.0`` indicate a hard-coded satellite state.
    """
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _collect_hardcoded_state(source: str) -> list[tuple[int, str, object]]:
    """Return (lineno, attribute, value) for any hardcoded numeric
    assignment to lat_deg, lon_deg, or alt_m on an attribute."""
    tree = ast.parse(source)
    suspicious: list[tuple[int, str, object]] = []

    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None

        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue

        if value is None:
            continue
        if not isinstance(value, ast.Constant):
            continue
        if not isinstance(value.value, (int, float)):
            continue

        for target in targets:
            name = _attribute_name(target)
            if name in ("lat_deg", "lon_deg", "alt_m"):
                suspicious.append((node.lineno, name, value.value))

    return suspicious


def test_orbital_source_has_no_hardcoded_geodetic_state() -> None:
    """AST audit: no literal numeric assignment to lat_deg, lon_deg, or
    alt_m attributes in the orbital module. Such an assignment would
    indicate a hard-coded geodetic state."""
    source = ORBITAL_SOURCE.read_text()
    suspicious = _collect_hardcoded_state(source)
    assert not suspicious, f"Hard-coded geodetic state detected in orbital.py: {suspicious}"


def test_audit_detects_a_synthetic_violation() -> None:
    """Meta-test: the AST audit must flag a synthetic hardcoded state,
    so that a future regression cannot silently break the audit."""
    synthetic = (
        "class Fake:\n"
        "    def __init__(self):\n"
        "        self.lat_deg = 45.0\n"
        "        self.lon_deg = -122.0\n"
        "        self.alt_m = 400_000.0\n"
    )
    suspicious = _collect_hardcoded_state(synthetic)
    assert len(suspicious) == 3, f"Audit missed synthetic violations: {suspicious}"
    names = {name for _, name, _ in suspicious}
    assert names == {"lat_deg", "lon_deg", "alt_m"}


def test_audit_ignores_dataclass_field_defaults() -> None:
    """Meta-test: the AST audit must NOT flag dataclass field defaults,
    which are Name targets, not Attribute targets."""
    synthetic = (
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Foo:\n"
        "    lat_deg: float = 0.0\n"
        "    lon_deg: float = 0.0\n"
        "    alt_m: float = 0.0\n"
    )
    suspicious = _collect_hardcoded_state(synthetic)
    assert suspicious == [], f"Audit falsely flagged dataclass defaults: {suspicious}"


def test_satellite_state_is_deterministic(iss: Satellite) -> None:
    """Same time -> same state, every time."""
    t = iss.epoch_utc + timedelta(hours=1)
    s1 = iss.at_utc(t)
    s2 = iss.at_utc(t)
    assert s1.lat_deg == s2.lat_deg
    assert s1.lon_deg == s2.lon_deg
    assert s1.alt_m == s2.alt_m


def test_satellite_state_varies_meaningfully_with_time(iss: Satellite) -> None:
    """Different times -> different lat/lon. Confirms the state is not a
    hard-coded constant."""
    t0 = iss.epoch_utc
    samples = [iss.at_utc(t0 + timedelta(minutes=5 * i)) for i in range(12)]
    lats = [s.lat_deg for s in samples]
    lons = [s.lon_deg for s in samples]

    assert max(lats) - min(lats) > 20.0, "Latitude barely varies over 1 hour"
    assert max(lons) - min(lons) > 20.0, "Longitude barely varies over 1 hour"


def test_satellite_state_is_never_null_island(iss: Satellite) -> None:
    """State never coincidentally equals (0, 0) - a fallback signature."""
    t0 = iss.epoch_utc
    for i in range(12):
        s = iss.at_utc(t0 + timedelta(minutes=5 * i))
        assert not (s.lat_deg == 0.0 and s.lon_deg == 0.0), (
            "State matches null island - possible hard-coded fallback"
        )
        assert s.alt_m > 100_000.0, f"Altitude {s.alt_m} m below any plausible orbital value"
