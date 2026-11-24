"""Persistence checking by nested depth-first search."""

from dataclasses import dataclass
from typing import Callable, Generic, Hashable, TypeVar

from mocha.algorithms.trace import AlgorithmTrace
from mocha.models.transition_system import TransitionSystem

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
AtomicProposition = TypeVar("AtomicProposition", bound=Hashable)


@dataclass(frozen=True)
class PersistenceResult(Generic[State]):
    """The result of checking the persistence property ``◇□Φ``.

    Attributes:
        satisfies: Whether every infinite run eventually remains in states
            satisfying the proposition.
        counterexample: A finite lasso-shaped prefix of a violating run, or
            ``None`` if the property holds. Its final state repeats the state
            at which the cycle begins.
        loop_start: The cycle's first position in ``counterexample``, or
            ``None`` if there is no counterexample.
    """

    satisfies: bool
    counterexample: tuple[State, ...] | None = None

    @property
    def loop_start(self) -> int | None:
        """Index of the repeated cycle state, or ``None`` without a lasso."""
        if self.counterexample is None:
            return None
        return max(
            (index for index, state in enumerate(self.counterexample[:-1])
             if state == self.counterexample[-1]),
            default=None,
        )


@dataclass(frozen=True)
class PersistenceStep(Generic[State]):
    """A nested-DFS configuration used in persistence checking.

    The fields correspond directly to the notation in *Principles of Model Checking*:
    ``outer_visited`` is ``R``, ``outer_stack`` is ``U``, ``inner_visited`` is
    ``T``, and ``inner_stack`` is ``V``. Every snapshot records the state after
    its operation has taken effect.

    Attributes:
        operation: The initialization, push, pop, or cycle-discovery event.
        state: The state involved in the operation, if any.
        outer_visited: States visited by the outer DFS.
        outer_stack: Current outer DFS stack, from bottom to top.
        inner_visited: States visited by all inner DFS calls so far.
        inner_stack: Current inner DFS stack, from bottom to top.
    """

    operation: str
    state: State | None
    outer_visited: frozenset[State]
    outer_stack: tuple[State, ...]
    inner_visited: frozenset[State]
    inner_stack: tuple[State, ...]


def cycle_check(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        start: State,
        visited: set[State],
        *,
        on_step: Callable[[str, State, tuple[State, ...]], None] | None = None,
) -> tuple[State, ...] | None:
    """Find a cycle through ``start`` using depth-first search.

    This is Algorithm 7, "Cycle detection", from *Principles of Model
    Checking*. ``visited`` is the algorithm's set ``T`` and is mutated in
    place. Persistence checking retains it between searches, as Algorithm 8
    requires for nested DFS. When supplied, ``on_step`` receives each inner
    stack operation after it has occurred.

    Args:
        transition_system: The transition system to search.
        start: The state that must lie on the discovered cycle.
        visited: States already visited by the inner DFS.
        on_step: Optional callback receiving an operation, its state, and the
            resulting inner stack.

    Returns:
        A cycle from ``start`` back to ``start``, including both occurrences
        of ``start``, or ``None`` if no such cycle is found.

    Raises:
        ValueError: If ``start`` is not a state of ``transition_system``.
    """
    if start not in transition_system.states:
        raise ValueError(f"Unknown state {start!r}")

    stack: list[State] = [start]
    visited.add(start)

    def report(operation: str, state: State) -> None:
        if on_step is not None:
            on_step(operation, state, tuple(stack))

    report("inner_push", start)

    while stack:
        state = stack[-1]

        if start in transition_system.post(state):
            report("cycle_found", start)
            return tuple(stack + [start])

        unvisited_successors = transition_system.post(state) - visited
        if unvisited_successors:
            successor = next(iter(unvisited_successors))
            stack.append(successor)
            visited.add(successor)
            report("inner_push", successor)
        else:
            popped_state = stack.pop()
            report("inner_pop", popped_state)

    return None


def check_persistence(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        proposition: AtomicProposition,
        *,
        on_step: Callable[[PersistenceStep[State]], None] | None = None,
) -> PersistenceResult[State]:
    """Check whether ``transition_system`` satisfies the persistence property ``◇□Φ``.

    This implements Algorithm 8, "Persistence checking by nested depth-first
    search", from *Principles of Model Checking*. The outer DFS finds reachable
    states. Once it finishes a state not satisfying ``Φ``, the inner DFS checks
    whether that state lies on a reachable cycle. The inner visited set is
    deliberately shared across calls, exactly as in the algorithm.

    Args:
        transition_system: A finite transition system without terminal states.
        proposition: The atomic proposition ``Φ`` that must eventually hold
            forever on every run.
        on_step: Optional callback receiving the initial configuration and
            every outer or inner DFS stack operation.

    Returns:
        A successful result, or a lasso-shaped counterexample to ``◇□Φ``.

    Raises:
        ValueError: If ``proposition`` is undeclared or ``transition_system`` has a terminal
            state.
    """
    if proposition not in transition_system.atomic_propositions:
        raise ValueError(f"Unknown atomic proposition {proposition!r}")
    if not transition_system.is_non_blocking():
        raise ValueError(
            "Persistence checking requires a transition system without "
            "terminal states"
        )

    outer_visited: set[State] = set()
    outer_stack: list[State] = []
    inner_visited: set[State] = set()

    def report(
            operation: str,
            state: State | None = None,
            inner_stack: tuple[State, ...] = (),
    ) -> None:
        if on_step is not None:
            on_step(
                PersistenceStep(
                    operation=operation,
                    state=state,
                    outer_visited=frozenset(outer_visited),
                    outer_stack=tuple(outer_stack),
                    inner_visited=frozenset(inner_visited),
                    inner_stack=inner_stack,
                )
            )

    report("initialize")

    while unvisited_initial_states := transition_system.initial_states - outer_visited:
        initial_state = next(iter(unvisited_initial_states))
        outer_stack.append(initial_state)
        outer_visited.add(initial_state)
        report("outer_push", initial_state)

        while outer_stack:
            state = outer_stack[-1]
            unvisited_successors = transition_system.post(state) - outer_visited

            if unvisited_successors:
                successor = next(iter(unvisited_successors))
                outer_stack.append(successor)
                outer_visited.add(successor)
                report("outer_push", successor)
                continue

            popped_state = outer_stack.pop()
            report("outer_pop", popped_state)
            if proposition in transition_system.labels(state):
                continue

            cycle = cycle_check(
                transition_system,
                state,
                inner_visited,
                on_step=lambda operation, inner_state, inner_stack: report(
                    operation,
                    inner_state,
                    inner_stack,
                ),
            )
            if cycle is not None:
                return PersistenceResult(
                    satisfies=False,
                    counterexample=tuple(outer_stack + list(cycle)),
                )

    return PersistenceResult(satisfies=True)


def trace_persistence(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        proposition: AtomicProposition,
) -> AlgorithmTrace[PersistenceResult[State], PersistenceStep[State]]:
    """Run persistence checking and retain every nested-DFS configuration.

    Args:
        transition_system: A finite transition system without terminal states.
        proposition: The atomic proposition ``Φ`` that must eventually hold
            forever on every run.

    Returns:
        The persistence result and snapshots suitable for a worked solution.

    Raises:
        ValueError: If ``proposition`` is undeclared or ``transition_system`` has a terminal
            state.
    """
    steps: list[PersistenceStep[State]] = []
    result = check_persistence(transition_system, proposition, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


__all__ = [
    "PersistenceResult",
    "PersistenceStep",
    "check_persistence",
    "cycle_check",
    "trace_persistence",
]
