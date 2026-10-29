"""Graphviz rendering helpers for invariant-checking results."""

from collections.abc import Callable
from itertools import pairwise

from graphviz import Digraph

from mocha.algorithms.invariance import InvariantResult, InvariantStep
from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    TransitionSystem,
)
from mocha.visualisation.transition_system import to_graphviz

__all__ = ["visualise_invariant_result", "visualise_invariant_step"]


def visualise_invariant_step(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        step: InvariantStep[State],
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Render an invariant-checking snapshot.

    Visited states receive a thicker outline and the state currently under
    examination receives a double outline.

    Args:
        transition_system: The transition system to render.
        step: The invariant-checking snapshot to visualise.
        format_state: Convert a state into its displayed name.
        format_action: Convert an action into its edge-label text.
        format_proposition: Convert an atomic proposition into its label text.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If the step refers to a state outside ``transition_system``.
    """
    return to_graphviz(
        transition_system,
        highlighted_states=step.visited,
        current_state=step.current_state,
        format_state=format_state,
        format_action=format_action,
        format_proposition=format_proposition,
    )


def visualise_invariant_result(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        result: InvariantResult[State],
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Render an invariant result and its counterexample, when present.

    A successful result renders the system unchanged. For a failing result,
    states and transitions that connect consecutive counterexample states are
    highlighted, and the violating final state receives a double outline.

    Args:
        transition_system: The transition system to render.
        result: The invariant-checking result to visualise.
        format_state: Convert a state into its displayed name.
        format_action: Convert an action into its edge-label text.
        format_proposition: Convert an atomic proposition into its label text.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If a counterexample state or transition is outside ``transition_system``.
    """
    if result.counterexample is None:
        return to_graphviz(
            transition_system,
            format_state=format_state,
            format_action=format_action,
            format_proposition=format_proposition,
        )

    counterexample_states = set(result.counterexample)

    path_edges = set(pairwise(result.counterexample))

    counterexample_transitions = {
        transition
        for transition in transition_system.transitions()
        if (
               transition.source,
               transition.target,
           ) in path_edges
    }

    return to_graphviz(
        transition_system,
        highlighted_states=counterexample_states,
        highlighted_transitions=counterexample_transitions,
        current_state=result.counterexample[-1],
        format_state=format_state,
        format_action=format_action,
        format_proposition=format_proposition,
    )
