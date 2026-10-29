"""Graphviz rendering of persistence counterexamples."""

from collections.abc import Callable

from graphviz import Digraph

from mocha.algorithms.persistence import PersistenceResult
from mocha.models.transition_system import Action, AtomicProposition, State, TransitionSystem

from .transition_system import to_lasso_graphviz


def visualise_persistence_counterexample(
        transition_system: TransitionSystem[State, Action, AtomicProposition],
        result: PersistenceResult[State],
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Render the ordered counterexample lasso of a failed persistence check.

    Each position is drawn separately, so repeated visits and the return edge
    remain visible. Formatting callbacks support product-system states and
    other non-string model values.

    Raises:
        ValueError: If the result is successful, lacks a counterexample lasso,
            or its lasso is not a valid run of ``transition_system``.
    """
    if result.satisfies:
        raise ValueError("A successful persistence result has no counterexample to visualise")

    if result.counterexample is None or result.loop_start is None:
        raise ValueError("A failing persistence result must include a lasso")
    graph = to_lasso_graphviz(
        transition_system,
        result.counterexample,
        result.loop_start,
        format_state=format_state,
        format_action=format_action,
        format_proposition=format_proposition,
    )
    graph.attr(label="Persistence counterexample", labelloc="t")
    return graph


__all__ = ["visualise_persistence_counterexample"]
