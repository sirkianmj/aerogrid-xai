"""Scientific gate under load (roadmap s11-7).

Claim: two POST /discovery/run requests with the same request body
return byte-identical responses, and both match a serial baseline.

This is not the s4-8 gate. s4-8 asserts in-process, single-threaded
determinism: same inputs -> same outputs, across two sequential calls
of the same Python functions. s11-7 asserts the same property across
the HTTP boundary, using the same invocation mechanism uvicorn uses.

Mechanism: httpx.AsyncClient over an in-process ASGITransport, driving
the app through its own async entry point. This mirrors how uvicorn
invokes the app: one event loop, one thread, requests scheduled by the
loop.

Why not ThreadPoolExecutor + TestClient
---------------------------------------

Two independent crashes were observed while developing this test.
Neither reflects an endpoint defect; both are artefacts of the
threaded test harness.

  1. Starlette's TestClient drives the ASGI app through
     ``anyio.from_thread.BlockingPortal``. Sharing one client across
     threads SIGSEGVs the interpreter. Constructing a fresh client per
     thread does not help: the two portals still funnel into the same
     app and the same process-global state.

  2. The Z3 Python bindings use a process-global context. Two threads
     concurrently building Z3 expressions produce
     ``Z3Exception: context mismatch`` (and, in some orderings, a hard
     crash). The failing line is in the architecture encoder, where a
     ``flow`` variable created in one thread's context is compared
     against a ``z3.RealVal`` created in another's.

The deployed endpoint never triggers either failure, because
``@router.post("/run")`` is ``async def`` and contains no ``await``.
Under single-worker uvicorn it runs on the event loop, one request at
a time, with no thread parallelism. The empirical record of concurrent
correctness is the load test: 13 runs at up to 128 concurrent HTTP
users, 0 failures, 0 exceptions (docs/LOAD_TEST_BASELINE.md).

If a future change moves any part of the discovery pipeline into
``run_in_threadpool`` or any other threaded execution path, the Z3
global-context issue becomes a real defect and this test must change
with it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi.testclient import TestClient

from app.main import app

# TestClient is used only for the serial sanity tests. It is not used
# for the concurrency assertions; see the module docstring.
_serial_client = TestClient(app)

_REQ: dict[str, Any] = {
    "population_size": 6,
    "n_generations": 3,
    "seed": 20261015,
    "min_nodes": 4,
    "max_nodes": 8,
    "max_links": 6,
    "use_conflict_directed": True,
}

_COMPARED_FIELDS = (
    "generation_stats",
    "hypervolume_history",
    "conflict_prone_table",
    "trace",
    "discovered",
)


def _run_serial() -> dict[str, Any]:
    r = _serial_client.post("/discovery/run", json=_REQ)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


async def _run_pair_concurrent() -> tuple[dict[str, Any], dict[str, Any]]:
    """Schedule two identical requests on one event loop via ASGI.

    Both requests are created with ``asyncio.gather`` before either
    completes, so they are in flight at the ASGI layer simultaneously.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        ra, rb = await asyncio.gather(
            c.post("/discovery/run", json=_REQ),
            c.post("/discovery/run", json=_REQ),
        )
    assert ra.status_code == 200, ra.text
    assert rb.status_code == 200, rb.text
    return ra.json(), rb.json()


def test_serial_baseline_is_itself_reproducible() -> None:
    """Two serial calls with identical bodies are identical. If this
    fails, the concurrent tests below cannot distinguish a concurrency
    defect from general nondeterminism."""
    a = _run_serial()
    b = _run_serial()
    assert a == b


def test_two_concurrent_requests_return_identical_bodies() -> None:
    """The s11-7 gate. Two requests scheduled concurrently on the app's
    event loop return equal response bodies field by field."""
    a, b = asyncio.run(_run_pair_concurrent())
    for key in _COMPARED_FIELDS:
        assert a[key] == b[key], f"field {key!r} differs between concurrent responses"
    assert a == b


def test_concurrent_responses_match_serial_baseline() -> None:
    """Both concurrent responses must match a serial response taken
    after them. Closes the failure mode where two concurrent responses
    agree with each other but diverge from the correct answer."""
    a, b = asyncio.run(_run_pair_concurrent())
    serial = _run_serial()
    for key in _COMPARED_FIELDS:
        assert a[key] == serial[key], f"concurrent response diverged from serial on {key!r}"
        assert b[key] == serial[key], f"concurrent response diverged from serial on {key!r}"


def test_different_seeds_produce_different_bodies() -> None:
    """Sanity: the endpoint is not returning a constant. If this fails,
    the identical-body assertions above are vacuous."""
    a = _run_serial()
    r2 = _serial_client.post("/discovery/run", json={**_REQ, "seed": _REQ["seed"] + 1})
    assert r2.status_code == 200
    b = r2.json()
    assert a["discovered"] != b["discovered"]
