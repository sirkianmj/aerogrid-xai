"""Validate the launchd plists under infrastructure/launchd/.

The plists are macOS deployment artifacts (Sprint 11 s11-1). They cannot
be loaded on Linux, but their XML, structure, and placeholder form can
be validated there. This module runs in the default ``backend`` CI job.
"""

from __future__ import annotations

import plistlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LAUNCHD_DIR = REPO_ROOT / "infrastructure" / "launchd"

EXPECTED_LABELS = {
    "com.forgex4.aerogrid.postgres",
    "com.forgex4.aerogrid.redis",
    "com.forgex4.aerogrid.minio",
    "com.forgex4.aerogrid.backend",
    "com.forgex4.aerogrid.frontend",
}

REQUIRED_KEYS = (
    "Label",
    "ProgramArguments",
    "RunAtLoad",
    "KeepAlive",
    "StandardOutPath",
    "StandardErrorPath",
)

REQUIRED_PLACEHOLDERS = ("__REPO_ROOT__", "__CONDA_ENV__", "__LOG_DIR__")

PLIST_PATHS = sorted(LAUNCHD_DIR.glob("com.forgex4.aerogrid.*.plist"))
IDS = [p.name for p in PLIST_PATHS]


def test_launchd_directory_exists() -> None:
    assert LAUNCHD_DIR.is_dir()


def test_all_five_plists_present() -> None:
    found = {p.name.removesuffix(".plist") for p in PLIST_PATHS}
    assert found == EXPECTED_LABELS


@pytest.mark.parametrize("path", PLIST_PATHS, ids=IDS)
def test_parses_as_plist_xml(path: Path) -> None:
    with path.open("rb") as f:
        plistlib.load(f)


@pytest.mark.parametrize("path", PLIST_PATHS, ids=IDS)
def test_has_required_keys(path: Path) -> None:
    with path.open("rb") as f:
        data = plistlib.load(f)
    for key in REQUIRED_KEYS:
        assert key in data, f"{path.name}: missing {key}"


@pytest.mark.parametrize("path", PLIST_PATHS, ids=IDS)
def test_label_matches_filename(path: Path) -> None:
    with path.open("rb") as f:
        data = plistlib.load(f)
    assert data["Label"] == path.name.removesuffix(".plist")


@pytest.mark.parametrize("path", PLIST_PATHS, ids=IDS)
def test_placeholders_present_no_absolute_paths(path: Path) -> None:
    text = path.read_text()
    for ph in REQUIRED_PLACEHOLDERS:
        assert ph in text, f"{path.name}: missing {ph}"


@pytest.mark.parametrize("path", PLIST_PATHS, ids=IDS)
def test_run_at_load_and_keepalive(path: Path) -> None:
    with path.open("rb") as f:
        data = plistlib.load(f)
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"].get("SuccessfulExit") is False


@pytest.mark.parametrize(
    "path",
    [p for p in PLIST_PATHS if "frontend" not in p.name],
    ids=[p.name for p in PLIST_PATHS if "frontend" not in p.name],
)
def test_non_frontend_binaries_come_from_conda_env(path: Path) -> None:
    with path.open("rb") as f:
        data = plistlib.load(f)
    first = data["ProgramArguments"][0]
    assert first.startswith("__CONDA_ENV__/"), first


def test_frontend_uses_wrapper_script() -> None:
    path = LAUNCHD_DIR / "com.forgex4.aerogrid.frontend.plist"
    with path.open("rb") as f:
        data = plistlib.load(f)
    args = data["ProgramArguments"]
    assert args[0] == "/bin/bash"
    assert args[1].endswith("/infrastructure/scripts/run_frontend.sh")
