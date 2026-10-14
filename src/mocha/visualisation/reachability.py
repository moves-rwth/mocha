"""Graphviz rendering helpers for reachability-analysis results."""

from graphviz import Digraph

from mocha.algorithms.reachability import ReachabilityStep
from mocha.models.transition_system import TransitionSystem

from .transition_system import to_graphviz


def visualise_reachability_step(
        ts: TransitionSystem[str, str, str],
        step: ReachabilityStep[str],
) -> Digraph:
    """Render ``ts`` with states reached at ``step`` highlighted.

    The returned :class:`graphviz.Digraph` can be passed directly to IPython's
    ``display`` function.

    Args:
        ts: The string-valued transition system to render.
        step: The reachability snapshot whose states are highlighted.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If the step refers to a state outside ``ts``.
    """
    return to_graphviz(
        ts,
        highlighted_states=step.reachable_states,
    )
