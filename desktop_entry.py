"""PyInstaller entrypoint for the AeroGrid-XAI desktop bundle.

Proof-of-concept. Starts FastAPI on a fixed port, serves the built
frontend at /, prints a ready line. For the POC, no pywebview, no
window, no SQLite migration — this proves only that PyInstaller can
freeze the backend with all of its scientific dependencies.

Usage (frozen):
    ./aerogrid-desktop
Usage (dev):
    python3 desktop_entry.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Frozen builds unpack to sys._MEIPASS; source runs use the repo root.
if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)
else:
    ROOT = Path(__file__).resolve().parent

# Import the FastAPI app. Needs backend/ on sys.path.
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.staticfiles import StaticFiles  # noqa: E402
from app.main import app  # noqa: E402

# Serve the built frontend at / if present.
frontend_dir = ROOT / "frontend_dist"
if frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


def main() -> None:
    import uvicorn

    port = int(os.environ.get("AEROGRID_PORT", "8000"))
    print(f"AeroGrid-XAI desktop entrypoint listening on http://127.0.0.1:{port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
