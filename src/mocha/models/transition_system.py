"""A mutable, typed representation of a labelled transition system.

A transition system is the tuple ``(S, Act, →, I, AP, L)``: states, actions,
the transition relation, initial states, atomic propositions, and a state
labelling function, respectively.
"""
from __future__ import annotations
from collections.abc import Iterable, Iterator
from typing import Generic, Hashable, NamedTuple, TypeVar, Self, Mapping

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
AtomicProposition = TypeVar("AtomicProposition", bound=Hashable)


class Transition(NamedTuple, Generic[State, Action]):
    """A member of the transition relation: ``source --action--> target``."""

    source: State
    action: Action
    target: State


class TransitionSystem(Generic[State, Action, AtomicProposition]):
    """A mutable labelled transition system.

    Type parameters represent hashable state, action, and atomic proposition
    values. Collection properties return immutable ``frozenset`` snapshots;
    use the supplied mutation methods to change the system.

    To construct a TS, use :meth:`from_components` when the formal tuple's components are already
    available, or :meth:`from_edges` to create a TS based on a graph structure where all transitions share an action

    Note that `None` is reserved and cannot be used for actions.
    """

    def __init__(self) -> None:
        """Create an empty transition system."""
        self._states: set[State] = set()
        self._actions: set[Action] = set()
        self._transitions: dict[State, dict[Action, set[State]]] = {}
        self._initial_states: set[State] = set()
        self._atomic_propositions: set[AtomicProposition] = set()
        self._labels: dict[State, set[AtomicProposition]] = {}

    @staticmethod
    def _validate_action(action: Action) -> None:
        """Reject the sentinel used for unfiltered ``pre`` and ``post`` queries."""
        if action is None:
            raise ValueError("None cannot be used as an action")

    @property
    def states(self) -> frozenset[State]:
        """Return the state set ``S``."""
        return frozenset(self._states)

    @property
    def actions(self) -> frozenset[Action]:
        """Return the action set ``Act``."""
        return frozenset(self._actions)

    @property
    def initial_states(self) -> frozenset[State]:
        """Return the initial-state set ``I``."""
        return frozenset(self._initial_states)

    @property
    def atomic_propositions(self) -> frozenset[AtomicProposition]:
        """Return the atomic-proposition set ``AP``."""
        return frozenset(self._atomic_propositions)

    def add_state(
            self,
            state: State,
            *,
            initial: bool = False,
            labels: Iterable[AtomicProposition] = (),
    ) -> None:
        """Add ``state`` with optional initial status and labels.

        The supplied labels are added to ``AP`` if necessary.
        Raises ``ValueError`` if the state is already present.
        """
        if state in self._states:
            raise ValueError(f"State {state!r} already exists")

        state_labels = set(labels)

        self._states.add(state)
        self._labels[state] = state_labels
        self._transitions[state] = {}

        self._atomic_propositions.update(state_labels)

        if initial:
            self._initial_states.add(state)

    def add_transition(
            self,
            source: State,
            action: Action,
            target: State,
    ) -> None:
        """Add the transition ``source --action--> target``.

        Endpoints must already be states. The action is added to ``Act`` if
        necessary. Raises ``ValueError`` for an unknown endpoint.
        """
        if source not in self._states:
            raise ValueError(f"Unknown source state {source!r}")

        if target not in self._states:
            raise ValueError(f"Unknown target state {target!r}")

        self._validate_action(action)
        self._actions.add(action)

        self._transitions[source].setdefault(action, set()).add(target)

    def add_action(self, action: Action) -> None:
        """Add an action to ``Act`` without adding a transition."""
        self._validate_action(action)
        self._actions.add(action)

    def post(
            self,
            state: State,
            action: Action | None = None,
    ) -> frozenset[State]:
        """Return successors of ``state``, optionally restricted to successors after ``action``.

        Raises ``ValueError`` if the state is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        if action is not None:
            return frozenset(self._transitions[state].get(action, ()))
        successors: set[State] = set()
        for targets in self._transitions[state].values():
            successors.update(targets)

        return frozenset(successors)

    def pre(
            self,
            state: State,
            action: Action | None = None,
    ) -> frozenset[State]:
        """Return predecessors of ``state``, optionally restricted to predecessors before ``action``.

        Raises ``ValueError`` if the state is unknown.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        result: set[State] = set()

        for source, transitions_by_action in self._transitions.items():
            if action is None:
                if any(
                        state in targets
                        for targets in transitions_by_action.values()
                ):
                    result.add(source)

            else:
                if state in transitions_by_action.get(action, set()):
                    result.add(source)

        return frozenset(result)

    def add_atomic_proposition(
            self,
            proposition: AtomicProposition,
    ) -> None:
        """Add a proposition to ``AP`` without labelling a state with it."""
        self._atomic_propositions.add(proposition)

    def labels(self, state: State) -> frozenset[AtomicProposition]:
        """Return ``L(state)``, the propositions that hold in ``state``."""
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        return frozenset(self._labels[state])

    def add_label(
            self,
            state: State,
            proposition: AtomicProposition,
    ) -> None:
        """Make ``proposition`` hold in ``state`` and add it to ``AP``."""
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        self._atomic_propositions.add(proposition)
        self._labels[state].add(proposition)

    def remove_label(
            self,
            state: State,
            proposition: AtomicProposition,
    ) -> None:
        """Remove a proposition from a state label, if present.

        The proposition remains declared in ``AP``.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        self._labels[state].discard(proposition)

    def set_labels(
            self,
            state: State,
            labels: Iterable[AtomicProposition],
    ) -> None:
        """Replace a state's labels, adding the supplied propositions to ``AP``."""
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        labels = set(labels)

        self._atomic_propositions.update(labels)
        self._labels[state] = labels

    def set_initial(
            self,
            state: State,
            initial: bool = True,
    ) -> None:
        """Set or clear membership of ``state`` in the initial-state set ``I``."""
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        if initial:
            self._initial_states.add(state)
        else:
            self._initial_states.discard(state)

    @property
    def terminal_states(self) -> frozenset[State]:
        """Return states without outgoing transitions."""
        return frozenset(
            state
            for state in self._states
            if not self.post(state)
        )

    def is_non_blocking(self) -> bool:
        """Return whether every state has at least one outgoing transition.

        An empty system is non-blocking by vacuous truth.
        """
        return all(self.post(state) for state in self._states)

    def transitions(self) -> Iterator[Transition[State, Action]]:
        """Iterate over each distinct member of the transition relation ``→``."""
        for source, actions in self._transitions.items():
            for action, targets in actions.items():
                for target in targets:
                    yield Transition(source, action, target)

    def has_transition(
            self,
            source: State,
            action: Action,
            target: State,
    ) -> bool:
        """Return whether ``source --action--> target`` belongs to ``→``."""
        return (
                source in self._transitions
                and target in self._transitions[source].get(action, ())
        )

    def enabled_actions(
            self,
            state: State,
    ) -> frozenset[Action]:
        """Return actions with at least one outgoing transition from ``state``."""
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        return frozenset(
            action
            for action, targets in self._transitions[state].items()
            if targets
        )

    def remove_transition(
            self,
            source: State,
            action: Action,
            target: State,
    ) -> None:
        """Remove one existing transition from ``→``.

        Raises ``ValueError`` for unknown endpoints or a missing transition.
        The action stays in ``Act`` even if this removes its final transition.
        """
        if source not in self._states:
            raise ValueError(f"Unknown source state {source!r}")

        if target not in self._states:
            raise ValueError(f"Unknown target state {target!r}")

        targets = self._transitions[source].get(action)

        if targets is None or target not in targets:
            raise ValueError(
                f"Transition ({source!r}, {action!r}, {target!r}) does not exist"
            )

        targets.remove(target)

        # Don't keep an empty action entry around.
        if not targets:
            del self._transitions[source][action]

    def remove_state(self, state: State) -> None:
        """Remove ``state`` and all incoming/outgoing transitions.

        Its labels and initial-state membership are removed. Actions and atomic
        propositions remain declared.
        """
        if state not in self._states:
            raise ValueError(f"Unknown state {state!r}")

        # Remove all incoming transitions.
        for source in self._states:
            if source == state:
                continue

            actions_to_remove: list[Action] = []

            for action, targets in self._transitions[source].items():
                targets.discard(state)

                if not targets:
                    actions_to_remove.append(action)

            for action in actions_to_remove:
                del self._transitions[source][action]

        # Remove the state itself and all outgoing transitions.
        del self._transitions[state]
        del self._labels[state]

        self._initial_states.discard(state)
        self._states.remove(state)

    def remove_action(self, action: Action) -> None:
        """Remove an action and all transitions that use it."""
        if action not in self._actions:
            raise ValueError(f"Unknown action {action!r}")

        for transitions_by_action in self._transitions.values():
            transitions_by_action.pop(action, None)

        self._actions.remove(action)

    def remove_atomic_proposition(
            self,
            proposition: AtomicProposition,
    ) -> None:
        """Remove a proposition from ``AP``. Also removes the proposition as a label for every state."""
        if proposition not in self._atomic_propositions:
            raise ValueError(
                f"Unknown atomic proposition {proposition!r}"
            )

        for labels in self._labels.values():
            labels.discard(proposition)

        self._atomic_propositions.remove(proposition)

    @classmethod
    def from_components(
            cls,
            *,
            states: Iterable[State],
            actions: Iterable[Action],
            transitions: Iterable[tuple[State, Action, State]],
            initial_states: Iterable[State] = (),
            atomic_propositions: Iterable[AtomicProposition] = (),
            labels: Mapping[State, Iterable[AtomicProposition]] | None = None,
    ) -> Self:
        """Construct a system from the explicit components of its formal tuple.

        The declared states, actions, and propositions form the sets.
        Initial states, transition endpoints/actions, and labels are validated
        against them; missing state labels default to the empty set. In contrast
        to the incremental mutation methods, this constructor does not infer
        undeclared actions or propositions from transitions and labels.
        """
        states = set(states)
        actions = set(actions)
        transitions = set(transitions)
        initial_states = set(initial_states)
        atomic_propositions = set(atomic_propositions)
        labels = {
            state: set(state_labels)
            for state, state_labels in (labels or {}).items()
        }

        if None in actions:
            raise ValueError("None cannot be used as an action")

        # Validate input and catch mistakes explicitly
        if not initial_states <= states:
            unknown = initial_states - states
            raise ValueError(
                f"Unknown initial states: {unknown!r}"
            )

        unknown_label_states = set(labels) - states

        if unknown_label_states:
            raise ValueError(
                f"Labels specified for unknown states: "
                f"{unknown_label_states!r}"
            )

        for state, state_labels in labels.items():
            unknown = state_labels - atomic_propositions
            if unknown:
                raise ValueError(
                    f"State {state!r} uses unknown atomic "
                    f"propositions: {unknown!r}"
                )

        for source, action, target in transitions:
            if action is None:
                raise ValueError("None cannot be used as an action")

            if source not in states:
                raise ValueError(
                    f"Unknown transition source: {source!r}"
                )

            if target not in states:
                raise ValueError(
                    f"Unknown transition target: {target!r}"
                )

            if action not in actions:
                raise ValueError(
                    f"Unknown transition action: {action!r}"
                )

        ts = cls()
        # states
        for state in states:
            ts.add_state(
                state,
                labels=labels.get(state, ()),
            )

        # actions
        for action in actions:
            ts.add_action(action)

        # atomic propositions
        for proposition in atomic_propositions:
            ts.add_atomic_proposition(proposition)

        # initial states
        for state in initial_states:
            ts.set_initial(state)

        # transitions
        for source, action, target in transitions:
            ts.add_transition(source, action, target)

        return ts

    @classmethod
    def from_edges(
            cls,
            *,
            states: Iterable[State],
            edges: Iterable[tuple[State, State]],
            action: Action,
            initial_states: Iterable[State] = (),
            atomic_propositions: Iterable[AtomicProposition] = (),
            labels: Mapping[State, Iterable[AtomicProposition]] | None = None,
    ) -> Self:
        """Construct a system from graph edges that all use one ``action``.

        Each ``(source, target)`` edge becomes ``(source, action, target)``.
        This is a shorthand for :meth:`from_components`.
        """
        return cls.from_components(
            states=states,
            actions={action},
            transitions={
                (source, action, target)
                for source, target in edges
            },
            initial_states=initial_states,
            atomic_propositions=atomic_propositions,
            labels=labels,
        )
