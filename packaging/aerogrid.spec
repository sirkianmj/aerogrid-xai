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

# pywebview and its dependencies. On macOS, pywebview uses pyobjc
# (Cocoa/WebKit). collect_all picks up the pywebview JS bridge files
# that PyInstaller misses by default.
webview_datas, webview_binaries, webview_hidden = collect_all("webview")
webview_datas += collect_data_files("webview")

# pyobjc frameworks required on macOS. collect_all for each so the
# compiled .so files ship.
pyobjc_frameworks = ("objc", "Foundation", "AppKit", "WebKit", "Quartz", "Cocoa")
pyobjc_datas = []
pyobjc_binaries = []
pyobjc_hidden = []
for fw in pyobjc_frameworks:
    d, b, h = collect_all(fw)
    pyobjc_datas += d
    pyobjc_binaries += b
    pyobjc_hidden += h

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
    binaries=z3_binaries + z3_dylibs + webview_binaries + pyobjc_binaries,
    datas=z3_datas + skyfield_datas + tle_datas + frontend_datas
        + webview_datas + pyobjc_datas,
    hiddenimports=z3_hidden + webview_hidden + pyobjc_hidden + [
        "webview.platforms.cocoa",
        "bottle",
        "proxy_tools",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib.tests", "numpy.tests", "scipy.tests"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# console=False on macOS produces a windowed app that does not
# open a Terminal when launched from Finder. On Windows, console=False
# similarly suppresses the console window.
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
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="aerogrid-desktop",
)

# macOS .app bundle. Wraps the COLLECT output in a proper
# AeroGrid-XAI.app that Finder treats as an application (draggable to
# /Applications, has the icon, has a bundle identifier).
#
# The entrypoint opens a pywebview window (Cocoa/WebKit on macOS) and
# starts FastAPI on an OS-chosen free port in a background thread.
# Closing the window exits the process.
#
# The BUNDLE step is skipped on non-macOS platforms. PyInstaller's
# BUNDLE is macOS-only; on Linux and Windows this section is a no-op
# and dist/aerogrid-desktop/ remains the deliverable.
import sys as _sys
if _sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AeroGrid-XAI.app",
        icon=str(REPO / "packaging" / "aerogrid.icns"),
        bundle_identifier="com.forgex4.aerogrid",
        info_plist={
            "CFBundleName": "AeroGrid-XAI",
            "CFBundleDisplayName": "AeroGrid-XAI",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.developer-tools",
            # App Transport Security: the app loads http://localhost
            # (not https) inside WKWebView. macOS blocks plain HTTP by
            # default; these exceptions allow only local traffic.
            "NSAppTransportSecurity": {
                "NSAllowsLocalNetworking": True,
                "NSExceptionDomains": {
                    "localhost": {
                        "NSExceptionAllowsInsecureHTTPLoads": True,
                        "NSIncludesSubdomains": True,
                    },
                    "127.0.0.1": {
                        "NSExceptionAllowsInsecureHTTPLoads": True,
                    },
                },
            },
        },
    )
