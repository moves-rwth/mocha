"""Render transition systems and lasso runs as Graphviz directed graphs.

States are drawn as nodes whose external labels show the atomic propositions
that hold in them.  Initial states receive an incoming edge from an invisible
marker.  Highlighted states and transitions use a thicker outline; a current
state receives a double outline.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from itertools import pairwise

from graphviz import Digraph, escape

from mocha.models.transition_system import (
    Action,
    AtomicProposition,
    State,
    Transition,
    TransitionSystem,
)

from .overlay import TransitionSystemOverlay

__all__ = ["to_graphviz", "to_lasso_graphviz", "visualise_step"]


def to_graphviz(
        ts: TransitionSystem[State, Action, AtomicProposition],
        *,
        highlighted_states: Iterable[State] = (),
        highlighted_transitions: Iterable[Transition[State, Action]] = (),
        current_state: State | None = None,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Build a Graphviz representation of a transition system.

    The graph contains one node per state and one labelled edge for each
    source-target pair.  Actions on ordinary and highlighted transitions are
    emitted as separate edges so the highlight remains visible when both kinds
    connect the same pair of states. Formatting callbacks support arbitrary
    hashable values, including integer states and product-state tuples. Their
    output is displayed as literal text. Highlight selections refer to the
    original model values, independently of their displayed labels.

    States are ordered by formatted label, with ``repr`` as a tie-breaker;
    action and proposition labels are sorted as text. Generated node IDs keep
    distinct states separate even when their labels coincide or resemble
    Graphviz syntax and initial-state markers.

    Args:
        ts: The transition system to render.
        highlighted_states: States to draw with a thicker outline.
        highlighted_transitions: Transitions to draw with a thicker edge.
        current_state: A state to draw with a double outline, or ``None`` for
            no current-state marker.
        format_state: Convert a state into its displayed name.
        format_action: Convert an action into its edge-label text.
        format_proposition: Convert an atomic proposition into its label text.

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

    state_labels = {state: format_state(state) for state in ts.states}
    states = sorted(ts.states, key=lambda state: (state_labels[state], repr(state)))
    state_indices = {state: index for index, state in enumerate(states)}
    node_ids = {
        state: f"state_{index}" for state, index in state_indices.items()
    }
    action_labels = {
        action: format_action(action)
        for action in {transition.action for transition in transitions}
    }

    graph: Digraph = Digraph()
    for state, node_id in node_ids.items():
        propositions = sorted(format_proposition(value) for value in ts.labels(state))

        if propositions:
            proposition_labels = f"{{{', '.join(propositions)}}}"
        else:
            proposition_labels = "∅"

        attributes = {}

        if state in highlighted_states:
            attributes["penwidth"] = "3"

        if current_state is not None and state == current_state:
            attributes["peripheries"] = "2"

        graph.node(
            node_id,
            label=escape(state_labels[state]),
            xlabel=escape(proposition_labels),
            **attributes,
        )

    edges: dict[tuple[State, State], set[Action]] = defaultdict(set)
    highlighted_edges: dict[tuple[State, State], set[Action]] = defaultdict(set)

    for transition in transitions:
        key = (transition.source, transition.target)

        if transition in highlighted_transitions:
            highlighted_edges[key].add(transition.action)
        else:
            edges[key].add(transition.action)

    all_pairs = set(edges) | set(highlighted_edges)

    for source, target in sorted(
            all_pairs,
            key=lambda pair: (state_indices[pair[0]], state_indices[pair[1]]),
    ):
        normal_actions = edges[source, target]
        highlighted_actions = highlighted_edges[source, target]

        if normal_actions:
            graph.edge(
                node_ids[source],
                node_ids[target],
                label=escape(", ".join(sorted(action_labels[action] for action in normal_actions))),
            )

        if highlighted_actions:
            graph.edge(
                node_ids[source],
                node_ids[target],
                label=escape(", ".join(sorted(action_labels[action] for action in highlighted_actions))),
                penwidth="3",
            )

    for index, state in enumerate(sorted(ts.initial_states, key=state_indices.__getitem__)):
        marker = f"__initial_{index}"
        graph.node(marker, label="", shape="none", width="0", height="0")
        graph.edge(marker, node_ids[state])

    return graph


def visualise_step(
        ts: TransitionSystem[State, Action, AtomicProposition],
        step: TransitionSystemOverlay[State, Action],
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Render a transition system with an overlay's selections highlighted.

    Args:
        ts: The transition system to render.
        step: The overlay that identifies states and transitions to emphasize.
        format_state: Convert a state into its displayed name.
        format_action: Convert an action into its edge-label text.
        format_proposition: Convert an atomic proposition into its label text.

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
        format_state=format_state,
        format_action=format_action,
        format_proposition=format_proposition,
    )


def to_lasso_graphviz(
        ts: TransitionSystem[State, Action, AtomicProposition],
        counterexample: Sequence[State],
        loop_start: int,
        *,
        format_state: Callable[[State], str] = str,
        format_action: Callable[[Action], str] = str,
        format_proposition: Callable[[AtomicProposition], str] = str,
) -> Digraph:
    """Draw a transition-system lasso as a prefix and a repeating cycle.

    ``counterexample`` ends by repeating the state at ``loop_start``. Each
    preceding position gets its own node, even when the same system state
    occurs more than once. The final edge returns to the loop-start node.
    Edge labels list all actions that connect each pair of states, since a
    state-only lasso does not select a particular action. Formatting callbacks
    make non-string states, actions, and propositions readable. Their output is
    displayed as literal text.

    Raises:
        ValueError: If the sequence is not a lasso-shaped run from an initial
            state of ``ts``.
    """
    states = tuple(counterexample)
    if len(states) < 2:
        raise ValueError("A lasso must contain a state and its repeated endpoint")
    if not isinstance(loop_start, int) or not 0 <= loop_start < len(states) - 1:
        raise ValueError(
            "loop_start must identify a position before the repeated endpoint"
        )
    if states[-1] != states[loop_start]:
        raise ValueError("The last state must repeat the state at loop_start")
    unknown = set(states) - ts.states
    if unknown:
        raise ValueError(f"Counterexample contains unknown states: {unknown!r}")
    if states[0] not in ts.initial_states:
        raise ValueError("The counterexample must start in an initial state")

    actions_by_pair: dict[tuple[State, State], set[Action]] = defaultdict(set)
    for transition in ts.transitions():
        actions_by_pair[transition.source, transition.target].add(transition.action)
    for source, target in pairwise(states):
        if not actions_by_pair[source, target]:
            raise ValueError(f"No transition connects {source!r} to {target!r}")

    graph: Digraph = Digraph()
    graph.attr(rankdir="LR")
    graph.node("__initial", label="", shape="none", width="0", height="0")
    graph.edge("__initial", "step_0")

    for index, state in enumerate(states[:-1]):
        propositions = sorted(format_proposition(value) for value in ts.labels(state))
        state_labels = f"{{{', '.join(propositions)}}}" if propositions else "∅"
        attributes = (
            {"style": "filled", "fillcolor": "#E8F0FE"}
            if index >= loop_start else {}
        )
        if index == loop_start:
            attributes["peripheries"] = "2"
        graph.node(
            f"step_{index}",
            label=escape(f"{index}: {format_state(state)}"),
            xlabel=escape(state_labels),
            **attributes,
        )

    last_edge = len(states) - 2
    for index, (source, target) in enumerate(pairwise(states)):
        actions = ", ".join(sorted(
            format_action(value) for value in actions_by_pair[source, target]
        ))
        attributes = {"color": "#1F6FEB"} if index >= loop_start else {}
        if index == last_edge:
            attributes["penwidth"] = "2"
            actions += " (repeat)"
        target_index = loop_start if index == last_edge else index + 1
        graph.edge(
            f"step_{index}",
            f"step_{target_index}",
            label=escape(actions),
            **attributes,
        )

    return graph
