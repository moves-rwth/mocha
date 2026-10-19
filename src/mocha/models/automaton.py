"""Typed representations of finite and omega (infinite word) automata.

The shared automaton structure is the tuple ``(Q, Σ, δ, I)``: states, alphabet,
transition relation, and initial states. Acceptance conditions belong to the
specialized classes: ``F ⊆ Q`` for finite automata and nondeterministic Büchi
automata, and ``𝓕 ⊆ 2^Q`` for generalized nondeterministic Büchi automata.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Generic, Hashable, NamedTuple, Self, TypeVar

AutomatonState = TypeVar("AutomatonState", bound=Hashable)
Symbol = TypeVar("Symbol", bound=Hashable)


class AutomatonTransition(NamedTuple, Generic[AutomatonState, Symbol]):
    """A member of an automaton transition relation.

    The tuple represents the transition ``source --symbol--> target``.
    """

    source: AutomatonState
    symbol: Symbol
    target: AutomatonState


class Automaton(Generic[AutomatonState, Symbol]):
    """A mutable automaton graph without an acceptance condition.

    The automaton stores the shared components ``(Q, Σ, δ, I)``. Its transition
    relation may be nondeterministic, and it may have multiple initial states.
    Collection properties return immutable ``frozenset`` snapshots; use the
    supplied mutation methods to change the automaton. Subclasses add an
    acceptance condition and its semantics.

    ``None`` is reserved as the unfiltered-symbol sentinel in :meth:`post` and
    :meth:`pre`, and therefore cannot be an alphabet symbol.
    """

    def __init__(self) -> None:
        """Create an automaton with empty components."""
        self._states: set[AutomatonState] = set()
        self._alphabet: set[Symbol] = set()
        self._transitions: dict[
            AutomatonState,
            dict[Symbol, set[AutomatonState]],
        ] = {}
        self._initial_states: set[AutomatonState] = set()

    @staticmethod
    def _validate_symbol(symbol: Symbol) -> None:
        """Reject the sentinel used for unfiltered transition queries."""
        if symbol is None:
            raise ValueError("None cannot be used as an alphabet symbol")

    @property
    def states(self) -> frozenset[AutomatonState]:
        """Return the state set ``Q``."""
        return frozenset(self._states)

    @property
    def alphabet(self) -> frozenset[Symbol]:
        """Return the input alphabet ``Σ``."""
        return frozenset(self._alphabet)

    @property
    def initial_states(self) -> frozenset[AutomatonState]:
        """Return the initial-state set ``I``."""
        return frozenset(self._initial_states)

    def add_state(
            self,
            state: AutomatonState,
            *,
            initial: bool = False,
    ) -> None:
        """Add a state with optional initial status.

        Raises:
            ValueError: If ``state`` is already present.
        """
        if state in self._states:
            raise ValueError(f"State {state!r} already exists")

        self._states.add(state)
        self._transitions[state] = {}

        if initial:
            self._initial_states.add(state)

    def add_symbol(self, symbol: Symbol) -> None:
        """Add ``symbol`` to the alphabet without adding a transition."""
        self._validate_symbol(symbol)
        self._alphabet.add(symbol)

    def add_transition(
            self,
            source: AutomatonState,
            symbol: Symbol,
            target: AutomatonState,
    ) -> None:
        """Add ``source --symbol--> target`` to the transition relation.

        Endpoints must already be states, and the symbol must be registered
        in the alphabet with :meth:`add_symbol`.

        Raises:
            ValueError: If either endpoint or the symbol is unknown, or
                ``symbol`` is ``None``.
        """
        if source not in self._states:
            raise ValueError(f"Unknown source state {source!r}")
        if target not in self._states:
            raise ValueError(f"Unknown target state {target!r}")

        self._validate_symbol(symbol)
        if symbol not in self._alphabet:
            raise ValueError(f"Unknown alphabet symbol {symbol!r}")
        self._transitions[source].setdefault(symbol, set()).add(target)

    def set_initial(
            self,
            state: AutomatonState,
            initial: bool = True,
    ) -> None:
        """Set or clear membership of ``state`` in ``I``.

        Raises:
            ValueError: If ``state`` is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        if initial:
            self._initial_states.add(state)
        else:
            self._initial_states.discard(state)

    def post(
            self,
            state: AutomatonState,
            symbol: Symbol | None = None,
    ) -> frozenset[AutomatonState]:
        """Return successors of ``state``, optionally after ``symbol``.

        Raises:
            ValueError: If ``state`` is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        if symbol is not None:
            return frozenset(self._transitions[state].get(symbol, ()))

        successors: set[AutomatonState] = set()
        for targets in self._transitions[state].values():
            successors.update(targets)
        return frozenset(successors)

    def pre(
            self,
            state: AutomatonState,
            symbol: Symbol | None = None,
    ) -> frozenset[AutomatonState]:
        """Return predecessors of ``state``, optionally before ``symbol``.

        Raises:
            ValueError: If ``state`` is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        predecessors: set[AutomatonState] = set()
        for source, transitions_by_symbol in self._transitions.items():
            if symbol is None:
                if any(
                        state in targets
                        for targets in transitions_by_symbol.values()
                ):
                    predecessors.add(source)
            elif state in transitions_by_symbol.get(symbol, ()):
                predecessors.add(source)

        return frozenset(predecessors)

    def transitions(
            self,
    ) -> Iterator[AutomatonTransition[AutomatonState, Symbol]]:
        """Iterate over each distinct member of ``δ``."""
        for source, transitions_by_symbol in self._transitions.items():
            for symbol, targets in transitions_by_symbol.items():
                for target in targets:
                    yield AutomatonTransition(source, symbol, target)

    def has_transition(
            self,
            source: AutomatonState,
            symbol: Symbol,
            target: AutomatonState,
    ) -> bool:
        """Return whether ``source --symbol--> target`` belongs to ``δ``."""
        return (
            source in self._transitions
            and target in self._transitions[source].get(symbol, ())
        )

    @property
    def is_deterministic(self) -> bool:
        """Return whether the automaton has at most one run per input word.

        A partial automaton is deterministic when it has at most one initial
        state and each state-symbol pair has at most one successor.
        """
        return (
            len(self._initial_states) <= 1
            and all(
                len(targets) <= 1
                for transitions_by_symbol in self._transitions.values()
                for targets in transitions_by_symbol.values()
            )
        )

    @property
    def is_complete(self) -> bool:
        """Return whether every state-symbol pair has at least one successor.

        All states are checked, including unreachable ones. Completeness is
        independent of determinism, initial states, and acceptance conditions.
        With no states or no alphabet symbols, the condition is vacuously true.
        """
        return all(
            transitions_by_symbol.get(symbol)
            for transitions_by_symbol in self._transitions.values()
            for symbol in self._alphabet
        )

    def remove_transition(
            self,
            source: AutomatonState,
            symbol: Symbol,
            target: AutomatonState,
    ) -> None:
        """Remove an existing transition from ``δ``.

        The symbol remains in ``Σ`` even if this removes its final transition.

        Raises:
            ValueError: If an endpoint is unknown or the transition is absent.
        """
        if source not in self._states:
            raise ValueError(f"Unknown source state {source!r}")
        if target not in self._states:
            raise ValueError(f"Unknown target state {target!r}")

        targets = self._transitions[source].get(symbol)
        if targets is None or target not in targets:
            raise ValueError(
                f"Transition ({source!r}, {symbol!r}, {target!r}) does not exist"
            )

        targets.remove(target)
        if not targets:
            del self._transitions[source][symbol]

    def remove_state(self, state: AutomatonState) -> None:
        """Remove ``state`` and all incident transitions.

        Its initial membership is also removed; alphabet symbols remain
        declared.

        Raises:
            ValueError: If ``state`` is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        for source in self._states:
            if source == state:
                continue

            empty_symbols: list[Symbol] = []
            for symbol, targets in self._transitions[source].items():
                targets.discard(state)
                if not targets:
                    empty_symbols.append(symbol)
            for symbol in empty_symbols:
                del self._transitions[source][symbol]

        del self._transitions[state]
        self._states.remove(state)
        self._initial_states.discard(state)

    def remove_symbol(self, symbol: Symbol) -> None:
        """Remove a symbol from ``Σ`` and all transitions labelled by it.

        Raises:
            ValueError: If ``symbol`` is unknown.
        """
        if symbol not in self._alphabet:
            raise ValueError(f"Unknown alphabet symbol {symbol!r}")

        for transitions_by_symbol in self._transitions.values():
            transitions_by_symbol.pop(symbol, None)
        self._alphabet.remove(symbol)

    @classmethod
    def from_components(
            cls,
            *,
            states: Iterable[AutomatonState],
            alphabet: Iterable[Symbol],
            transitions: Iterable[tuple[AutomatonState, Symbol, AutomatonState]],
            initial_states: Iterable[AutomatonState] = (),
    ) -> Self:
        """Construct an automaton from the explicit tuple components.

        The declared states and alphabet form ``Q`` and ``Σ``. Initial states,
        transition endpoints, and transition symbols must be declared; this
        constructor never infers omitted components.

        Raises:
            ValueError: If a component refers to an undeclared state or symbol,
                or if ``None`` is supplied as an alphabet symbol.
        """
        states = set(states)
        alphabet = set(alphabet)
        transitions = set(transitions)
        initial_states = set(initial_states)

        if None in alphabet:
            raise ValueError("None cannot be used as an alphabet symbol")

        if not initial_states <= states:
            raise ValueError(
                f"Unknown initial states: {initial_states - states!r}"
            )
        for source, symbol, target in transitions:
            if source not in states:
                raise ValueError(f"Unknown transition source: {source!r}")
            if target not in states:
                raise ValueError(f"Unknown transition target: {target!r}")
            if symbol is None:
                raise ValueError("None cannot be used as an alphabet symbol")
            if symbol not in alphabet:
                raise ValueError(f"Unknown transition symbol: {symbol!r}")

        automaton = cls()
        for state in states:
            automaton.add_state(
                state,
                initial=state in initial_states,
            )
        for symbol in alphabet:
            automaton.add_symbol(symbol)
        for source, symbol, target in transitions:
            automaton.add_transition(source, symbol, target)

        return automaton


class _StateAcceptanceAutomaton(Automaton[AutomatonState, Symbol]):
    """Shared storage for automata whose condition is ``F ⊆ Q``."""

    def __init__(self) -> None:
        super().__init__()
        self._accepting_states: set[AutomatonState] = set()

    @property
    def accepting_states(self) -> frozenset[AutomatonState]:
        """Return the accepting-state set ``F``."""
        return frozenset(self._accepting_states)

    def add_state(
            self,
            state: AutomatonState,
            *,
            initial: bool = False,
            accepting: bool = False,
    ) -> None:
        """Add a state with optional initial and accepting status."""
        super().add_state(state, initial=initial)
        if accepting:
            self._accepting_states.add(state)

    def set_accepting(
            self,
            state: AutomatonState,
            accepting: bool = True,
    ) -> None:
        """Set or clear membership of ``state`` in ``F``.

        Raises:
            ValueError: If ``state`` is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        if accepting:
            self._accepting_states.add(state)
        else:
            self._accepting_states.discard(state)

    def remove_state(self, state: AutomatonState) -> None:
        """Remove a state and its membership in ``F``."""
        super().remove_state(state)
        self._accepting_states.discard(state)

    @classmethod
    def from_components(
            cls,
            *,
            states: Iterable[AutomatonState],
            alphabet: Iterable[Symbol],
            transitions: Iterable[tuple[AutomatonState, Symbol, AutomatonState]],
            initial_states: Iterable[AutomatonState] = (),
            accepting_states: Iterable[AutomatonState] = (),
    ) -> Self:
        """Construct an automaton with a state-based acceptance condition.

        An empty ``accepting_states`` set is valid and represents the empty
        language for both finite and Büchi automata.
        """
        states = set(states)
        alphabet = set(alphabet)
        transitions = set(transitions)
        initial_states = set(initial_states)
        accepting_states = set(accepting_states)

        if not accepting_states <= states:
            raise ValueError(
                f"Unknown accepting states: {accepting_states - states!r}"
            )

        automaton = super().from_components(
            states=states,
            alphabet=alphabet,
            transitions=transitions,
            initial_states=initial_states,
        )
        automaton._accepting_states = accepting_states
        return automaton


class FiniteAutomaton(_StateAcceptanceAutomaton[AutomatonState, Symbol]):
    """An automaton with non-deterministic finite-word acceptance semantics.

    A word is accepted exactly when at least one run starts in ``I``, consumes
    every symbol in the word through ``δ``, and ends in ``F``. This models an
    NFA directly; :attr:`is_deterministic` identifies the DFA subset.
    An empty ``F`` is allowed and rejects every word, including the empty word.
    """

    def accepts(self, word: Iterable[Symbol]) -> bool:
        """Return whether the automaton accepts a finite input word.

        Symbols outside ``Σ`` cause rejection because they are not words over
        the automaton's alphabet. The empty word is accepted precisely when an
        initial state is accepting.
        """
        current_states = set(self.initial_states)

        for symbol in word:
            if symbol not in self._alphabet:
                return False

            next_states: set[AutomatonState] = set()
            for state in current_states:
                next_states.update(self.post(state, symbol))
            current_states = next_states

            if not current_states:
                return False

        return bool(current_states & self._accepting_states)


class NBA(_StateAcceptanceAutomaton[AutomatonState, Symbol]):
    """A nondeterministic Büchi automaton over infinite words.

    An NBA accepts an infinite word when at least one run starts in ``I`` and
    visits states in ``F`` infinitely often. The common automaton components
    retain the standard tuple ``(Q, Σ, δ, I, F)``; only the interpretation of
    ``F`` differs from :class:`FiniteAutomaton`.
    An empty ``F`` is allowed and rejects every infinite word.

    This class represents the acceptance condition only. Algorithms decide
    language acceptance and model checking questions outside the domain model.
    """


class GNBA(Automaton[AutomatonState, Symbol]):
    """A generalized nondeterministic Büchi automaton.

    A GNBA is the tuple ``(Q, Σ, δ, I, 𝓕)``. Its acceptance condition is a
    finite family ``𝓕`` of state sets. An infinite run is accepting when it
    visits every member of ``𝓕`` infinitely often. This class stores that
    condition; it intentionally does not implement an acceptance algorithm.
    """

    def __init__(self) -> None:
        """Create a GNBA with empty graph components and acceptance family."""
        super().__init__()
        self._accepting_sets: set[frozenset[AutomatonState]] = set()

    @property
    def accepting_sets(self) -> frozenset[frozenset[AutomatonState]]:
        """Return the generalized Büchi acceptance condition ``𝓕 ⊆ 2^Q``."""
        return frozenset(self._accepting_sets)

    def add_accepting_set(
            self,
            states: Iterable[AutomatonState],
    ) -> None:
        """Add a state set to the generalized acceptance condition.

        Empty sets are allowed: they represent an unsatisfiable acceptance
        requirement. Duplicate sets do not change the condition.

        Raises:
            ValueError: If a supplied state is unknown.
        """
        accepting_set = frozenset(states)
        unknown_states = accepting_set - self._states
        if unknown_states:
            raise ValueError(f"Unknown accepting states: {unknown_states!r}")

        self._accepting_sets.add(accepting_set)

    def remove_accepting_set(
            self,
            states: Iterable[AutomatonState],
    ) -> None:
        """Remove an existing member of the generalized acceptance condition.

        Raises:
            ValueError: If the supplied state set is not a member of ``𝓕``.
        """
        accepting_set = frozenset(states)
        if accepting_set not in self._accepting_sets:
            raise ValueError(f"Unknown accepting set: {accepting_set!r}")

        self._accepting_sets.remove(accepting_set)

    def remove_state(self, state: AutomatonState) -> None:
        """Remove a state and delete it from every member of ``𝓕``."""
        super().remove_state(state)
        self._accepting_sets = {
            accepting_set - {state}
            for accepting_set in self._accepting_sets
        }

    @classmethod
    def from_components(
            cls,
            *,
            states: Iterable[AutomatonState],
            alphabet: Iterable[Symbol],
            transitions: Iterable[tuple[AutomatonState, Symbol, AutomatonState]],
            initial_states: Iterable[AutomatonState] = (),
            accepting_sets: Iterable[Iterable[AutomatonState]] = (),
    ) -> Self:
        """Construct a GNBA from its explicit tuple components.

        Every state in each acceptance set must be declared in ``Q``. The
        empty set is a valid member of ``𝓕`` and makes acceptance impossible.

        Raises:
            ValueError: If any tuple component refers to an undeclared state
                or symbol.
        """
        accepting_sets = tuple(
            frozenset(accepting_set)
            for accepting_set in accepting_sets
        )
        automaton = super().from_components(
            states=states,
            alphabet=alphabet,
            transitions=transitions,
            initial_states=initial_states,
        )
        for accepting_set in accepting_sets:
            automaton.add_accepting_set(accepting_set)

        return automaton


NondeterministicBuchiAutomaton = NBA
GeneralizedNondeterministicBuchiAutomaton = GNBA


__all__ = [
    "Automaton",
    "AutomatonState",
    "AutomatonTransition",
    "FiniteAutomaton",
    "GNBA",
    "GeneralizedNondeterministicBuchiAutomaton",
    "NBA",
    "NondeterministicBuchiAutomaton",
    "Symbol",
]
