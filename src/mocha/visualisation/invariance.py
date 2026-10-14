"""Graphviz rendering helpers for invariant-checking results."""

from graphviz import Digraph

from mocha.algorithms.invariance import InvariantStep, InvariantResult
from mocha.models.transition_system import TransitionSystem
from mocha.visualisation.transition_system import to_graphviz


def visualise_invariant_step(
        ts: TransitionSystem[str, str, str],
        step: InvariantStep[str],
) -> Digraph:
    """Render an invariant-checking snapshot.

    Visited states receive a thicker outline and the state currently under
    examination receives a double outline.

    Args:
        ts: The string-valued transition system to render.
        step: The invariant-checking snapshot to visualise.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If the step refers to a state outside ``ts``.
    """
    return to_graphviz(
        ts,
        highlighted_states=step.visited,
        current_state=step.current_state,
    )


def visualise_invariant_result(
        ts: TransitionSystem[str, str, str],
        result: InvariantResult[str],
) -> Digraph:
    """Render an invariant result and its counterexample, when present.

    A successful result renders the system unchanged. For a failing result,
    states and transitions that connect consecutive counterexample states are
    highlighted, and the violating final state receives a double outline.

    Args:
        ts: The string-valued transition system to render.
        result: The invariant-checking result to visualise.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If a counterexample state or transition is outside ``ts``.
    """
    if result.counterexample is None:
        return to_graphviz(ts)

    counterexample_states = set(result.counterexample)

    path_edges = set(
        zip(
            result.counterexample,
            result.counterexample[1:],
        )
    )

    counterexample_transitions = {
        transition
        for transition in ts.transitions()
        if (
               transition.source,
               transition.target,
           ) in path_edges
    }

    return to_graphviz(
        ts,
        highlighted_states=counterexample_states,
        highlighted_transitions=counterexample_transitions,
        current_state=result.counterexample[-1],
    )
