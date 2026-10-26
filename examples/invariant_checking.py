"""Explore an invariant violation and its trace in a mutual-exclusion model.

With MoChA installed, run from the repository root:

    python -I examples/invariant_checking.py

The example uses only the base package. Its counterexample is a finite path
to a violating state. Removing the faulty transition makes that state
unreachable, so the invariant holds in the modified model.
"""

from mocha import TransitionSystem, check_invariant, trace_invariant


def main() -> None:
    # A faulty controller lets worker 2 enter while worker 1 is still inside.
    system = TransitionSystem[str, str, str].from_components(
        states={"idle", "worker_1_inside", "both_inside"},
        actions={"enter_1", "enter_2", "leave_1"},
        transitions={
            ("idle", "enter_1", "worker_1_inside"),
            ("worker_1_inside", "enter_2", "both_inside"),
            ("worker_1_inside", "leave_1", "idle"),
        },
        initial_states={"idle"},
        atomic_propositions={"in_cs_1", "in_cs_2"},
        labels={
            "idle": set(),
            "worker_1_inside": {"in_cs_1"},
            "both_inside": {"in_cs_1", "in_cs_2"},
        },
    )

    # check_invariant takes the states where the property holds. Derive them
    # from the labels: at most one worker may occupy its critical section.
    invariant_states = {
        state for state in system.states
        if not {"in_cs_1", "in_cs_2"} <= system.labels(state)
    }
    print("Invariant: workers 1 and 2 are never in their critical sections together.")
    print(f"Allowed states: {sorted(invariant_states)}")

    result = check_invariant(system, invariant_states)
    assert not result.satisfies
    path = result.counterexample
    assert path is not None

    print(f"\nCounterexample starts in the initial state {path[0]!r}:")
    for source, target in zip(path, path[1:]):
        actions = sorted(
            transition.action for transition in system.transitions()
            if transition.source == source and transition.target == target
        )
        print(f"  {source} --{', '.join(actions)}--> {target}")
    violating_state = path[-1]
    print(f"Violation at {violating_state!r}: labels are {sorted(system.labels(violating_state))}.")
    print("Both workers are inside, so this reachable state is outside the invariant.")

    # The trace retains the result and a snapshot for each examined state.
    trace = trace_invariant(system, invariant_states)
    assert trace.result == result
    print("\nInvariant-checking trace:")
    for index, step in enumerate(trace.steps, 1):
        verdict = "holds" if step.satisfies_invariant else "VIOLATED"
        print(f"  Step {index}: check {step.current_state!r}: {verdict}; "
              f"visited={sorted(step.visited)}")

    # Remove the faulty edge. The unsafe state remains declared, but is now
    # unreachable: invariants constrain reachable states, not every state.
    system.remove_transition("worker_1_inside", "enter_2", "both_inside")
    repaired = check_invariant(system, invariant_states)
    assert repaired.satisfies
    assert repaired.counterexample is None
    print("\nAfter removing the faulty enter_2 transition, the invariant holds.")
    print("The unsafe state still exists, but no initial path reaches it.")


if __name__ == "__main__":
    main()
