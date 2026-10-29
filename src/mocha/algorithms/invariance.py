"""Invariant checking for labelled transition systems."""

from dataclasses import dataclass
from typing import Generic, Iterable, Callable

from mocha.algorithms.trace import AlgorithmTrace
from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    TransitionSystem,
)

__all__ = [
    "InvariantResult",
    "InvariantStep",
    "check_invariant",
    "trace_invariant",
]


@dataclass(frozen=True)
class InvariantResult(Generic[State]):
    """The result of checking an invariant over reachable states.

    Attributes:
        satisfies: Whether every reachable state belongs to the requested
            invariant set.
        counterexample: A path from an initial state to a violating state, or
            ``None`` when ``satisfies`` is true.
    """

    satisfies: bool
    counterexample: tuple[State, ...] | None = None


@dataclass(frozen=True)
class InvariantStep(Generic[State]):
    """An immutable snapshot produced while checking an invariant.

    Attributes:
        current_state: The reachable state currently being checked.
        visited: All states examined through and including ``current_state``.
        satisfies_invariant: Whether ``current_state`` belongs to the
            invariant set.
    """

    current_state: State
    visited: frozenset[State]
    satisfies_invariant: bool

def check_invariant(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        invariant_states: Iterable[State],
        *,
        on_step: Callable[[InvariantStep[State]], None] | None = None,
) -> InvariantResult[State]:
    """Check that every reachable state belongs to an invariant set.

    Exploration starts from all initial states. If a reachable state is absent
    from ``invariant_states``, the result includes a path from an initial state
    to that state. Unreachable states do not affect the result.

    Args:
        transition_system: The transition system to analyse.
        invariant_states: States in which the invariant holds.
        on_step: Optional callback invoked for each examined reachable state.

    Returns:
        A successful result, or a counterexample path to the first violating
        state encountered.

    Raises:
        ValueError: If ``invariant_states`` contains a state outside ``transition_system``.
    """
    invariant_states = set(invariant_states)

    unknown = invariant_states - transition_system.states
    if unknown:
        raise ValueError(
            f"Invariant contains unknown states: {unknown!r}"
        )

    visited: set[State] = set()
    initial_states = transition_system.initial_states
    to_explore: list[State] = list(initial_states)

    predecessor: dict[State, State] = {
        state: state
        for state in initial_states
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
            path: list[State] = [state]
            current = state

            while current not in initial_states:
                current = predecessor[current]
                path.append(current)

            path.reverse()

            return InvariantResult(
                satisfies=False,
                counterexample=tuple(path),
            )

        for successor in transition_system.post(state):
            if successor not in visited and successor not in predecessor:
                predecessor[successor] = state
                to_explore.append(successor)

    return InvariantResult(
        satisfies=True,
    )

def trace_invariant(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        invariant_states: Iterable[State],
) -> AlgorithmTrace[
    InvariantResult[State],
    InvariantStep[State],
]:
    """Run invariant checking and retain every exploration step.

    Args:
        transition_system: The transition system to analyse.
        invariant_states: States in which the invariant holds.

    Returns:
        The invariant result and one snapshot per examined state.

    Raises:
        ValueError: If ``invariant_states`` contains a state outside ``transition_system``.
    """
    steps: list[InvariantStep[State]] = []

    result = check_invariant(
        transition_system,
        invariant_states,
        on_step=steps.append,
    )

    return AlgorithmTrace(
        result=result,
        steps=tuple(steps),
    )
