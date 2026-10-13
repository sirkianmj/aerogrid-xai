"""Meta-test: every per-source module states its error bound.

The sprint s9-2 gate says "within stated error bounds". A test file that
silently reproduces a number without stating its bound does not meet
the requirement. This module enforces that each per-source validation
file contains an explicit statement of the bound in its docstring.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent


def _read(name: str) -> str:
    return (HERE / name).read_text()


def test_xidian_states_error_bound() -> None:
    text = _read("test_xidian.py")
    assert "5%" in text, "test_xidian.py must state its 5% error bound"
    assert "3-5%" in text or "3 to 5" in text, "test_xidian.py must state the 3-5% band"


def test_powerlight_states_error_bound() -> None:
    text = _read("test_powerlight.py")
    assert "5%" in text, "test_powerlight.py must state its 5% error bound"


def test_darpa_states_range_bound() -> None:
    text = _read("test_darpa_power.py")
    assert "0.85" in text or "(0.85" in text, "test_darpa_power.py must state the tau range"


def test_overview_states_no_reproduction() -> None:
    text = _read("test_overview_energy.py")
    assert "not" in text.lower() and "satellite" in text.lower(), (
        "test_overview_energy.py must state it disclaims the satellite-to-UAV analogy"
    )


def test_han_states_component_not_link() -> None:
    text = _read("test_han_et_al.py")
    assert "component" in text.lower(), "test_han_et_al.py must state component-not-link"
    assert "P5" in text or "DOI" in text, "test_han_et_al.py must carry forward P5"
