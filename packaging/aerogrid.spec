# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AeroGrid-XAI desktop proof-of-concept.

Key things this spec does that the default would miss:
  - collects all of z3 (shared library + Python bindings)
  - collects Skyfield's .npz data files
  - bundles the TLE fixtures so app.physics.catalog can read them
  - bundles frontend/dist so the entrypoint can serve it
  - adds backend/ to pathex so `import app` works
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

REPO = Path(SPECPATH).resolve().parent
BACKEND = REPO / "backend"
FRONTEND_DIST = REPO / "frontend" / "dist"

# Z3: native library + Python bindings + all submodules.
z3_datas, z3_binaries, z3_hidden = collect_all("z3")

# The conda-forge z3-solver ships libz3.dylib in the env's lib/
# directory, not inside the Python package. collect_all only sees
# the Python package, so the shared library must be added explicitly.
# All three names are bundled so the loader finds whichever name
# z3core.py searches for.
import os as _os
_ENV_LIB = _os.path.expanduser("~/miniforge3/envs/aerogrid/lib")
z3_dylibs = [
    (_os.path.join(_ENV_LIB, "libz3.dylib"), "."),
    (_os.path.join(_ENV_LIB, "libz3.5.1.dylib"), "."),
    (_os.path.join(_ENV_LIB, "libz3.5.1.0.0.dylib"), "."),
]

# Skyfield: .npz ephemeris data files that PyInstaller misses.
skyfield_datas = collect_data_files("skyfield")

# TLE fixtures. Kept at the same relative path the source uses, so
# Path(__file__).parent / "data" / "tle" resolves the same in both modes.
tle_datas = [
    (str(BACKEND / "app" / "physics" / "data" / "tle" / name), "app/physics/data/tle")
    for name in ("geo.tle", "iss.tle", "vanguard_r3.tle")
]

# Frontend static build.
frontend_datas = [(str(FRONTEND_DIST), "frontend_dist")] if FRONTEND_DIST.is_dir() else []

a = Analysis(
    [str(REPO / "desktop_entry.py")],
    pathex=[str(BACKEND)],
    binaries=z3_binaries + z3_dylibs,
    datas=z3_datas + skyfield_datas + tle_datas + frontend_datas,
    hiddenimports=z3_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib.tests", "numpy.tests", "scipy.tests"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="aerogrid-desktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="aerogrid-desktop",
)
