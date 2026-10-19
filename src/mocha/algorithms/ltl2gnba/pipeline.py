"""Translate LTL to a GNBA while preserving the details of each construction stage.

The pipeline normalizes the formula, enumerates elementary sets, selects initial
states, derives transitions, and builds UNTIL acceptance sets. Stage callbacks
share one global sequence number while retaining their original local details.
Each construction stage is also available as an independent function.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from mocha.logic.ltl import LTLFormula

from ..ltl_transformations import LTLRewriteStep, normalize_ltl
from mocha.models.automaton import GNBA

from ..trace import AlgorithmTrace
from .acceptance import AcceptanceResult, AcceptanceStep, compute_acceptance_sets
from .elementary_set_enumeration import ElementarySetEnumeration, ElementaryTableStep, enumerate_elementary_sets
from .initial_states import InitialStatesResult, InitialStateStep, compute_initial_states
from .transitions import (
    ElementarySet, Valuation, TransitionRelationResult, TransitionRelationStep, compute_transition_relation,
)

StageName = Literal["normalization", "elementary_sets", "initial_states", "transitions", "acceptance"]
StageDetail = LTLRewriteStep | ElementaryTableStep | InitialStateStep | TransitionRelationStep | AcceptanceStep


@dataclass(frozen=True)
class LTLToGNBAStep:
    """A construction event with both global ordering and local stage detail.

    ``iteration`` counts from zero across the entire translation. ``stage``
    identifies normalization, elementary-set enumeration, initial-state
    selection, transitions, or acceptance. ``detail`` is the original immutable
    event from that stage, including its own local iteration number.
    """

    iteration: int
    stage: StageName
    detail: StageDetail


@dataclass(frozen=True)
class LTLToGNBAResult:
    """The assembled GNBA and the results used to construct it.

    Attributes:
        formula: Original input, before normalization.
        normalized_formula: Equivalent formula in the construction's core syntax.
        elementary_sets: All elementary states over the normalized closure,
            including states that are not initial or reachable.
        initial_states: States containing the normalized formula.
        transition_relation: Labelled edges and the full valuation alphabet.
        acceptance: One generalized Büchi condition per UNTIL formula.
        automaton: GNBA recognizing precisely the input formula's infinite words.

    The result and stage records are frozen, but ``automaton`` remains mutable.
    Editing it does not update the recorded construction results.
    """

    formula: LTLFormula
    normalized_formula: LTLFormula
    elementary_sets: ElementarySetEnumeration
    initial_states: InitialStatesResult
    transition_relation: TransitionRelationResult
    acceptance: AcceptanceResult
    automaton: GNBA[ElementarySet, Valuation]


def ltl_to_gnba(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLToGNBAStep], None] | None = None,
) -> LTLToGNBAResult:
    """Normalize, enumerate, select initial states, add transitions and acceptance.

    Recognizes the input formula itself: model checking's negation of a
    property must be explicit. All states and stage indices retain the same
    elementary-set enumeration. The alphabet is 2^AP for the formula's AP.
    Stage functions also remain independently callable.

    Args:
        formula: LTL formula to recognize. Derived operators are normalized
            automatically before the elementary-set stages run.
        on_step: Optional synchronous callback receiving each stage's events
            in construction order, wrapped with a global zero-based iteration.

    Returns:
        The original and normalized formulas, every stage result, and the
        assembled GNBA. Its states include all enumerated elementary sets;
        unreachable states are retained.
    """
    iteration = 0

    def report(stage: StageName, detail: StageDetail) -> None:
        nonlocal iteration
        if on_step is not None:
            on_step(LTLToGNBAStep(iteration, stage, detail))
        iteration += 1

    normalized = normalize_ltl(formula, on_step=lambda step: report("normalization", step))
    enumeration = enumerate_elementary_sets(normalized, on_step=lambda step: report("elementary_sets", step))
    initial = compute_initial_states(
        normalized, enumeration.elementary_sets,
        on_step=lambda step: report("initial_states", step),
    )
    transitions = compute_transition_relation(
        normalized, enumeration.elementary_sets,
        on_step=lambda step: report("transitions", step),
    )
    acceptance = compute_acceptance_sets(
        normalized, enumeration.elementary_sets,
        on_step=lambda step: report("acceptance", step),
    )
    automaton = GNBA.from_components(
        states=enumeration.elementary_sets, alphabet=transitions.alphabet,
        transitions=transitions.transitions, initial_states=initial.initial_states,
        accepting_sets=acceptance.accepting_sets,
    )
    return LTLToGNBAResult(formula, normalized, enumeration, initial, transitions, acceptance, automaton)


def trace_ltl_to_gnba(formula: LTLFormula) -> AlgorithmTrace[LTLToGNBAResult, LTLToGNBAStep]:
    """Translate ``formula`` and retain the complete construction trace in memory.

    ``result`` is the same construction returned by ``ltl_to_gnba``; ``steps``
    collects its callback events in global order, retaining stage-specific
    details such as elementary-table snapshots and transition restrictions.
    """
    steps: list[LTLToGNBAStep] = []
    result = ltl_to_gnba(formula, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = ["LTLToGNBAResult", "LTLToGNBAStep", "ltl_to_gnba", "trace_ltl_to_gnba"]
