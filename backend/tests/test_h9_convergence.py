"""H9 convergence test for conflict-directed vs. random mutation.

Roadmap task s4-5: Conflict-directed mutation.
Gate: Bias toward changing conflict-prone features; convergence rate
> random mutation (H9 test).

H9 (spec Section 27): closed-loop CLEAR-D discovers architectures with
higher verified feasibility than generative search without unsat-core
feedback, at equal computational budget.

The test below isolates the mutation step. On a synthetic problem
where the sole source of infeasibility is a single designated
"bottleneck" link, we compare:

  - ConflictDirectedMutator, which reads the ConflictProneTable from
    the UNSAT core and targets the marked link.
  - RandomMutator, which picks operator and target uniformly.

Both run for the same number of mutation steps. The conflict-directed
mutator reaches SAT much more often. That is the H9 claim in its
operational form.
"""

from __future__ import annotations

import random

import z3

from app.discovery.attribution import (
    ConflictProneTable,
    FeatureConstraint,
    FeatureKind,
    GrammarFeature,
    attribute_and_mark,
)
from app.discovery.generator import (
    LINK_PARAM_RANGES,
    GeneratorConfig,
    generate_architecture,
)
from app.discovery.grammar import (
    Architecture,
    LinkInstance,
    Terminal,
)
from app.discovery.mutation import (
    MutationConfig,
    mutate_conflict_directed,
    mutate_random,
)


def _make_initial_architecture_and_bottleneck(seed: int) -> tuple[Architecture, str]:
    """Generate an architecture whose first link is forced to be a
    Laser_Link. Return the architecture and the bottleneck link_id."""
    gen_config = GeneratorConfig(min_nodes=6, max_nodes=8, max_links=12, seed=seed)
    arch = generate_architecture(gen_config)
    first = arch.links[0]
    rng = random.Random(seed + 500_000)
    new_params = {
        name: rng.uniform(lo, hi)
        for name, (lo, hi) in LINK_PARAM_RANGES[Terminal.LASER_LINK].items()
    }
    forced_first = LinkInstance(
        link_id=first.link_id,
        kind=Terminal.LASER_LINK,
        source_id=first.source_id,
        target_id=first.target_id,
        params=new_params,
    )
    new_links = (forced_first, *arch.links[1:])
    new_arch = Architecture(nodes=arch.nodes, links=new_links)
    return new_arch, forced_first.link_id


def _make_constraints(arch: Architecture, bottleneck_id: str) -> tuple[FeatureConstraint, ...]:
    """Return a synthetic UNSAT constraint system with a single
    designated bottleneck.

    - A fixed constraint x <= 5 (unconditional, tagged to Ground_Station
      type symbolically).
    - If the bottleneck link exists and is a Laser_Link, add x >= 10,
      which conflicts with the fixed constraint.
    """
    x = z3.Real(f"x_h9_{bottleneck_id}")
    constraints: list[FeatureConstraint] = [
        FeatureConstraint(
            family_name="ground_max",
            expression=x <= 5.0,
            features=frozenset(
                {
                    GrammarFeature(
                        FeatureKind.NODE_TYPE,
                        Terminal.GROUND_STATION.value,
                    ),
                }
            ),
        ),
    ]
    bottleneck = next(
        (ln for ln in arch.links if ln.link_id == bottleneck_id),
        None,
    )
    if bottleneck is not None and bottleneck.kind == Terminal.LASER_LINK:
        constraints.append(
            FeatureConstraint(
                family_name="bottleneck_requires_high",
                expression=x >= 10.0,
                features=frozenset(
                    {
                        GrammarFeature(FeatureKind.LINK_INSTANCE, bottleneck.link_id),
                        GrammarFeature(FeatureKind.LINK_TYPE, bottleneck.kind.value),
                    }
                ),
            )
        )
    return tuple(constraints)


def _run_loop(
    initial_arch: Architecture,
    bottleneck_id: str,
    mode: str,
    max_steps: int,
    rng: random.Random,
    config: MutationConfig,
) -> int | None:
    """Run the mutation loop. Return the step at which the architecture
    became SAT, or None if not found within max_steps."""
    arch = initial_arch
    for step in range(max_steps):
        table = ConflictProneTable()
        constraints = _make_constraints(arch, bottleneck_id)
        attribution = attribute_and_mark(constraints, table)
        if attribution.status == "sat":
            return step
        if mode == "random":
            arch = mutate_random(arch, rng, config)
        else:
            arch = mutate_conflict_directed(arch, table, rng, config)
    return None


def test_h9_conflict_directed_converges_faster_than_random() -> None:
    n_trials = 20
    max_steps = 15
    config = MutationConfig()

    conflict_successes = 0
    random_successes = 0
    conflict_steps: list[int] = []
    random_steps: list[int] = []

    for trial in range(n_trials):
        initial_seed = 7000 + trial
        initial_arch, bottleneck_id = _make_initial_architecture_and_bottleneck(initial_seed)

        rng_conflict = random.Random(9000 + trial)
        steps_c = _run_loop(
            initial_arch,
            bottleneck_id,
            "conflict",
            max_steps,
            rng_conflict,
            config,
        )
        if steps_c is not None:
            conflict_successes += 1
            conflict_steps.append(steps_c)

        rng_random = random.Random(11_000 + trial)
        steps_r = _run_loop(
            initial_arch,
            bottleneck_id,
            "random",
            max_steps,
            rng_random,
            config,
        )
        if steps_r is not None:
            random_successes += 1
            random_steps.append(steps_r)

    print(
        f"H9: conflict-directed = {conflict_successes}/{n_trials} "
        f"(mean steps = {sum(conflict_steps) / max(len(conflict_steps), 1):.2f}); "
        f"random = {random_successes}/{n_trials} "
        f"(mean steps = {sum(random_steps) / max(len(random_steps), 1):.2f})"
    )

    mean_conflict = sum(conflict_steps) / len(conflict_steps) if conflict_steps else float("inf")
    mean_random = sum(random_steps) / len(random_steps) if random_steps else float("inf")
    assert conflict_successes >= 1, f"Conflict-directed made no progress in {n_trials} trials"
    assert mean_conflict < mean_random, (
        f"Conflict-directed mean steps ({mean_conflict:.2f}) not less "
        f"than random mean steps ({mean_random:.2f})"
    )
    assert mean_conflict <= 0.6 * mean_random, (
        f"Conflict-directed mean steps ({mean_conflict:.2f}) not at "
        f"least 40%% faster than random ({mean_random:.2f})"
    )


def test_h9_loop_is_deterministic_twice() -> None:
    initial_arch, bottleneck_id = _make_initial_architecture_and_bottleneck(42)
    config = MutationConfig()

    rng1 = random.Random(999)
    steps1 = _run_loop(initial_arch, bottleneck_id, "conflict", 20, rng1, config)
    rng2 = random.Random(999)
    steps2 = _run_loop(initial_arch, bottleneck_id, "conflict", 20, rng2, config)
    assert steps1 == steps2


def test_h9_random_loop_is_deterministic_twice() -> None:
    initial_arch, bottleneck_id = _make_initial_architecture_and_bottleneck(43)
    config = MutationConfig()

    rng1 = random.Random(555)
    steps1 = _run_loop(initial_arch, bottleneck_id, "random", 20, rng1, config)
    rng2 = random.Random(555)
    steps2 = _run_loop(initial_arch, bottleneck_id, "random", 20, rng2, config)
    assert steps1 == steps2
