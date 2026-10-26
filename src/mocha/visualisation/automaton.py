"""Graphviz state diagrams for automata and their acceptance conditions.

Supports the shared automaton graph, finite automata, Büchi automata, and
generalized Büchi automata, with optional state and transition highlighting.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable

from graphviz import Digraph, escape

from mocha.models.automaton import (
    Automaton,
    AutomatonState,
    AutomatonTransition,
    FiniteAutomaton,
    GNBA,
    NBA,
    Symbol,
)

__all__ = ["to_graphviz"]


def to_graphviz(
        automaton: Automaton[AutomatonState, Symbol],
        *,
        format_state: Callable[[AutomatonState], str] = str,
        format_symbol: Callable[[Symbol], str] = str,
        highlighted_states: Iterable[AutomatonState] = (),
        highlighted_transitions: Iterable[
            AutomatonTransition[AutomatonState, Symbol]
        ] = (),
) -> Digraph:
    """Build a Graphviz state diagram of an automaton.

    Each state is a circle, with an incoming arrow from an invisible marker for
    each initial state. Finite and ordinary Büchi automata use double circles
    for accepting states. Generalized Büchi automata display memberships such
    as ``[F1, F2]`` beneath the state name inside the circle. These one-based
    acceptance-set indices are assigned for the diagram from the ordered state
    memberships; they are not identifiers stored in the model. A graph tooltip
    lists the indices, marks empty sets, and identifies an empty acceptance
    family as having no acceptance requirements.

    Symbols connecting the same pair of states share an edge label. Highlighted
    transitions are drawn separately with thicker edges; highlighted states use
    thicker outlines without changing their acceptance notation.

    Formatting callbacks support arbitrary hashable states and symbols, such as
    product states and proposition sets. Their output is literal text. Generated
    node IDs preserve distinct states even when their displayed labels coincide
    or resemble Graphviz syntax. States are ordered by formatted label, with
    ``repr`` as a tie-breaker; symbols on each edge are sorted by formatted label.

    Args:
        automaton: The automaton to draw. Acceptance notation is included for
            ``FiniteAutomaton``, ``NBA``, and ``GNBA`` instances.
        format_state: Convert a state into its displayed name.
        format_symbol: Convert an alphabet symbol into its edge-label text.
        highlighted_states: States to draw with a thicker outline.
        highlighted_transitions: Transitions to draw with a thicker edge,
            separately from ordinary transitions between the same states.

    Returns:
        A :class:`graphviz.Digraph` ready to display, render, or save.

    Raises:
        ValueError: If a highlighted state or transition is not in the automaton.
    """
    highlighted_states = set(highlighted_states)
    highlighted_transitions = set(highlighted_transitions)
    unknown_states = highlighted_states - automaton.states
    if unknown_states:
        raise ValueError(f"Cannot highlight unknown states: {unknown_states!r}")
    transitions = set(automaton.transitions())
    unknown_transitions = highlighted_transitions - transitions
    if unknown_transitions:
        raise ValueError(
            f"Cannot highlight unknown transitions: {unknown_transitions!r}"
        )

    state_labels = {state: format_state(state) for state in automaton.states}
    states = sorted(
        automaton.states, key=lambda state: (state_labels[state], repr(state))
    )
    state_indices = {state: index for index, state in enumerate(states)}
    node_ids = {state: f"state_{index}" for state, index in state_indices.items()}
    symbol_labels = {
        symbol: format_symbol(symbol) for symbol in automaton.alphabet
    }

    graph: Digraph = Digraph()
    graph.attr(rankdir="LR")
    graph.attr("node", shape="circle")

    memberships: dict[AutomatonState, list[str]] = defaultdict(list)
    if isinstance(automaton, GNBA):
        accepting_sets = sorted(
            automaton.accepting_sets,
            key=lambda members: tuple(sorted(
                state_indices[state] for state in members
            )),
        )
        acceptance_names = []
        for index, members in enumerate(accepting_sets, start=1):
            name = f"F{index}"
            for state in members:
                memberships[state].append(name)
            acceptance_names.append(name if members else f"{name} (empty)")
        graph.attr(
            tooltip=(
                "Generalized Büchi: visit every set infinitely often; "
                + ", ".join(acceptance_names)
                if accepting_sets else "Generalized Büchi: no acceptance requirements"
            )
        )

    accepting_states = (
        automaton.accepting_states
        if isinstance(automaton, (FiniteAutomaton, NBA)) else frozenset()
    )
    for state in states:
        attributes = {}
        if state in accepting_states:
            attributes["shape"] = "doublecircle"
        if state in highlighted_states:
            attributes["penwidth"] = "3"
        label = state_labels[state]
        if memberships[state]:
            label += f"\n[{', '.join(memberships[state])}]"
        graph.node(node_ids[state], label=escape(label), **attributes)

    edges: dict[tuple[int, int, bool], list[str]] = defaultdict(list)
    for transition in transitions:
        key = (
            state_indices[transition.source],
            state_indices[transition.target],
            transition in highlighted_transitions,
        )
        edges[key].append(symbol_labels[transition.symbol])
    for (source, target, highlighted), labels in sorted(edges.items()):
        attributes = {"penwidth": "3"} if highlighted else {}
        graph.edge(
            f"state_{source}", f"state_{target}",
            label=escape(", ".join(sorted(labels))), **attributes,
        )

    initial_states = automaton.initial_states
    ordered_initial_states = (state for state in states if state in initial_states)
    for index, state in enumerate(ordered_initial_states):
        marker = f"__initial_{index}"
        graph.node(marker, label="", shape="none", width="0", height="0")
        graph.edge(marker, node_ids[state])

    return graph
