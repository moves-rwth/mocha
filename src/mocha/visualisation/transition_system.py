from typing import Iterable

from graphviz import Digraph

from mocha.models.transition_system import TransitionSystem


def to_graphviz(
        ts: TransitionSystem[str, str, str],
        *,
        highlighted_states: Iterable[str] = (),
) -> Digraph:
    highlighted_states = set(highlighted_states)
    unknown = highlighted_states - ts.states
    if unknown:
        raise ValueError(
            f"Cannot highlight unknown states: {unknown!r}"
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
    for source, action, target in ts.transitions():
        edges[source, target].add(action)

    for (source, target), actions in sorted(edges.items()):
        graph.edge(
            source,
            target,
            label=", ".join(sorted(actions)),
        )

    return graph