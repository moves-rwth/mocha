"""Algorithms for transforming and analysing automata."""

from itertools import combinations
from typing import Hashable, TypeVar

from mocha.models.automaton import FiniteAutomaton, GNBA, NBA
from mocha.models.transition_system import TransitionSystem

AutomatonState = TypeVar("AutomatonState", bound=Hashable)
Symbol = TypeVar("Symbol", bound=Hashable)
State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
AtomicProposition = TypeVar("AtomicProposition", bound=Hashable)

ProductState = tuple[State, AutomatonState]


def gnba_to_nba(
        gnba: GNBA[AutomatonState, Symbol],
) -> NBA[tuple[AutomatonState, int], Symbol]:
    """Construct an NBA equivalent to ``gnba``.

    The construction augments every GNBA state with a round-robin counter and
    chooses an arbitrary enumeration
    ``𝓕 = {F₁, …, Fₖ}``. Counter ``i`` means that the run is waiting to visit
    ``Fᵢ``. A transition out of a state in ``Fᵢ`` advances the counter to the
    next acceptance set. The NBA accepts states whose counter is one and whose
    GNBA component belongs to ``F₁``; visiting them infinitely often requires
    every acceptance set to be visited infinitely often. Any enumeration of
    ``𝓕`` produces an equivalent NBA.

    When ``𝓕`` is empty, its generalized Büchi condition is vacuously true.
    The result therefore has one counter value and marks every state as
    accepting.

    Args:
        gnba: The generalized nondeterministic Büchi automaton to convert.

    Returns:
        An equivalent nondeterministic Büchi automaton. Its states are pairs
        ``(state, index)`` where ``index`` identifies the next acceptance set.
    """
    accepting_sets = tuple(gnba.accepting_sets)
    condition_count = len(accepting_sets)
    counter_count = max(condition_count, 1)

    states = {
        (state, index)
        for state in gnba.states
        for index in range(1, counter_count + 1)
    }
    initial_states = {
        (state, 1)
        for state in gnba.initial_states
    }

    transitions: set[
        tuple[tuple[AutomatonState, int], Symbol, tuple[AutomatonState, int]]
    ] = set()
    for transition in gnba.transitions():
        for index in range(1, counter_count + 1):
            if condition_count and transition.source in accepting_sets[index - 1]:
                next_index = index % condition_count + 1
            else:
                next_index = index

            transitions.add(
                (
                    (transition.source, index),
                    transition.symbol,
                    (transition.target, next_index),
                )
            )

    if condition_count:
        accepting_states = {
            (state, 1)
            for state in accepting_sets[0]
        }
    else:
        accepting_states = states

    return NBA.from_components(
        states=states,
        alphabet=gnba.alphabet,
        transitions=transitions,
        initial_states=initial_states,
        accepting_states=accepting_states,
    )


def _valuations(
        propositions: frozenset[AtomicProposition],
) -> frozenset[frozenset[AtomicProposition]]:
    """Return the powerset ``2^propositions`` as state-label valuations."""
    proposition_list = tuple(propositions)
    return frozenset(
        frozenset(subset)
        for size in range(len(proposition_list) + 1)
        for subset in combinations(proposition_list, size)
    )


def transition_system_automaton_product(
        ts: TransitionSystem[State, Action, AtomicProposition],
        automaton: (
            FiniteAutomaton[AutomatonState, frozenset[AtomicProposition]]
            | NBA[AutomatonState, frozenset[AtomicProposition]]
        ),
) -> TransitionSystem[
    ProductState[State, AutomatonState],
    Action,
    AutomatonState,
]:
    r"""Construct the standard product of ``ts`` and a finite automaton or NBA.

    The automaton alphabet must be exactly ``2^AP``, where ``AP`` is the
    transition system's atomic-proposition set. Product states are ``(s, q)``.
    To align a run with its trace, initial states consume ``L(s)`` from an
    automaton initial state, and a product transition consumes the label of its
    target system state:

    .. math::

       (s, q) \xrightarrow{a} (s', q')
       \quad\text{iff}\quad
       s \xrightarrow{a} s'
       \ \text{and}\ q \xrightarrow{L(s')} q'.

    The product has atomic-proposition set ``Q`` and labels every product state
    with its automaton component: ``L'(s, q) = {q}``. For an NBA, a product
    state ``(s, q)`` is accepting exactly when ``q`` is a member of
    ``automaton.accepting_states``.

    Args:
        ts: The labelled transition system.
        automaton: A finite automaton or NBA over the valuations ``2^AP``.

    Returns:
        The product transition system over ``S × Q``, labelled by ``Q``.

    Raises:
        ValueError: If the automaton alphabet differs from ``2^AP``.
    """
    expected_alphabet = _valuations(ts.atomic_propositions)
    if automaton.alphabet != expected_alphabet:
        raise ValueError(
            "Automaton alphabet must equal the transition system's "
            f"valuation set 2^AP: expected {expected_alphabet!r}, "
            f"got {automaton.alphabet!r}"
        )

    product_states = {
        (state, automaton_state)
        for state in ts.states
        for automaton_state in automaton.states
    }
    initial_states = {
        (state, automaton_state)
        for state in ts.initial_states
        for initial_automaton_state in automaton.initial_states
        for automaton_state in automaton.post(
            initial_automaton_state,
            ts.labels(state),
        )
    }
    transitions: set[
        tuple[
            ProductState[State, AutomatonState],
            Action,
            ProductState[State, AutomatonState],
        ]
    ] = set()

    for transition in ts.transitions():
        for automaton_state in automaton.states:
            for next_automaton_state in automaton.post(
                    automaton_state,
                    ts.labels(transition.target),
            ):
                transitions.add(
                    (
                        (transition.source, automaton_state),
                        transition.action,
                        (transition.target, next_automaton_state),
                    )
                )

    return TransitionSystem.from_components(
        states=product_states,
        actions=ts.actions,
        transitions=transitions,
        initial_states=initial_states,
        atomic_propositions=automaton.states,
        labels={
            (state, automaton_state): {automaton_state}
            for state, automaton_state in product_states
        },
    )


__all__ = [
    "gnba_to_nba",
    "transition_system_automaton_product",
]
