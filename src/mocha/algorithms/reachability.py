"""Reachability analysis for transition systems."""

from dataclasses import dataclass
from typing import Generic, Callable

from mocha.algorithms.trace import AlgorithmTrace
from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    TransitionSystem,
)

__all__ = [
    "ReachabilityStep",
    "compute_reachable_states",
    "reduce_to_reachable",
    "trace_reachability",
]


@dataclass(frozen=True)
class ReachabilityStep(Generic[State]):
    """An immutable snapshot of one reachability expansion.

    Attributes:
        iteration: Zero for the initial-state snapshot and incremented after
            each expansion that discovers at least one state.
        reachable_states: The states known to be reachable at this iteration.
    """

    iteration: int
    reachable_states: frozenset[State]


def compute_reachable_states(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        *,
        on_step: Callable[[ReachabilityStep[State]], None] | None = None,
) -> frozenset[State]:
    """Find every state reachable from an initial state.

    Follow all transitions regardless of their actions. The returned immutable
    set includes all initial states and reachable terminal states. With no
    initial states, it is empty. The input system is not modified.

    ``on_step`` receives an initial snapshot, followed by one snapshot for
    every expansion that discovers new states. The callback is not called for
    the final expansion that reaches the fixed point.

    Args:
        transition_system: The transition system to analyse.
        on_step: Optional callback for progress snapshots.

    Returns:
        The complete reachable set as a ``frozenset`` of state values.
    """
    reachable_states = set(transition_system.initial_states)
    iteration = 0

    if on_step is not None:
        on_step(
            ReachabilityStep(
                iteration=iteration,
                reachable_states=frozenset(reachable_states),
            )
        )

    while True:
        successors: set[State] = set()

        for state in reachable_states:
            successors.update(transition_system.post(state))

        new_reachable = reachable_states | successors

        if new_reachable == reachable_states:
            break

        reachable_states = new_reachable
        iteration += 1

        if on_step is not None:
            on_step(
                ReachabilityStep(
                    iteration=iteration,
                    reachable_states=frozenset(reachable_states),
                )
            )

    return frozenset(reachable_states)


def reduce_to_reachable(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
) -> TransitionSystem[State, Action, AtomicProposition]:
    """Return a new system containing only states reachable from initial states.

    Retain their labels, initial-state membership, and transitions between
    them. All declared actions and atomic propositions are preserved.
    With no initial states, the result has no states or transitions.
    The input system is not modified.
    """
    reachable = compute_reachable_states(transition_system)
    return transition_system.induced_subsystem(reachable)


def trace_reachability(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
) -> AlgorithmTrace[
    frozenset[State],
    ReachabilityStep[State],
]:
    """Run reachability analysis and retain every reported step.

    Args:
        transition_system: The transition system to analyse.

    Returns:
        An ``AlgorithmTrace`` whose ``result`` is the reachable-state
        ``frozenset`` returned by :func:`compute_reachable_states` and whose
        ``steps`` are the initial and expansion snapshots. The last snapshot's
        ``reachable_states`` equals ``result``. With no initial states, the
        trace contains a single snapshot with an empty reachable set.
    """
    steps: list[ReachabilityStep[State]] = []

    result = compute_reachable_states(
        transition_system,
        on_step=steps.append,
    )

    return AlgorithmTrace(
        result=result,
        steps=tuple(steps),
    )
