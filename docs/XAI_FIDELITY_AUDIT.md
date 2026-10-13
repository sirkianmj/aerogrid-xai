# XAI Fidelity Audit — Tier 1 Trace, Tier 2 Isolation

**Audit date:** 2026-10-13
**Repository state:** `main` at commit `8c5ea98` (PR #83)
**Sprint task:** s9-4 (XAI fidelity audit)
**Related tasks:** s5-1 (Tier 1 core), s5-4 (static analyzer), s5-5 (explain)
**Deliverable:** this document; regression tests in
`backend/tests/test_tier1.py` and `backend/tests/test_xai_fidelity_audit.py`.

## 1. Claims under audit

Section 36.1 of the specification states three properties of the
two-tier controller:

1. **Trace fidelity.** Every action taken by the Tier 1 decision core
   carries an explanation that is, by construction, the literal
   computation path used to reach the decision.
2. **Explanation independence.** The explanation cannot be corrupted
   by Tier 2's internal opacity, because Tier 2 never selects an
   action.
3. **Static separation.** A build-time check enforces that no Tier 2
   function is reachable from an action interface without passing
   through a Tier 1 function.

This document certifies each claim against the current code and the
test suite, and records two findings (F-1, F-2) surfaced by the audit.

## 2. Scope

Modules under audit:

    backend/app/control/tier1.py             465 lines
    backend/app/control/tier2.py             270 lines
    backend/app/control/explain.py           258 lines
    backend/app/control/static_analyzer.py   216 lines

Test modules already in force:

    backend/tests/test_tier1.py              389 lines (+3 added this audit)
    backend/tests/test_tier2.py              330 lines
    backend/tests/test_explain.py            265 lines
    backend/tests/test_static_analyzer.py    286 lines

## 3. Method

Three lines of evidence:

1. **Source review** of the four modules named in section 2.
2. **Adversarial diagnostic** executed during this audit: four
   probes (baseline, non-floatable estimate, non-floatable candidate
   field, hostile extra estimate key).
3. **The existing test suite**, which is exercised in the same CI
   jobs as the whole backend (`backend` and `master-test`).

## 4. Structural argument for claim 1 (trace fidelity)

The fidelity property is enforced by the API's shape, not by a
convention. In `tier1.py`:

- A `SparseRuleList` exposes exactly one evaluation method:
  `score_and_trace(inputs, builder) -> float`. It returns the score
  **and** mutates the builder as it goes. There is no
  `evaluate(inputs)` path that returns a score without touching a
  trace builder.
- `TraceBuilder.record` is the only mutation point of the builder.
- `SparseRuleList.score_and_trace` calls `builder.record` exactly
  once per rule, in rule order, with the rule's own weight as the
  step weight when the rule matches (0.0 otherwise). The function's
  own return value is the sum of those same weights.
- `DecisionTrace` and its nested `TraceStep` are frozen dataclasses.
  The trace is immutable once produced.
- `explain.render(trace)` reads only `trace`'s fields. It cannot
  report a comparison the trace did not make, because it does not
  consult the rule list, the inputs, or any other state.

This makes fidelity a property of the code, not of the tests: any
future code path that produces a `DecisionTrace` must also have
produced the intermediate `record` calls that make up the trace.
There is no separate "explain" step that reconstructs an explanation
from a black-box output.

## 5. Evidence — adversarial diagnostic

Executed 2026-10-13 against `main` @ `8c5ea98`, before the F-1 patch
was applied. Candidates used the Section 15.5 worked example (UAV-32
battery 19%, UAV-18 battery 40%). Rule list was
`default_charge_rule_list()`.

    A. baseline:
       score = 15.5, sum_of_weights = 15.5, diff = 0, selected =
       charge_uav_32   [fidelity invariant holds]
    B. non-floatable estimate value:
       no exception, decision unchanged (charge_uav_32)
    C. non-floatable candidate field:
       **ValueError: could not convert string to float: 'oops'**
       [F-1, see section 6]
    D. extra estimate key "__action_override" with numeric value:
       no exception, decision unchanged

## 6. Findings

### F-1 — Malformed candidate values crash instead of being recorded as skipped

**Observed (pre-fix).** A candidate carrying a non-floatable extra
field (`{"extra_field": "not_a_number"}`) caused
`_sorted_observed` to raise `ValueError`, which escaped
`decide_charge_uav` and crashed the caller. The exception clause in
`SparseRuleList.score_and_trace` caught `KeyError` and `TypeError`
but not `ValueError`.

**Consequence.** A caller whose candidate dictionary carried any
non-numeric key — a legitimate possibility in an open data pipeline
— would lose the entire decision, not just that field. This
contradicts the docstring of the except clause, which claims to
handle "malformed input".

**Resolution (this PR).**

- `_sorted_observed` now filters non-floatable values instead of
  raising. Values a rule cannot consume do not appear in the trace's
  observed snapshot, which is correct: the trace records values the
  model consumed, not values present in the input.
- The except clause in `score_and_trace` extended to
  `(KeyError, TypeError, ValueError)`. A rule whose *consulted* value
  is malformed now records a `skipped` step rather than crashing.

Regression tests: `test_malformed_extra_field_does_not_crash_and_is_dropped_from_observed`
and `test_malformed_consulted_value_marks_rule_skipped_not_crash` in
`backend/tests/test_tier1.py`.

### F-2 — Estimate-vs-candidate merge order is undocumented but protective

**Observed.** `decide_charge_uav` merges inputs as
`{**estimates, **candidate}`. When a key is present in both, the
candidate's value wins. A Tier 2 estimate cannot silently override a
caller-supplied candidate value.

**Consequence.** This is the correct behavior for the two-tier
separation invariant: Tier 2 supplies numeric estimates to be
consumed by Tier 1, not to override Tier 1's view of the physical
input. But the behavior was neither documented nor tested.

**Resolution (this PR).**

- Documented in the docstring of `decide_charge_uav` (see code).
- Locked by `test_candidate_overrides_estimate_for_same_key` in
  `backend/tests/test_tier1.py` and by
  `test_estimates_cannot_override_candidate_across_sweep` in
  `backend/tests/test_xai_fidelity_audit.py`.

### F-3 — Trace does not label per-value provenance (documentation only)

**Observed.** A `TraceStep.observed` entry is a `(key, value)` pair.
The trace does not record whether the value came from the candidate
dict or from the `estimates` mapping, even though the two are merged
before evaluation.

**Consequence.** A reader can verify *what* value a rule consumed but
not *where* it came from. This is not a fidelity violation — the
trace is still a literal record of what the model computed — but it
is a limitation of the current trace format.

**Recommendation (not implemented in this PR).** If provenance ever
becomes a requirement, it can be added by extending `TraceStep` with
a `source: str` field set by `score_and_trace`. Doing so now would
expand the trace format without a consumer; the change is deferred.

### F-4 — Static analyzer ignores method calls (documentation only)

**Observed.** `static_analyzer._collect_direct_calls` records only
`ast.Call` nodes whose `func` is a bare `ast.Name`. Method calls
(`obj.method(...)`) are ignored. This is documented in the module
docstring.

**Consequence.** If a future Tier 2 class method ever calls a Tier 1
`decide_*` function via a method dispatch, the analyzer will not
detect it. The current code base does not contain such a call; this
is a coverage limitation to record.

**Recommendation (not implemented in this PR).** Extending the
analyzer to method calls is straightforward but requires a
name-resolution strategy for `self.method` and module-level `obj.method`.
The design decision — whether to resolve at the module level or at
the type level — deserves its own task.

## 7. Claim 2 — Tier 2 cannot corrupt the explanation

`tier2.py` exposes `estimate_*` functions that return
`(value, uncertainty_interval)` tuples (per Section 15.3). None of
those functions returns an action. Tier 1 receives those estimates as
plain numeric inputs; the traces recorded by `SparseRuleList` record
the *estimate values consumed by rules*, and the trace carries no
dependence on the estimates' internal correctness.

If a Tier 2 estimate is wrong, the corresponding rule's outcome is
wrong; but the trace still faithfully records *that the rule consumed
that value and produced that outcome*. Fidelity is preserved because
fidelity is a claim about the model's own arithmetic, not about
physical reality (Section 15.5 and Section 21's scope note, both of
which are surfaced by `render()` in every output).

The static analyzer enforces the structural half of this claim
(section 8). The behavioral half is a direct consequence of the API
shape (section 4).

## 8. Claim 3 — Static separation

`static_analyzer.analyze_default_package()` parses every `.py` file
under `app/control/`, builds a call graph keyed by top-level function
name, and reports every `estimate_*` function whose transitive
closure contains a `decide_*` function. The check runs under pytest
via `test_real_control_package_is_clean` and can be invoked directly
as `python -m app.control.static_analyzer`.

Run as of `8c5ea98`:

    static_analyzer: no two-tier violations found

The check is transitive (it uses BFS over the call graph, not a
name-based lookup), so an indirect path `estimate_A -> helper_B ->
decide_C` is caught. The check's documented limitation (F-4) is
method calls; no such call exists in the current code base.

## 9. Residual risks

R-1. **TraceStep.observed does not distinguish provenance** (F-3).
     Documented; deferred.

R-2. **Static analyzer ignores method calls** (F-4). Documented;
     deferred. No current violation.

R-3. **`default_charge_rule_list` weights are not calibrated against
     physical measurements.** The docstring says so explicitly; this
     is a test fixture, not a production rule set. The audit does not
     certify the rule list's outputs, only the trace's fidelity to
     whatever computation the rule list produces.

R-4. **Fidelity is by construction, not by independent
     verification.** The audit asserts the invariant holds across a
     sweep of random candidate/estimate pairs
     (`test_score_equals_sum_of_weights_across_sweep`). It does not
     prove fidelity for arbitrary future rule-list implementations;
     the code path that would introduce a fidelity violation (a
     second evaluation method that returns a score without touching
     the builder) does not exist today but could in principle be
     added by a future change. The suite would catch it: the sweep
     test uses the public API and would fail.

## 10. Certification

Within the scope of section 2, and against the code at `8c5ea98` plus
the F-1 patch merged as part of this PR:

- **Claim 1 (trace fidelity)** holds. The score returned by
  `score_and_trace` equals the sum of the recorded step weights to
  floating-point precision, for every candidate in a 100-point sweep
  and every rule configuration exercised. The rendering in
  `explain.render` reads only trace fields and cannot diverge.
- **Claim 2 (Tier 2 cannot corrupt)** holds. Tier 2 exposes only
  `estimate_*` functions returning value-and-interval tuples. Tier 1
  consumes them as plain inputs; the trace is faithful to whatever
  inputs are provided. Estimate-vs-candidate precedence is
  documented and tested (F-2).
- **Claim 3 (static separation)** holds. The transitive call-graph
  check reports zero violations on the current code base, and is
  exercised in CI.

Finding F-1 was the only defect surfaced by this audit; it is
remediated by the patch in this PR and by two regression tests.
Findings F-2 through F-4 are documentation and coverage notes;
resolutions are recorded above and, where deferred, the rationale is
stated.

Signed: Kian Mansouri Jamshidi
