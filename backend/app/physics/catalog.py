"""Satellite catalog.

Loads TLE files from the packaged data directory and caches the parsed
Satellite objects. A production deployment would ingest current TLEs
from Celestrak, Space-Track, or an equivalent source; the three TLEs
packaged here are demonstration records and their epochs are fixed.

Catalog keys are the TLE filename stems: iss, geo, vanguard_r3. The
catalog is loaded lazily on first access and cached for the lifetime of
the process; if a TLE is updated on disk while the process is running,
restart the process or call ``reset_catalog_cache``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.physics.orbital import Satellite

_DATA_DIR = Path(__file__).resolve().parent / "data" / "tle"


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Satellite]:
    """Return the loaded Satellite catalog, keyed by filename stem."""
    out: dict[str, Satellite] = {}
    for path in sorted(_DATA_DIR.glob("*.tle")):
        out[path.stem] = Satellite.from_tle_file(path)
    return out


def list_satellite_keys() -> tuple[str, ...]:
    """Return every available satellite key, sorted."""
    return tuple(sorted(_catalog().keys()))


def get_satellite(key: str) -> Satellite:
    """Return the Satellite for a key.

    Raises:
        KeyError if the key is not present. Callers on the HTTP layer
        catch this and translate it to a 404.
    """
    catalog = _catalog()
    if key not in catalog:
        raise KeyError(key)
    return catalog[key]


def reset_catalog_cache() -> None:
    """Clear the catalog cache. Used by tests after fixture updates."""
    _catalog.cache_clear()
