"""Z3 process-global context contract (post-s11-7 follow-up).

Background
----------

The s11-7 concurrency test found that two threads building Z3
expressions can raise ``Z3Exception: context mismatch``. Direct
inspection (see the recon scripts in the s11-7 PR body) falsified the
initial hypothesis that Z3's context is per-thread. The mechanism is a
first-touch race on a process-global singleton:

    z3.main_ctx()        # process-global, cached after first call
    # Two threads calling this in parallel before either initialises
    # get *different* contexts. After any thread has called it once,
    # every subsequent call from any thread returns the same context.

The fix lives at the FastAPI import boundary: ``app.main`` calls
``z3.main_ctx()`` once, synchronously, before any request handler can
run. That removes the race for every process that goes through the
app entry point.

This test asserts the invariant holds. It does not re-prove Z3's
internal behaviour; it asserts the *observable contract* the pipeline
depends on.

Pre-registered acceptance criteria for the eventual full per-context
fix (deferred — not part of this change)
----------------------------------------------------

The current fix makes the single-threaded pipeline safe by removing
the first-touch race. It does *not* make the pipeline safe if a future
change moves Z3 work into a thread pool. That full fix requires
passing an explicit ``z3.Context()`` instance to every Z3 call site
across ``app/verification/*`` and ``app/discovery/*`` (~60 sites). The
acceptance criteria for that fix, declared now so it is judged against
a bar declared before it is written:

  1. Every ``z3.Real``, ``z3.RealVal``, ``z3.Bool``, ``z3.BoolVal``,
     ``z3.And``, ``z3.If``, ``z3.Solver`` construction passes an
     explicit ``ctx=`` argument.
  2. A single ``z3.Context`` instance is created per pipeline run and
     threaded through encoder -> solver -> unsat -> attribution.
  3. ``test_two_concurrent_requests_return_identical_bodies`` passes
     when the ASGI app is invoked from a real thread pool (not only
     from the event loop).
  4. No regression in ``test_discovery_determinism.py``,
     ``test_h9_convergence.py``, or ``test_fuzz_soundness.py``.
  5. The benchmark suite (``backend/tests/scientific_validation/``)
     reports the same numeric results before and after.

Until criterion 5 is met, the fix is not complete. The invariants
above are what "complete" means.
"""

from __future__ import annotations

import asyncio
import threading

import httpx
import z3

from app.main import app  # import for the side effect that inits Z3's global context


def test_main_context_is_stable_across_threads_after_import() -> None:
    """After importing ``app.main``, every thread sees one context."""
    ctx_ids: dict[int, int] = {}
    barrier = threading.Barrier(4)

    def worker(i: int) -> None:
        barrier.wait()
        ctx_ids[i] = id(z3.main_ctx())

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    distinct = set(ctx_ids.values())
    assert len(distinct) == 1, (
        f"z3.main_ctx() returned {len(distinct)} distinct contexts across "
        f"threads after app.main import: {ctx_ids}. The force-init in "
        f"backend/app/main.py is missing or was removed."
    )


def test_encoder_output_lives_in_main_context() -> None:
    """encode_architecture binds every constraint to z3.main_ctx()."""
    from app.discovery.generator import GeneratorConfig, generate_architecture
    from app.verification.architecture_encoder import encode_architecture

    arch = generate_architecture(GeneratorConfig(min_nodes=4, max_nodes=6, seed=42))
    constraints = encode_architecture(arch)
    assert constraints, "encoder produced no constraints for a valid architecture"

    main = z3.main_ctx()
    for fc in constraints:
        assert fc.expression.ctx is main, (
            f"constraint {fc.family_name!r} is bound to a context that is not z3.main_ctx()"
        )


def test_concurrent_requests_do_not_recreate_the_context() -> None:
    """Two concurrent POST /discovery/run requests complete cleanly, and
    the Z3 main context is the same object before and after.

    If the context had been re-created by either request (the first-touch
    race), cross-thread arithmetic would raise ``Z3Exception: context
    mismatch`` and the request would return 500 rather than 200. Both
    responses succeeding is the observable form of the invariant.
    """
    ctx_before = z3.main_ctx()

    async def go() -> tuple[int, int]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            body = {"population_size": 4, "n_generations": 2, "seed": 20261015}
            ra, rb = await asyncio.gather(
                client.post("/discovery/run", json=body),
                client.post("/discovery/run", json=body),
            )
        return ra.status_code, rb.status_code

    codes = asyncio.run(go())
    assert codes == (200, 200), (
        f"concurrent requests returned {codes}; a 500 would indicate a cross-context Z3 error"
    )
    assert z3.main_ctx() is ctx_before, "z3.main_ctx() changed identity during the concurrent run"
