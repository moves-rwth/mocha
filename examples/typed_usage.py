"""Check type inference through MoChA's public API.

After installing MoChA and mypy in a virtual environment, run from the
repository root:

    python -I examples/typed_usage.py
    python -I -m mypy --strict examples/typed_usage.py

Use an installed wheel to check the type information shipped to consumers.
"""

from typing import assert_type

from mocha import ReachabilityResult, TransitionSystem, compute_reachable_states


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

    result = compute_reachable_states(system)

    # A type checker verifies these inferred types; runtime execution does not.
    assert_type(result, ReachabilityResult[int])
    assert_type(result.reachable_states, frozenset[int])

    # This ordinary assertion checks the values at runtime: 99 is unreachable.
    assert result.reachable_states == frozenset({0, 1, 2})
    print(f"Reachable states: {sorted(result.reachable_states)}")


if __name__ == "__main__":
    main()
