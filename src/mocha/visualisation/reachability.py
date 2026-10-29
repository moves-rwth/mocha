"""Graphviz rendering helpers for reachability-analysis results."""

from collections.abc import Callable

from graphviz import Digraph

from mocha.algorithms.reachability import ReachabilityStep
from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    TransitionSystem,
)

from .transition_system import to_graphviz

__all__ = ["visualise_reachability_step"]


def visualise_reachability_step(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        step: ReachabilityStep[State],
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Render ``transition_system`` with states reached at ``step`` highlighted.

    The returned :class:`graphviz.Digraph` can be passed directly to IPython's
    ``display`` function.

    Args:
        transition_system: The transition system to render.
        step: The reachability snapshot whose states are highlighted.
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
        highlighted_states=step.reachable_states,
        format_state=format_state,
        format_action=format_action,
        format_proposition=format_proposition,
    )
