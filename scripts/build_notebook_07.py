"""Build Notebook 07 - Tier 1 explanation fidelity test."""

from pathlib import Path

import nbformat as nbf

NB = nbf.v4.new_notebook()
CELLS = []


def md(text: str) -> None:
    CELLS.append(nbf.v4.new_markdown_cell(text))


def code(text: str) -> None:
    CELLS.append(nbf.v4.new_code_cell(text))


md('''# Notebook 07 - Tier 1 explanation fidelity test

**Sprint:** S5 (Two-Tier XAI Controller)
**Roadmap task:** s5-6, and the s5-7 invariant demonstration.

## Scientific gate

> Fidelity score = 1.0 (by construction); Tier 2 opacity cannot corrupt it.

## What this notebook demonstrates

1. A Tier 1 decision runs on a synthetic UAV charge-selection problem.
2. The trace is verified to be a *literal* computation path: the sum
   of step weights equals the reported score, and a re-run of the
   same evaluation produces the same trace.
3. A counterfactual is computed exactly by rule ablation.
4. The static analyzer confirms the two-tier invariant: no Tier 2
   function reaches any Tier 1 action interface.

Fidelity is 1.0 by construction because the trace is produced as a
byproduct of evaluation. There is no reconstruction step, so there is
nothing to be infaithful. The final section runs the AST-based static
analyzer against the real `app.control` package to confirm the
invariant on the current repository state.
''')

md('## Setup')

code('''%matplotlib inline

import sys
from pathlib import Path

repo_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(repo_root / "backend"))

from app.control.explain import (
    counterfactuals_to_text,
    render,
    rule_ablation_counterfactuals,
    to_structured_dict,
)
from app.control.static_analyzer import analyze_default_package
from app.control.tier1 import (
    DecisionKind,
    SparseRuleList,
    decide_charge_uav,
    default_charge_rule_list,
)

print("Setup complete.")
''')

md('''## Section 1 - A Tier 1 decision

Four UAVs, different battery, mission priority, network centrality,
and thermal headroom. The rule list is the demonstration fixture from
`tier1.py`.
''')

code('''rule_list = default_charge_rule_list()

candidates = [
    {
        "uav_id": 1.0,
        "battery_pct": 15.0,
        "mission_priority": 0.4,
        "network_centrality": 0.2,
        "coverage_contribution": 0.01,
        "workload_urgency": 0.2,
        "thermal_headroom_c": 25.0,
        "atmospheric_factor": 0.9,
        "beam_alignment": 0.95,
        "transfer_loss": 0.10,
    },
    {
        "uav_id": 32.0,
        "battery_pct": 19.0,
        "mission_priority": 0.9,
        "network_centrality": 0.8,
        "coverage_contribution": 0.084,
        "workload_urgency": 0.9,
        "thermal_headroom_c": 38.0,
        "atmospheric_factor": 0.95,
        "beam_alignment": 0.94,
        "transfer_loss": 0.11,
    },
    {
        "uav_id": 18.0,
        "battery_pct": 25.0,
        "mission_priority": 0.5,
        "network_centrality": 0.3,
        "coverage_contribution": 0.02,
        "workload_urgency": 0.3,
        "thermal_headroom_c": 40.0,
        "atmospheric_factor": 0.85,
        "beam_alignment": 0.90,
        "transfer_loss": 0.14,
    },
    {
        "uav_id": 45.0,
        "battery_pct": 40.0,
        "mission_priority": 0.6,
        "network_centrality": 0.5,
        "coverage_contribution": 0.04,
        "workload_urgency": 0.5,
        "thermal_headroom_c": 35.0,
        "atmospheric_factor": 0.88,
        "beam_alignment": 0.92,
        "transfer_loss": 0.12,
    },
]

trace = decide_charge_uav(candidates, rule_list)
print(f"Selected: {trace.selected_action}")
print(f"Decision kind: {trace.decision_kind.value}")
''')

md('''## Section 2 - Trace fidelity is by construction

The operational form of "fidelity = 1.0" is: the sum of step weights
recorded in the trace equals the score the model returned, and a
second run of the exact same evaluation produces a bit-identical
trace.
''')

code('''sum_of_weights = sum(step.weight for step in trace.steps)
print(f"Score from evaluation:      {trace.score:+.6f}")
print(f"Sum of step weights:        {sum_of_weights:+.6f}")
print(f"Difference:                 {trace.score - sum_of_weights:+.2e}")
assert abs(trace.score - sum_of_weights) < 1e-12, "Trace is not faithful"

trace2 = decide_charge_uav(candidates, rule_list)
assert trace == trace2, "Trace is not deterministic across runs"
print()
print("Fidelity check: PASS")
print("Determinism check: PASS")
''')

md('''## Section 3 - The trace as rendered text (Section 15.5 format)

The rendering is a pure function of the trace and adds no
information. It cannot diverge from the trace because it reads only
the trace's own fields.
''')

code('''print(render(trace))
''')

md('''## Section 4 - Structured form

The structured dict is what a UI or API consumes. It carries the
Section 21 epistemic tag.
''')

code('''import json
structured = to_structured_dict(trace)
print(f"epistemic_tag:     {structured['epistemic_tag']}")
print(f"decision:          {structured['decision']}")
print(f"n_primary_reasons: {len(structured['primary_reasons'])}")
print(f"n_consulted:       {len(structured['consulted_rules'])}")
print(f"confidence:        {structured['confidence']:.3f}")
print()
print("First three primary reasons:")
for r in structured["primary_reasons"][:3]:
    print(f"  {r['label']} (weight {r['weight']:+.2f})")
''')

md('''## Section 5 - Counterfactuals by rule ablation

For each rule that fired on the winner, the decision is re-run with
that single rule disabled. The outcome is an exact consequence of
the model's arithmetic (Section 26).
''')

code('''cfs = rule_ablation_counterfactuals(trace, rule_list, candidates)
print(counterfactuals_to_text(cfs))
''')

md('''## Section 6 - The two-tier invariant, verified by static analysis

Section 36.1 defines "Tier 2 never selects an action" as a hard
architectural invariant enforced by a build-time static analyzer.
The analyzer in `app.control.static_analyzer` parses every Python
file under the control package, builds a call graph of top-level
functions, and reports any `estimate_*` function that can transitively
reach any `decide_*` function.
''')

code('''violations = analyze_default_package()
if violations:
    for v in violations:
        path_str = " -> ".join(v.path)
        print(f"VIOLATION: {v.source_file}:{v.source_line} -> {path_str}")
    raise AssertionError(f"{len(violations)} two-tier violations found")

print(f"Static analyzer: 0 violations on the control package")
print("Tier 2 never reaches decide_*: verified")
''')

md('''## Section 7 - Summary

The three properties demonstrated above constitute the s5-6 and s5-7
gates:

- **Fidelity = 1.0 by construction.** The sum of step weights equals
  the reported score, and the trace is reproduced bit-for-bit on a
  second run.
- **Counterfactuals are exact.** Rule ablation re-runs the actual
  Tier 1 evaluation path; the reported would-select is a literal
  consequence of the model's arithmetic, not a statistical
  approximation.
- **The two-tier invariant is statically verified.** The AST-based
  analyzer confirms that no `estimate_*` function in `app.control`
  can transitively reach any `decide_*` function. Tier 2 opacity
  cannot corrupt the Tier 1 explanation because Tier 2 never
  selects an action.
''')

code('''print("Notebook 07 - Tier 1 explanation fidelity")
print("=" * 60)
print(f"Decision:                 {trace.selected_action}")
print(f"Number of trace steps:    {len(trace.steps)}")
print(f"Number of matched rules:  {sum(1 for s in trace.steps if s.result == 'match')}")
print(f"Score:                    {trace.score:+.6f}")
print(f"Confidence:               {trace.confidence:.3f}")
print(f"Counterfactuals computed: {len(cfs)}")
print(f"Counterfactuals flipping: {sum(1 for c in cfs if c.changed)}")
print(f"Static analyzer:          clean")
print()
print("ALL GATES PASS")
''')

NB["cells"] = CELLS
NB["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (aerogrid)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.12"},
}

out = Path("notebooks/07_tier1_fidelity.ipynb")
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(NB, str(out))
print(f"Wrote {out}")
print(f"Cells: {len(CELLS)}")
