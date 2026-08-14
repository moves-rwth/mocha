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


@dataclass(frozen=True)
class ReachabilityResult(Generic[State]):
    reachable_states: frozenset[State]


@dataclass(frozen=True)
class ReachabilityStep(Generic[State]):
    iteration: int
    reachable_states: frozenset[State]


def compute_reachable_states(
        ts: TransitionSystem[State, Action, AtomicProposition],
        *,
        on_step: Callable[[ReachabilityStep[State]], None] | None = None,
) -> ReachabilityResult[State]:
    reachable_states = set(ts.initial_states)
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
            successors.update(ts.post(state))

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

    return ReachabilityResult(
        reachable_states=frozenset(reachable_states),
    )


def trace_reachability(
        ts: TransitionSystem[State, Action, AtomicProposition],
) -> AlgorithmTrace[
    ReachabilityResult[State],
    ReachabilityStep[State],
]:
    steps: list[ReachabilityStep[State]] = []

    result = compute_reachable_states(
        ts,
        on_step=steps.append,
    )

    return AlgorithmTrace(
        result=result,
        steps=tuple(steps),
    )