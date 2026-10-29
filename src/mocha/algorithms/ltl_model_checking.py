"""Check universal LTL properties through automata and persistence search.

The negated property is translated to a Büchi automaton and combined with the
transition system. A reachable accepting cycle gives an infinite run violating
the property. Results retain both the automaton product used for the proof and
the counterexample projected onto the original system's states.

Use ``check_ltl(transition_system, property)`` for the verdict and construction results, or
``trace_ltl`` to retain the detailed steps. Formula interpretation starts
at the initial state's label. Failed checks return a finite prefix and cycle
representing an infinite violating path through the original system.
"""

import builtins
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Final, Generic, Hashable, Literal, TypeVar, cast

from mocha.logic.ltl import LTLFormula, Not, propositions
from mocha.models.automaton import NBA
from mocha.models.transition_system import TransitionSystem

from .automata import gnba_to_nba, transition_system_automaton_product
from .ltl_transformations import LTLRewriteStep
from .persistence import PersistenceResult, PersistenceStep, check_persistence
from .ltl2gnba.acceptance import AcceptanceStep
from .ltl2gnba.elementary_set_enumeration import ElementaryTableStep
from .ltl2gnba.initial_states import InitialStateStep
from .ltl2gnba.pipeline import LTLToGNBAResult, LTLToGNBAStep, ltl_to_gnba
from .ltl2gnba.transitions import ElementarySet, TransitionRelationStep, Valuation
from .trace import AlgorithmTrace

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
NBAState = tuple[ElementarySet, int]
_ProductState = tuple[State, NBAState]

_ModelCheckingStage = Literal[
    "negation", "translation", "nba_conversion", "product", "emptiness", "verdict",
]


class _SearchMarker(Enum):
    NONACCEPTING = "nonaccepting"
    SINK_STATE = "sink_state"
    SINK_ACTION = "sink_action"


_SearchState = _ProductState[State] | Literal[_SearchMarker.SINK_STATE]
_SearchProposition = NBAState | Literal[_SearchMarker.NONACCEPTING]


@dataclass(frozen=True)
class LTLModelCheckingStep(Generic[State]):
    """A globally numbered model-checking event with optional nested details.

    ``iteration`` counts from zero across all stages, and ``message`` explains
    the event. ``stage`` identifies negation, translation, NBA conversion,
    product construction, emptiness search, or the verdict. ``detail`` is the
    negated formula for negation, an ``LTLToGNBAStep`` for translation, or a
    ``PersistenceStep`` for DFS events; announcements can have no detail.
    Nested events keep their original stage-specific iteration numbers.
    """

    iteration: int
    stage: _ModelCheckingStage
    message: str
    detail: LTLFormula | LTLToGNBAStep | PersistenceStep[_SearchState[State]] | None = None


@dataclass(frozen=True)
class LTLModelCheckingResult(Generic[State]):
    """A verdict and, when false, a lasso of original transition-system states.

    ``emptiness`` is the persistence result on the search product.
    ``counterexample`` projects its lasso onto original transition-system
    states, retaining the same ``loop_start``. The prefix before that index
    is followed by the infinitely repeated cycle. ``product_counterexample``
    preserves the NBA components as proof of acceptance. ``counterexample``,
    ``product_counterexample``, and ``loop_start`` are ``None`` when the property
    holds; the construction and emptiness results remain available.

    Attributes:
        satisfies: Whether every infinite run from an initial state satisfies
            the original ``property``.
        property: Original input property, before negation or normalization.
        negated_formula: Explicit negation of the property before normalization.
        translation: GNBA construction for the negated property.
        nba: Equivalent NBA recognizing words that violate the property.
        product: Product of the system, projected to the property's proposition
            names, and the NBA. States pair an original state with an NBA state.
        search_product: Separate product copy with non-accepting states marked
            and any dead ends completed by a non-accepting sink for DFS.
        emptiness: Persistence-search result whose verdict matches ``satisfies``.
        counterexample: Original-state lasso with its final state repeating the
            state at ``loop_start``, or ``None`` when the property holds.
        loop_start: Zero-based start of the repeating cycle, or ``None``.

    To recover the infinite state path, take ``counterexample[:loop_start]``
    once and repeat ``counterexample[loop_start:-1]`` forever. The last entry
    closes the loop and is not an additional cycle position. Apply the system's
    labels to those states to obtain the violating word, starting with the
    initial state's label. Although the result is frozen, its stored automaton
    and transition systems remain mutable.
    """

    satisfies: bool
    property: LTLFormula
    negated_formula: LTLFormula
    translation: LTLToGNBAResult
    nba: NBA[NBAState, Valuation]
    product: TransitionSystem[_ProductState[State], Hashable, NBAState]
    search_product: TransitionSystem[_SearchState[State], Hashable, _SearchProposition]
    emptiness: PersistenceResult[_SearchState[State]]
    counterexample: tuple[State, ...] | None
    loop_start: int | None

    @builtins.property
    def product_counterexample(self) -> tuple[_ProductState[State], ...] | None:
        """The accepting product lasso before projection, or ``None`` if satisfied.

        Each state pairs an original system state with an NBA state. The last
        entry repeats the product state at ``loop_start``; projecting the first
        component gives ``counterexample`` with the same cycle boundary.
        """
        # The non-accepting sink only loops on itself and cannot occur in a
        # violating persistence lasso, so every entry is an ordinary product state.
        return cast(tuple[_ProductState[State], ...] | None, self.emptiness.counterexample)


def check_ltl(
    transition_system: TransitionSystem[State, Action, str],
    property: LTLFormula,
    *,
    on_step: Callable[[LTLModelCheckingStep[State]], None] | None = None,
) -> LTLModelCheckingResult[State]:
    """Check whether every infinite run of ``transition_system`` satisfies ``property``.

    The pipeline explicitly constructs the negation of ``property``, translates that formula to
    a GNBA, converts it to an NBA, forms the standard product, and uses
    ``check_persistence`` to detect a reachable accepting cycle. A cycle gives a
    counterexample to the original property. The system must be non-blocking
    and its proposition names must be strings. Formula names must be declared
    in the system.

    The product sees only propositions in the formula. Projecting the system's
    labels onto these names makes the NBA alphabet exactly 2^AP while leaving
    the original states, actions, transitions, and initial states unchanged.

    Formula evaluation begins at the initial state's label: an atomic formula
    concerns that state, while NEXT concerns its successor. The returned
    counterexample contains system states, with a repeated final endpoint and
    a zero-based loop index as documented by ``LTLModelCheckingResult``. The
    chosen counterexample need not be shortest or unique.

    Args:
        transition_system: Transition system with string proposition names and
            no terminal states, including among unreachable states. It is not
            modified.
        property: LTL formula interpreted from the first state of each initial
            run. Derived operators are normalized automatically. Every formula
            proposition must be declared in ``transition_system.atomic_propositions``.
        on_step: Optional synchronous callback receiving globally numbered
            events from negation through the verdict, including nested
            translation details and persistence DFS snapshots.

    Returns:
        The verdict and construction results. A failed property includes an
        original-state counterexample lasso and its zero-based loop boundary.
        With no initial runs, the property holds vacuously.

    Raises:
        TypeError: If a declared system proposition name is not a string.
        ValueError: If the formula uses an undeclared proposition or the system
            contains a terminal state.
    """
    if any(not isinstance(name, str) for name in transition_system.atomic_propositions):
        raise TypeError("LTL model checking requires string atomic proposition names")
    used = propositions(property)
    undeclared = used - transition_system.atomic_propositions
    if undeclared:
        raise ValueError(f"Unknown atomic propositions: {sorted(undeclared)!r}")
    if not transition_system.is_non_blocking():
        raise ValueError("LTL model checking requires a transition system without terminal states")

    iteration = 0

    def report(
        stage: _ModelCheckingStage,
        message: str,
        detail: LTLFormula | LTLToGNBAStep | PersistenceStep[_SearchState[State]] | None = None,
    ) -> None:
        nonlocal iteration
        if on_step is not None:
            on_step(LTLModelCheckingStep(iteration, stage, message, detail))
        iteration += 1

    negated = Not(property)
    report("negation", f"Negate the property: ¬({property}) = {negated}.", negated)

    def describe_translation(step: LTLToGNBAStep) -> str:
        detail = step.detail
        if isinstance(detail, LTLRewriteStep):
            return f"Normalize ({detail.rule}): {detail.formula}."
        if isinstance(detail, ElementaryTableStep):
            return f"Elementary sets ({detail.rule}): {detail.message} ({len(detail.table.rows)} rows.)"
        if isinstance(detail, InitialStateStep):
            return detail.message
        if isinstance(detail, TransitionRelationStep):
            names = ", ".join(f"B{i + 1}" for i in sorted(detail.targets))
            symbol = "{" + ", ".join(sorted(detail.input)) + "}" if detail.input else "∅"
            return f"Transitions from B{detail.source_index + 1} on {symbol}: {{{names}}}."
        if isinstance(detail, AcceptanceStep):
            if detail.condition is None:
                return detail.message
            names = ", ".join(f"B{i + 1}" for i in sorted(detail.condition.state_indices))
            return f"Acceptance for ({detail.condition.formula}): {{{names}}}."
        return f"GNBA translation: {step.stage}."

    translation = ltl_to_gnba(
        negated, on_step=lambda step: report("translation", describe_translation(step), step)
    )
    nba = gnba_to_nba(translation.automaton)
    report("nba_conversion", f"Convert the GNBA to an NBA with {len(nba.states)} states.")
    projected = TransitionSystem[State, Hashable, str].from_components(
        states=transition_system.states,
        actions=transition_system.actions,
        transitions=transition_system.transitions(),
        initial_states=transition_system.initial_states,
        atomic_propositions=used,
        labels={state: transition_system.labels(state) & used for state in transition_system.states},
    )
    product = transition_system_automaton_product(projected, nba)
    report("product", f"Build the product after projecting labels onto {sorted(used)!r}; "
          f"it has {len(product.states)} states and {len(product.initial_states)} initial states.")
    state_numbers = {state: index + 1 for index, state in enumerate(translation.elementary_sets.elementary_sets)}

    # Persistence checks for a cycle outside Φ. Let Φ hold precisely at the
    # non-accepting product states; a violation is an accepting cycle. The
    # standard product can have dead ends even when the original TS is total.
    # Complete those ends with a non-accepting sink for the persistence search.
    nonaccepting: Final = _SearchMarker.NONACCEPTING
    sink: Final = _SearchMarker.SINK_STATE
    sink_action: Final = _SearchMarker.SINK_ACTION
    search_product = TransitionSystem[
        _SearchState[State], Hashable, _SearchProposition,
    ].from_components(
        states=product.states, actions=product.actions,
        transitions=product.transitions(), initial_states=product.initial_states,
        atomic_propositions=(*product.atomic_propositions, nonaccepting),
        labels={state: (*product.labels(state), nonaccepting)
                if state[1] not in nba.accepting_states else product.labels(state)
                for state in product.states},
    )
    terminal = product.terminal_states
    if terminal:
        search_product.add_state(sink, labels={nonaccepting})
        for state in terminal:
            search_product.add_transition(state, sink_action, sink)
        search_product.add_transition(sink, sink_action, sink)
    report("emptiness", "Mark non-accepting product states with Φ and use the persistence "
          "nested DFS to find a cycle outside Φ. Complete dead ends with a non-accepting sink.")

    def describe_emptiness(step: PersistenceStep[_SearchState[State]]) -> str:
        if step.state is None:
            return "Initialize persistence nested DFS on the prepared product."
        if step.state is sink:
            label = "the non-accepting sink"
        else:
            ts_state, (elementary, counter) = step.state
            label = f"({ts_state!r}, B{state_numbers[elementary]}, round {counter})"
        if step.operation == "cycle_found":
            return f"Inner DFS found an accepting cycle through {label}."
        return f"{step.operation.replace('_', ' ').capitalize()} at {label}."

    emptiness = check_persistence(
        search_product, nonaccepting,
        on_step=(
            (lambda step: report("emptiness", describe_emptiness(step), step))
            if on_step is not None else None
        ),
    )
    # As in product_counterexample, the accepting lasso cannot visit the sink.
    product_counterexample = cast(tuple[_ProductState[State], ...] | None, emptiness.counterexample)
    counterexample = (
        tuple(state for state, _ in product_counterexample)
        if product_counterexample is not None else None
    )
    satisfies = emptiness.satisfies
    verdict = "holds" if satisfies else "fails; the accepting product cycle gives a counterexample"
    report("verdict", f"The LTL property {verdict}.")
    return LTLModelCheckingResult(
        satisfies, property, negated, translation, nba, product, search_product,
        emptiness, counterexample, emptiness.loop_start,
    )


def trace_ltl(
    transition_system: TransitionSystem[State, Action, str], property: LTLFormula,
) -> AlgorithmTrace[LTLModelCheckingResult[State], LTLModelCheckingStep[State]]:
    """Check the property and retain every construction and search event in memory.

    Inputs and validation requirements match ``check_ltl``. The trace's
    ``result`` contains the verdict and optional counterexample; ``steps``
    collects the callback events in global order, retaining the detailed
    translation records and persistence DFS snapshots.
    """
    steps: list[LTLModelCheckingStep[State]] = []
    result = check_ltl(transition_system, property, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = ["LTLModelCheckingResult", "LTLModelCheckingStep", "check_ltl", "trace_ltl"]
