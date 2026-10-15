# Desktop packaging

Proof-of-concept packaging of AeroGrid-XAI as a frozen standalone
binary. Uses PyInstaller to bundle the FastAPI backend, the scientific
stack (numpy, scipy, Z3, Skyfield), the TLE fixtures, and the built
frontend into one self-contained directory.

## Status

**Proof of concept only.** Verified on macOS arm64: the frozen binary
starts, binds a port, and answers three probes:

    GET  /health          -> 200 {"status":"healthy"}
    GET  /mission/state   -> 200 (Skyfield)
    POST /discovery/run   -> 200 (Z3)

It has **not** been verified on Windows. It does **not** produce a
`.app` bundle (the output is a folder with an executable inside). The
SaaS layer (`backend/app/saas/`) still expects PostgreSQL and Redis;
the three probes above do not touch it, but any `/auth/*` or `/saas/*`
call will fail unless those services are running.

## Files

    desktop_entry.py                entrypoint (repo root)
    packaging/aerogrid.spec         PyInstaller spec
    packaging/build_macos.sh        macOS build script
    packaging/aerogrid-icon-source.png  master icon (2048x2048)
    packaging/aerogrid.icns         macOS icon (derived)
    packaging/requirements-desktop.txt  build-time deps

## Build

    bash packaging/build_macos.sh

Produces `dist/aerogrid-desktop/`. Run with:

    ./dist/aerogrid-desktop/aerogrid-desktop

Then visit `http://127.0.0.1:8000/`.

## Why the spec file looks the way it does

Two dependencies are missed by PyInstaller's default analysis and are
collected explicitly:

- **Z3 native library.** The conda-forge `z3-solver` package ships
  `libz3.dylib` in the environment's `lib/` directory, not inside the
  Python package. `collect_all("z3")` only sees the Python package, so
  the shared library is added explicitly in the spec.

- **Skyfield ephemeris data.** Skyfield reads `.npz` files at runtime
  that PyInstaller does not collect by default. `collect_data_files`
  handles this.

Both omissions produce runtime crashes, not build-time failures.
`libz3.dylib` missing produces `Z3Exception: libz3.dylib not found`;
Skyfield missing produces a `FileNotFoundError` on first propagation.
