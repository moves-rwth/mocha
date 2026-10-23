"""Check LTL satisfiability and validity using Büchi automaton emptiness.

Satisfiability asks whether some infinite valuation word satisfies a formula;
validity asks whether every such word does. Both checks normalize formulas
during translation and expose construction and search details through optional
callbacks. Satisfying words and validity counterexamples use a finite prefix
followed by an infinitely repeated nonempty loop.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal, cast

from mocha.algorithms.trace import AlgorithmTrace
from mocha.logic.ltl import LTLFormula, Not
from mocha.models.automaton import NBA
from mocha.models.transition_system import TransitionSystem

from .automata import gnba_to_nba
from .ltl2gnba.pipeline import LTLToGNBAResult, LTLToGNBAStep, ltl_to_gnba
from .ltl2gnba.transitions import ElementarySet, Valuation
from .persistence import PersistenceResult, PersistenceStep, check_persistence

NBAState = tuple[ElementarySet, int]

_SatisfiabilityStage = Literal["translation", "nba_conversion", "emptiness", "verdict"]
_ValidityStage = Literal["negation", "satisfiability", "verdict"]


class _SearchMarker(Enum):
    NONACCEPTING = "nonaccepting"
    SINK_STATE = "sink_state"
    SINK_ACTION = "sink_action"


_SearchState = NBAState | Literal[_SearchMarker.SINK_STATE]
_SearchAction = Valuation | Literal[_SearchMarker.SINK_ACTION]


@dataclass(frozen=True)
class LTLSatisfiabilityStep:
    """A stage of Algorithm 12 in *Principles of Model Checking*, retaining the detailed translation or DFS step.

    ``iteration`` is zero-based across the whole check. ``stage`` distinguishes
    GNBA translation, NBA conversion, emptiness search, and the final verdict;
    ``message`` explains the event. ``detail`` retains an ``LTLToGNBAStep`` for
    translation events or a ``PersistenceStep`` for DFS events, and is ``None``
    for stage announcements without a detailed event.
    """

    iteration: int
    stage: _SatisfiabilityStage
    message: str
    detail: LTLToGNBAStep | PersistenceStep[_SearchState] | None = None


@dataclass(frozen=True)
class LTLSatisfiabilityResult:
    """An NBA emptiness verdict and, if satisfiable, an accepted lasso.

    ``run`` ends by repeating the state at ``loop_start``. ``witness`` has one
    valuation for each transition in the run. Thus the infinite word is
    ``witness[:loop_start]`` followed by ``witness[loop_start:]`` forever.

    Attributes:
        satisfiable: Whether at least one infinite word satisfies the formula.
        formula: Original input, before translation normalizes it.
        translation: GNBA construction, including the normalized formula.
        nba: Equivalent NBA with states (elementary set, acceptance round).
        search_system: NBA transition graph prepared for persistence search,
            with non-accepting states marked and dead ends completed by a sink.
        emptiness: Persistence result; ``satisfies`` is true exactly when the
            NBA language is empty, the opposite of ``satisfiable``.
        run: Accepting NBA lasso, including its repeated final state.
        witness: Valuation word labelling the run, excluding any extra letter
            for the repeated endpoint. Each valuation is a set of true names.
        loop_start: Zero-based start of the repeating portion in run and word.

    ``run``, ``witness``, and ``loop_start`` are all ``None`` when unsatisfiable.
    The result is frozen, but its automaton and transition system are mutable.
    """

    satisfiable: bool
    formula: LTLFormula
    translation: LTLToGNBAResult
    nba: NBA[NBAState, Valuation]
    search_system: TransitionSystem[_SearchState, _SearchAction, _SearchMarker]
    emptiness: PersistenceResult[_SearchState]
    run: tuple[NBAState, ...] | None
    witness: tuple[Valuation, ...] | None
    loop_start: int | None


@dataclass(frozen=True)
class LTLValidityStep:
    """A negation, satisfiability, or verdict step of validity checking.

    ``iteration`` counts from zero across the validity check, and ``message``
    explains the event. ``detail`` is the negated formula for ``negation``, a
    nested ``LTLSatisfiabilityStep`` for ``satisfiability``, or ``None`` for the
    final ``verdict``. Nested steps retain their own iteration numbers.
    """

    iteration: int
    stage: _ValidityStage
    message: str
    detail: LTLFormula | LTLSatisfiabilityStep | None = None


@dataclass(frozen=True)
class LTLValidityResult:
    """Validity of a formula, with a word falsifying it when it is invalid.

    ``valid`` means that every infinite valuation word satisfies ``formula``.
    ``negated_formula`` is its explicit negation before normalization, and
    ``satisfiability`` contains the check of that negation. Its satisfying
    witness, exposed as ``counterexample``, falsifies the original formula.
    The counterexample and ``loop_start`` are ``None`` when the formula is valid.
    """

    valid: bool
    formula: LTLFormula
    negated_formula: LTLFormula
    satisfiability: LTLSatisfiabilityResult

    @property
    def counterexample(self) -> tuple[Valuation, ...] | None:
        """A falsifying word whose suffix from ``loop_start`` repeats forever."""
        return self.satisfiability.witness

    @property
    def loop_start(self) -> int | None:
        """Zero-based start of the counterexample's loop, or ``None`` if valid."""
        return self.satisfiability.loop_start


def check_ltl_satisfiability(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLSatisfiabilityStep], None] | None = None,
) -> LTLSatisfiabilityResult:
    """Apply Algorithm 12 from *Principles of Model Checking* to ``formula``.

    Translate the formula to an NBA and test for a reachable accepting cycle.
    The existing persistence nested DFS finds such a cycle when its proposition
    marks precisely the non-accepting states. Dead ends lead to a non-accepting
    sink so that the search system remains non-blocking.

    Args:
        formula: LTL formula to test. Translation normalizes derived operators
            automatically; no transition system or declared alphabet is needed.
        on_step: Optional synchronous callback receiving globally numbered
            translation events, conversion and search announcements, detailed
            persistence DFS events, and the final verdict.

    Returns:
        The construction and emptiness results, plus an accepted NBA run and
        valuation word when satisfiable. The alphabet is the powerset of the
        formula's proposition names. ``loop_start`` identifies the nonempty
        repeating suffix of the finite witness word.
    """
    iteration = 0

    def report(
        stage: _SatisfiabilityStage,
        message: str,
        detail: LTLToGNBAStep | PersistenceStep[_SearchState] | None = None,
    ) -> None:
        nonlocal iteration
        if on_step is not None:
            on_step(LTLSatisfiabilityStep(iteration, stage, message, detail))
        iteration += 1

    translation = ltl_to_gnba(
        formula,
        on_step=lambda step: report("translation", f"GNBA translation: {step.stage}.", step),
    )
    nba = gnba_to_nba(translation.automaton)
    report("nba_conversion", f"Convert the GNBA to an NBA with {len(nba.states)} states.")

    nonaccepting: Final = _SearchMarker.NONACCEPTING
    sink: Final = _SearchMarker.SINK_STATE
    sink_action: Final = _SearchMarker.SINK_ACTION
    search_system = TransitionSystem[_SearchState, _SearchAction, _SearchMarker].from_components(
        states=nba.states,
        actions=nba.alphabet,
        transitions=((edge.source, edge.symbol, edge.target) for edge in nba.transitions()),
        initial_states=nba.initial_states,
        atomic_propositions={nonaccepting},
        labels={state: {nonaccepting} if state not in nba.accepting_states else set()
                for state in nba.states},
    )
    terminal_states = search_system.terminal_states
    if terminal_states:
        search_system.add_state(sink, labels={nonaccepting})
        search_system.add_transition(sink, sink_action, sink)
        for state in terminal_states:
            search_system.add_transition(state, sink_action, sink)
    report("emptiness", "Search for a reachable accepting cycle with persistence nested DFS.")
    emptiness = check_persistence(
        search_system,
        nonaccepting,
        on_step=(
            (lambda step: report("emptiness", step.operation.replace("_", " ").capitalize(), step))
            if on_step is not None else None
        ),
    )

    # The non-accepting sink only loops on itself, so an accepting lasso
    # cannot visit it. The cast records this invariant without changing the run.
    run = cast(tuple[NBAState, ...] | None, emptiness.counterexample)
    if run is None:
        witness = None
        loop_start = None
    else:
        ordered_alphabet = sorted(nba.alphabet, key=lambda value: tuple(sorted(value)))
        witness = tuple(
            next(symbol for symbol in ordered_alphabet if target in nba.post(source, symbol))
            for source, target in zip(run, run[1:])
        )
        loop_start = max(index for index, state in enumerate(run[:-1]) if state == run[-1])
    satisfiable = not emptiness.satisfies
    report("verdict", "The formula is satisfiable." if satisfiable else "The formula is unsatisfiable.")
    return LTLSatisfiabilityResult(
        satisfiable, formula, translation, nba, search_system, emptiness,
        run, witness, loop_start,
    )


def trace_ltl_satisfiability(
    formula: LTLFormula,
) -> AlgorithmTrace[LTLSatisfiabilityResult, LTLSatisfiabilityStep]:
    """Check satisfiability and retain all translation and search callback events.

    Accepts the same formulas as ``check_ltl_satisfiability``. ``result`` contains
    the verdict and optional witness, and ``steps`` holds the complete ordered
    trace, including detailed persistence DFS snapshots, in memory.
    """
    steps: list[LTLSatisfiabilityStep] = []
    result = check_ltl_satisfiability(formula, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


def check_ltl_validity(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLValidityStep], None] | None = None,
) -> LTLValidityResult:
    """Check validity by testing whether the negated formula is unsatisfiable.

    Args:
        formula: LTL formula that should hold on every infinite valuation word.
            Its explicit negation is normalized during satisfiability checking.
        on_step: Optional synchronous callback receiving the initial negation,
            wrapped satisfiability events, and the final verdict, with one
            global zero-based sequence across all these events.

    Returns:
        The validity verdict and the satisfiability result for the negation.
        If invalid, ``counterexample`` gives a valuation word falsifying the
        input; its suffix starting at ``loop_start`` repeats infinitely.
    """
    iteration = 0

    def report(
        stage: _ValidityStage,
        message: str,
        detail: LTLFormula | LTLSatisfiabilityStep | None = None,
    ) -> None:
        nonlocal iteration
        if on_step is not None:
            on_step(LTLValidityStep(iteration, stage, message, detail))
        iteration += 1

    negated = Not(formula)
    report("negation", f"Negate the formula: {negated}.", negated)
    satisfiability = check_ltl_satisfiability(
        negated,
        on_step=(
            (lambda step: report("satisfiability", step.message, step))
            if on_step is not None else None
        ),
    )
    valid = not satisfiability.satisfiable
    report("verdict", "The formula is valid." if valid else "The formula is not valid.")
    return LTLValidityResult(valid, formula, negated, satisfiability)


def trace_ltl_validity(
    formula: LTLFormula,
) -> AlgorithmTrace[LTLValidityResult, LTLValidityStep]:
    """Check validity and retain the negation, satisfiability, and verdict events.

    ``result`` is the verdict from ``check_ltl_validity``; ``steps`` retains all
    callback events in global order, including nested translation and search
    details from the satisfiability check of the negated formula.
    """
    steps: list[LTLValidityStep] = []
    result = check_ltl_validity(formula, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = [
    "LTLSatisfiabilityResult", "LTLSatisfiabilityStep", "LTLValidityResult", "LTLValidityStep",
    "check_ltl_satisfiability", "check_ltl_validity",
    "trace_ltl_satisfiability", "trace_ltl_validity",
]
