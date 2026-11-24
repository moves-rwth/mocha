"""Check type inference through MoChA's public API.

After installing MoChA and mypy in a virtual environment, run from the
repository root:

    python -I examples/typed_usage.py
    python -I -m mypy --strict examples/typed_usage.py

Use an installed wheel to check the type information shipped to consumers.
"""

from typing import assert_type

from mocha import (
    AlgorithmTrace,
    ReachabilityStep,
    TransitionSystem,
    compute_reachable_states,
    trace_reachability,
)


def main() -> None:
    # Type parameters describe states, actions, and atomic propositions.
    system = TransitionSystem[int, str, str].from_components(
        states={0, 1, 2, 99},
        actions={"step"},
        transitions={(0, "step", 1), (1, "step", 2), (2, "step", 2)},
        initial_states={0},
        atomic_propositions={"done"},
        labels={2: {"done"}},
    )

    reachable = compute_reachable_states(transition_system=system)
    trace = trace_reachability(transition_system=system)

    # A type checker verifies these inferred types; runtime execution does not.
    assert_type(reachable, frozenset[int])
    assert_type(trace, AlgorithmTrace[frozenset[int], ReachabilityStep[int]])
    assert_type(trace.result, frozenset[int])
    assert_type(trace.steps[0].reachable_states, frozenset[int])

    # This ordinary assertion checks the values at runtime: 99 is unreachable.
    assert reachable == frozenset({0, 1, 2})
    assert trace.result == reachable
    print(f"Reachable states: {sorted(reachable)}")


if __name__ == "__main__":
    main()
