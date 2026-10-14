"""Render transition systems and lasso runs as Graphviz directed graphs.

States are drawn as nodes whose external labels show the atomic propositions
that hold in them.  Initial states receive an incoming edge from an invisible
marker.  Highlighted states and transitions use a thicker outline; a current
state receives a double outline.
"""

from graphviz import Digraph

from .overlay import TransitionSystemOverlay
from mocha.models.transition_system import Transition,TransitionSystem


def to_graphviz(
        ts: TransitionSystem[str, str, str],
        *,
        highlighted_states: Iterable[str] = (),
        highlighted_transitions: Iterable[Transition[str, str]] = (),
        current_state: str | None = None,
) -> Digraph:
    """Build a Graphviz representation of a transition system.

    The graph contains one node per state and one labelled edge for each
    source-target pair.  Actions on ordinary and highlighted transitions are
    emitted as separate edges so the highlight remains visible when both kinds
    connect the same pair of states.  States and actions are sorted to make the
    generated graph deterministic. Generated node IDs keep state names separate
    from Graphviz syntax and initial-state markers. Labels are literal text.

    Args:
        ts: The string-valued transition system to render.
        highlighted_states: States to draw with a thicker outline.
        highlighted_transitions: Transitions to draw with a thicker edge.
        current_state: A state to draw with a double outline.

    Returns:
        A :class:`graphviz.Digraph` ready to display, render, or save.

    Raises:
        ValueError: If a highlighted state or transition, or ``current_state``,
            does not belong to ``ts``.
    """
    highlighted_states = set(highlighted_states)
    highlighted_transitions = set(highlighted_transitions)

    unknown_states = highlighted_states - ts.states
    if unknown_states:
        raise ValueError(
            f"Cannot highlight unknown states: {unknown_states!r}"
        )

    transitions = set(ts.transitions())
    unknown_transitions = highlighted_transitions - transitions
    if unknown_transitions:
        raise ValueError(
            f"Cannot highlight unknown transitions: "
            f"{unknown_transitions!r}"
        )

    if current_state is not None and current_state not in ts.states:
        raise ValueError(
            f"Cannot mark unknown current state: {current_state!r}"
        )

    graph = Digraph()
    for state in sorted(ts.states):
        propositions = sorted(ts.labels(state))

        if propositions:
            state_labels = f"{{{', '.join(propositions)}}}"
        else:
            state_labels = "∅"

        attributes = {}

        if state in highlighted_states:
            attributes["penwidth"] = "3"

        if state == current_state:
            attributes["peripheries"] = "2"

        graph.node(
            state,
            label=state,
            xlabel=f"{state_labels}",
            **attributes,
        )

    from collections import defaultdict

    edges: dict[tuple[str, str], set[str]] = defaultdict(set)
    highlighted_edges: dict[tuple[str, str], set[str]] = defaultdict(set)

    for transition in transitions:
        key = (transition.source, transition.target)

        if transition in highlighted_transitions:
            highlighted_edges[key].add(transition.action)
        else:
            edges[key].add(transition.action)

    all_pairs = set(edges) | set(highlighted_edges)

    for source, target in sorted(all_pairs):
        normal_actions = edges[source, target]
        highlighted_actions = highlighted_edges[source, target]

        if normal_actions:
            graph.edge(
                source,
                target,
                label=", ".join(sorted(normal_actions)),
            )

        if highlighted_actions:
            graph.edge(
                source,
                target,
                label=", ".join(sorted(highlighted_actions)),
                penwidth="3",
            )

    for index, state in enumerate(sorted(ts.initial_states)):
        marker = f"__initial_{index}"
        graph.node(marker, label="", shape="none", width="0", height="0")
        graph.edge(marker, state)

    return graph


def visualise_step(
        ts: TransitionSystem[str, str, str],
        step: TransitionSystemOverlay[str, str],
) -> Digraph:
    """Render a transition system with an overlay's selections highlighted.

    Args:
        ts: The string-valued transition system to render.
        step: The overlay that identifies states and transitions to emphasize.

    Returns:
        A Graphviz directed graph produced by :func:`to_graphviz`.

    Raises:
        ValueError: If the overlay refers to a state or transition outside
            ``ts``.
    """
    return to_graphviz(
        ts,
        highlighted_states=step.highlighted_states,
        highlighted_transitions=step.highlighted_transitions,
    )
