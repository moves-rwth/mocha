from typing import Iterable

from graphviz import Digraph

from mocha.models.transition_system import Transition,TransitionSystem


def to_graphviz(
        ts: TransitionSystem[str, str, str],
        *,
        highlighted_states: Iterable[str] = (),
        highlighted_transitions: Iterable[Transition[str, str]] = (),
) -> Digraph:
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

    return graph