from dataclasses import dataclass
from typing import Generic, Iterable, Callable

from mocha.algorithms.trace import AlgorithmTrace
from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    TransitionSystem,
)


@dataclass(frozen=True)
class InvariantResult(Generic[State]):
    satisfies: bool
    counterexample: tuple[State, ...] | None = None

@dataclass(frozen=True)
class InvariantStep(Generic[State]):
    current_state: State
    visited: frozenset[State]
    satisfies_invariant: bool

def check_invariant(
        ts: TransitionSystem[State, Action, AtomicProposition],
        invariant_states: Iterable[State],
        *,
        on_step: Callable[[InvariantStep[State]], None] | None = None,
) -> InvariantResult[State]:
    invariant_states = set(invariant_states)

    unknown = invariant_states - ts.states
    if unknown:
        raise ValueError(
            f"Invariant contains unknown states: {unknown!r}"
        )

    visited: set[State] = set()
    to_explore: list[State] = list(ts.initial_states)

    predecessor: dict[State, State | None] = {
        state: None
        for state in ts.initial_states
    }

    while to_explore:
        state = to_explore.pop()

        if state in visited:
            continue

        visited.add(state)

        satisfies = state in invariant_states

        if on_step is not None:
                on_step(
                    InvariantStep(
                        current_state=state,
                        visited=frozenset(visited),
                        satisfies_invariant=satisfies,
                    )
                )

        if not satisfies:
            path: list[State] = []
            current: State | None = state

            while current is not None:
                path.append(current)
                current = predecessor[current]

            path.reverse()

            return InvariantResult(
                satisfies=False,
                counterexample=tuple(path),
            )

        for successor in ts.post(state):
            if successor not in visited and successor not in predecessor:
                predecessor[successor] = state
                to_explore.append(successor)

    return InvariantResult(
        satisfies=True,
    )

def trace_invariant(
        ts: TransitionSystem[State, Action, AtomicProposition],
        invariant_states: Iterable[State],
) -> AlgorithmTrace[
    InvariantResult[State],
    InvariantStep[State],
] :
    steps: list[InvariantStep[State]] = []

    result = check_invariant(
        ts,
        invariant_states,
        on_step=steps.append,
    )

    return AlgorithmTrace(
        result=result,
        steps=tuple(steps),
    )
