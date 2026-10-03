"""Build Notebook 02 - LEO vs. GEO visibility comparison.

Run once from the repo root:
    python scripts/build_notebook_02.py

Generates: notebooks/02_orbital_visibility.ipynb
"""

from pathlib import Path

import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# Notebook 02 - LEO vs. GEO Visibility Comparison

**Sprint:** S1 (Digital Twin Core: Orbital Mechanics & Geography)
**Roadmap task:** s1-6
**Specification reference:** Section 7.1 (Orbital Mechanics).

## Scientific gate

> LEO short windows, GEO persistent - both computed, not assumed.

## What this notebook does

1. Loads two real satellites from TLE fixtures: ISS (LEO) and a synthetic
   near-GEO satellite.
2. Computes the ISS's sub-satellite ground track and the GEO sub-satellite
   point.
3. Computes visibility windows from a ground node over a 24-hour period
   for both satellites, using the same SGP4 propagator and the same
   `visibility_windows` primitive.
4. Asserts the qualitative difference: LEO produces many short passes,
   GEO produces at most one long continuous window.

Every position is computed by SGP4 propagation. Nothing is hard-coded.
"""
))

cells.append(nbf.v4.new_markdown_cell("## Setup"))

cells.append(nbf.v4.new_code_cell(
"""import sys
from datetime import timedelta
from pathlib import Path

repo_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(repo_root / "backend"))

from app.physics.orbital import GroundNode, Satellite, visibility_windows

iss = Satellite.from_tle_file(repo_root / "backend/tests/fixtures/iss.tle")
geo = Satellite.from_tle_file(repo_root / "backend/tests/fixtures/geo.tle")

print(f"LEO  {iss.name}: period = {iss.period_seconds/60:.1f} min")
print(f"GEO  {geo.name}: period = {geo.period_seconds/60:.1f} min")
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Section 1 - GEO sub-satellite point

The GEO satellite's position at its TLE epoch determines its sub-satellite
longitude. We compute this from the SGP4 propagation, not from any stored
constant.
"""
))

cells.append(nbf.v4.new_code_cell(
"""geo_state = geo.at_utc(geo.epoch_utc)
print(f"GEO sub-satellite point at epoch:")
print(f"  lat = {geo_state.lat_deg:+.3f} deg")
print(f"  lon = {geo_state.lon_deg:+.3f} deg")
print(f"  alt = {geo_state.alt_km:.0f} km")
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Section 2 - Ground nodes

Two ground nodes:

- **Greenbelt, MD**: a mid-latitude station that sees ISS passes.
- **GEO sub-point**: a virtual ground station directly under the GEO
  satellite at epoch, so GEO should have persistent visibility.
"""
))

cells.append(nbf.v4.new_code_cell(
"""greenbelt = GroundNode("Greenbelt", 38.99, -76.84, 50.0)
geo_ground = GroundNode("GEO-subpoint", geo_state.lat_deg, geo_state.lon_deg, 0.0)

print(f"Greenbelt:    lat={greenbelt.lat_deg:+.2f}, lon={greenbelt.lon_deg:+.2f}")
print(f"GEO sub-point: lat={geo_ground.lat_deg:+.2f}, lon={geo_ground.lon_deg:+.2f}")
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Section 3 - LEO visibility windows over 24 hours

Compute visibility windows for the ISS over Greenbelt. Expect multiple
short passes.
"""
))

cells.append(nbf.v4.new_code_cell(
"""t_start = iss.epoch_utc
t_end = t_start + timedelta(hours=24)

leo_windows = visibility_windows(
    iss, greenbelt, t_start, t_end,
    step_seconds=30.0, min_elevation_deg=10.0,
)

print(f"LEO windows over 24 h: {len(leo_windows)}")
for i, w in enumerate(leo_windows):
    print(f"  pass {i+1}: duration {w.duration_seconds/60:5.1f} min, "
          f"peak elev {w.peak_elevation_deg:5.1f} deg")

leo_total = sum(w.duration_seconds for w in leo_windows)
leo_max = max((w.duration_seconds for w in leo_windows), default=0.0)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Section 4 - GEO visibility over 24 hours

Compute visibility windows for the GEO satellite over its sub-satellite
ground node. Expect at most one continuous window spanning the interval.
"""
))

cells.append(nbf.v4.new_code_cell(
"""geo_windows = visibility_windows(
    geo, geo_ground, t_start, t_end,
    step_seconds=120.0, min_elevation_deg=10.0,
)

print(f"GEO windows over 24 h: {len(geo_windows)}")
for i, w in enumerate(geo_windows):
    print(f"  window {i+1}: duration {w.duration_seconds/3600:5.2f} h, "
          f"peak elev {w.peak_elevation_deg:5.1f} deg")

geo_total = sum(w.duration_seconds for w in geo_windows)
"""
))

cells.append(nbf.v4.new_markdown_cell(
"""## Section 5 - Gate assertion

The gate is qualitative but firm:

- LEO must produce **multiple short windows** (>= 3 windows, each < 30 min).
- GEO must produce **one long window** or zero, with any window > 1 h.
- Both must be computed from real SGP4 propagation of the same TLEs used
  in every other test in the repository.
"""
))

cells.append(nbf.v4.new_code_cell(
"""print("Gate: LEO short windows, GEO persistent (both computed, not assumed)")
print("=" * 68)
print(f"LEO window count:       {len(leo_windows)} (require >= 3)")
print(f"LEO max window:         {leo_max/60:.1f} min (require < 30 min)")
print(f"GEO window count:       {len(geo_windows)} (require <= 1)")
print(f"GEO total visible time: {geo_total/3600:.2f} h (require > 1 h if nonzero)")
print()

assert len(leo_windows) >= 3, "LEO should produce multiple passes over 24 h"
assert leo_max < 1800.0, f"LEO max window {leo_max/60:.1f} min exceeds 30 min"
assert len(geo_windows) <= 1, "GEO should produce at most one persistent window"
if geo_windows:
    assert geo_total > 3600.0, f"GEO persistent window {geo_total/3600:.2f} h too short"
print("ALL GATES PASS")
"""
))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (aerogrid)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/02_orbital_visibility.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(cells)}")
