"""CTL model checking, with exercise-level and detailed traces."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Hashable, Literal, TypeAlias, TypeVar

from mocha.logic.ctl import (
    Always, And, BooleanConstant, CTLStateFormula, Exists, Next, Not,
    Proposition, Until, is_ctl_formula, propositions,
)
from mocha.models.transition_system import TransitionSystem

from .trace import AlgorithmTrace

State = TypeVar("State", bound=Hashable)
Action = TypeVar("Action", bound=Hashable)
Detail = Literal["sets", "reasoning"]


@dataclass(frozen=True, slots=True)
class CTLSuccessorCheck(Generic[State]):
    """For ``state``, the successors belonging to a relevant target set.

    An empty ``matching_successors`` explains why an existential predecessor
    condition fails; any member supplies a witness when it succeeds.
    """

    state: State
    matching_successors: frozenset[State]


@dataclass(frozen=True, slots=True)
class CTLSubformulaStep(Generic[State]):
    """Final satisfaction set and set-theoretic reason for one subformula."""

    formula: CTLStateFormula
    satisfying_states: frozenset[State]
    rule: Literal["true", "proposition", "not", "and", "ex", "eu", "eg"]
    premises: tuple[tuple[CTLStateFormula, frozenset[State]], ...]
    explanation: str


@dataclass(frozen=True, slots=True)
class CTLPredecessorStep(Generic[State]):
    """Detailed successor checks used to compute an ``EX`` set."""

    formula: Exists
    target_states: frozenset[State]
    satisfying_states: frozenset[State]
    checks: frozenset[CTLSuccessorCheck[State]]


@dataclass(frozen=True, slots=True)
class CTLFixedPointStep(Generic[State]):
    """A backward-search snapshot for ``EU`` or ``EG``.

    The notation follows Algorithms 15 and 16 in *Principles of Model
    Checking*: ``approximation`` is ``T``, ``pending_states`` is ``E``, and
    ``processed_state`` is ``s′``.
    Iteration zero records initialization, with no processed state. Each
    subsequent snapshot follows processing one state from ``E``. For ``EG``,
    ``successor_counts`` records ``count[s] = |Post(s) ∩ (T ∪ E)|`` for
    every operand state. ``checks`` shows successors in the current ``T``.
    """

    formula: Exists
    iteration: int
    approximation: frozenset[State]
    added_states: frozenset[State]
    removed_states: frozenset[State]
    checks: frozenset[CTLSuccessorCheck[State]]
    explanation: str
    pending_states: frozenset[State]
    processed_state: State | None
    successor_counts: frozenset[tuple[State, int]]


CTLModelCheckingStep: TypeAlias = (
    CTLSubformulaStep[State] | CTLPredecessorStep[State] | CTLFixedPointStep[State]
)


@dataclass(frozen=True, slots=True)
class CTLModelCheckingResult(Generic[State]):
    """Model-checking result with sets for the ENF formula and every state subformula.

    ``subformula_sets`` is in bottom-up order, with structurally equal
    subformulae listed once. Satisfaction is checked at every initial state;
    sets themselves cover all states, including unreachable ones.
    """

    formula: CTLStateFormula
    satisfying_states: frozenset[State]
    initial_states: frozenset[State]
    subformula_sets: tuple[CTLSubformulaStep[State], ...]

    @property
    def satisfies(self) -> bool:
        return self.initial_states <= self.satisfying_states

    @property
    def violating_initial_states(self) -> frozenset[State]:
        return self.initial_states - self.satisfying_states

    def set_for(self, formula: CTLStateFormula) -> frozenset[State]:
        """Look up the satisfaction set of a subformula of the input."""
        for row in self.subformula_sets:
            if row.formula == formula:
                return row.satisfying_states
        raise KeyError(formula)


def _require_enf(formula: CTLStateFormula) -> None:
    """Require true, propositions, Not, And, and Exists around X, U, or G.

    Normalization must eliminate false and the other quantified operators
    before the bottom-up model-checking rules can be applied.
    """
    if isinstance(formula, BooleanConstant):
        if formula.value:
            return
    elif isinstance(formula, Proposition):
        return
    elif isinstance(formula, Not):
        _require_enf(formula.operand)
        return
    elif isinstance(formula, And):
        _require_enf(formula.left)
        _require_enf(formula.right)
        return
    elif isinstance(formula, Exists):
        path = formula.operand
        if isinstance(path, (Next, Always)):
            _require_enf(path.operand)
            return
        if isinstance(path, Until):
            _require_enf(path.left)
            _require_enf(path.right)
            return
    raise ValueError(
        "CTL model checking requires existential normal form; "
        "call to_existential_normal_form first"
    )


def _exists_until(
    ts: TransitionSystem[State, Action, str],
    formula: Exists,
    sat_left: frozenset[State],
    sat_right: frozenset[State],
    *,
    on_step: Callable[[CTLFixedPointStep[State]], None] | None = None,
) -> frozenset[State]:
    """Compute existential until using Algorithm 15 in *Principles of Model Checking*.

    ``sat_left`` and ``sat_right`` are ``Sat(Φ)`` and ``Sat(Ψ)``.
    ``pending_states`` is ``E``, ``satisfying_states`` is ``T``,
    ``processed_state`` is ``s′``, and ``ts.pre`` implements ``Pre``.

    """
    pending_states = set(sat_right)  # E
    satisfying_states = set(pending_states)  # T
    # Tracing extension: label and freeze the initial state before the search.
    # The formula and callback do not participate in Algorithm 15's updates.
    if on_step is not None:
        on_step(CTLFixedPointStep(
            formula=formula,
            iteration=0,
            approximation=frozenset(satisfying_states),
            added_states=frozenset(),
            removed_states=frozenset(),
            checks=frozenset(),
            explanation="E = Sat(right); T = E",
            pending_states=frozenset(pending_states),
            processed_state=None,
            successor_counts=frozenset(),
        ))
    iteration = 0  # Trace counter, not a variable in Algorithm 15.
    while pending_states:
        processed_state = pending_states.pop()  # s′; arbitrary choice, as in Algorithm 15.
        added: set[State] = set()  # Track discoveries only for the trace.
        for state in ts.pre(processed_state):
            if state in sat_left and state not in satisfying_states:
                pending_states.add(state)
                satisfying_states.add(state)
                added.add(state)
        iteration += 1
        if on_step is not None:
            # Trace one complete predecessor loop, not a simultaneous fixed-point round.
            # Record one witness per new state, rather than every tested predecessor.
            checks = frozenset(
                CTLSuccessorCheck(state, frozenset({processed_state}))
                for state in added
            )
            on_step(CTLFixedPointStep(
                formula=formula,
                iteration=iteration,
                approximation=frozenset(satisfying_states),
                added_states=frozenset(added),
                removed_states=frozenset(),
                checks=checks,
                explanation="Add predecessors in Sat(left) outside T to E and T",
                pending_states=frozenset(pending_states),
                processed_state=processed_state,
                successor_counts=frozenset(),
            ))
    # When tracing, the last snapshot already has E = ∅; no extra step is needed.
    return frozenset(satisfying_states)


def _exists_globally(
    ts: TransitionSystem[State, Action, str],
    formula: Exists,
    sat_operand: frozenset[State],
    *,
    on_step: Callable[[CTLFixedPointStep[State]], None] | None = None,
) -> frozenset[State]:
    """Compute existential globally using Algorithm 16 in *Principles of Model Checking*.

    ``sat_operand`` is ``Sat(Φ)``, ``pending_states`` is ``E``,
    ``candidate_states`` is ``T``, and ``processed_state`` is ``s′``.
    ``ts.post`` and ``ts.pre`` implement ``Post`` and ``Pre``.
    The successor counter retains the name ``count`` and satisfies
    ``count[s] = |Post(s) ∩ (T ∪ E)|``. The graph must be non-blocking.

    """
    pending_states = set(ts.states - sat_operand)  # E
    candidate_states = set(sat_operand)  # T
    count = {state: len(ts.post(state)) for state in sat_operand}
    if on_step is not None:
        on_step(CTLFixedPointStep(
            formula=formula,
            iteration=0,
            approximation=frozenset(candidate_states),
            added_states=frozenset(),
            removed_states=frozenset(),
            checks=frozenset(),
            explanation="E = S \\ Sat(operand); T = Sat(operand); count[s] = |Post(s)|",
            pending_states=frozenset(pending_states),
            processed_state=None,
            successor_counts=frozenset(count.items()),
        ))
    iteration = 0  # Trace counter, not a variable in Algorithm 16.
    while pending_states:
        processed_state = pending_states.pop()  # s′; arbitrary choice, as in Algorithm 16.
        # Extra bookkeeping for the trace; only count, T, and E drive the search.
        removed: set[State] = set()
        checked: set[State] = set()
        for state in ts.pre(processed_state):
            if state in candidate_states:
                count[state] -= 1
                checked.add(state)
                if count[state] == 0:
                    candidate_states.remove(state)
                    pending_states.add(state)
                    removed.add(state)
        iteration += 1
        if on_step is not None:
            # Trace after the entire predecessor loop. Checks show successors in T;
            # their sizes can differ from count[s], which counts successors in T ∪ E.
            checks = frozenset(
                CTLSuccessorCheck(state, ts.post(state) & candidate_states)
                for state in checked
            )
            on_step(CTLFixedPointStep(
                formula=formula,
                iteration=iteration,
                approximation=frozenset(candidate_states),
                added_states=frozenset(),
                removed_states=frozenset(removed),
                checks=checks,
                explanation="Decrement predecessor counts; move states with count zero from T to E",
                pending_states=frozenset(pending_states),
                processed_state=processed_state,
                successor_counts=frozenset(count.items()),
            ))
    # When tracing, the last snapshot already has E = ∅; no extra step is needed.
    return frozenset(candidate_states)


def model_check_ctl(
    ts: TransitionSystem[State, Action, str],
    formula: CTLStateFormula,
    *,
    detail: Detail = "sets",
    on_step: Callable[[CTLModelCheckingStep[State]], None] | None = None,
) -> CTLModelCheckingResult[State]:
    """Model check an ENF CTL formula by computing ``Sat`` bottom-up.

    ``detail='sets'`` emits one final set per distinct subformula. With
    ``detail='reasoning'``, ``EX`` also emits its successor checks, while
    ``EU`` and ``EG`` emit the initialization and each backward-search step
    from Algorithms 15 and 16 in *Principles of Model Checking*. Summary
    rows include the operand sets and set equation.

    The searches in ``_exists_until`` and ``_exists_globally`` document the
    correspondence between their variables and the notation in these algorithms.

    Only CTL state formulae in the supported existential fragment are
    accepted. Path nodes have no satisfaction set of their own; the
    quantifier and its temporal operand form one evaluation rule.

    The transition system must be non-blocking so all paths are infinite.
    Unknown propositions and non-ENF formulas raise ``ValueError``.
    """
    # API addition: check the textbook's assumptions explicitly before computing Sat.
    if detail not in {"sets", "reasoning"}:
        raise ValueError("detail must be 'sets' or 'reasoning'")
    if not is_ctl_formula(formula):
        raise ValueError("CTL model checking requires a state formula in the supported CTL fragment")
    _require_enf(formula)

    states = ts.states
    if terminal := ts.terminal_states:
        raise ValueError(f"CTL model checking requires no terminal states: {terminal!r}")
    unknown = propositions(formula) - ts.atomic_propositions
    if unknown:
        raise ValueError(f"Unknown atomic propositions: {sorted(unknown)!r}")
    initial_states = ts.initial_states

    # Build Sat bottom-up. Structurally equal subformulae share one table entry,
    # even when they occur at several positions in the formula tree.
    satisfaction_sets: dict[CTLStateFormula, frozenset[State]] = {}
    subformula_steps: list[CTLSubformulaStep[State]] = []

    def emit(step: CTLModelCheckingStep[State]) -> None:
        if on_step is not None:
            on_step(step)

    def record_result(
        node: CTLStateFormula,
        value: frozenset[State],
        rule: Literal["true", "proposition", "not", "and", "ex", "eu", "eg"],
        premises: tuple[tuple[CTLStateFormula, frozenset[State]], ...],
        explanation: str,
    ) -> frozenset[State]:
        satisfaction_sets[node] = value
        # Additional output: attach the rule and operand sets to this Sat entry.
        step = CTLSubformulaStep(
            formula=node,
            satisfying_states=value,
            rule=rule,
            premises=premises,
            explanation=explanation,
        )
        subformula_steps.append(step)
        emit(step)
        return value

    def evaluate(node: CTLStateFormula) -> frozenset[State]:
        if node in satisfaction_sets:
            return satisfaction_sets[node]

        if isinstance(node, BooleanConstant):
            return record_result(node, states, "true", (), "Sat(true) = S")
        if isinstance(node, Proposition):
            sat_formula = frozenset(state for state in states if node.name in ts.labels(state))
            return record_result(node, sat_formula, "proposition", (),
                          f"Sat({node}) = {{s ∈ S | {node.name!r} ∈ L(s)}}")
        if isinstance(node, Not):
            sat_operand = evaluate(node.operand)
            return record_result(node, states - sat_operand, "not", ((node.operand, sat_operand),),
                          f"Sat({node}) = S \\ Sat({node.operand})")
        if isinstance(node, And):
            sat_left = evaluate(node.left)
            sat_right = evaluate(node.right)
            return record_result(node, sat_left & sat_right, "and",
                          ((node.left, sat_left), (node.right, sat_right)),
                          f"Sat({node}) = Sat({node.left}) ∩ Sat({node.right})")
        if isinstance(node, Exists) and isinstance(node.operand, Next):
            child = node.operand.operand
            sat_operand = evaluate(child)
            sat_formula = frozenset(
                state for state in states if ts.post(state) & sat_operand
            )
            if detail == "reasoning":
                # Tracing extension: collect witnesses separately from computing Sat(EX).
                checks = frozenset(
                    CTLSuccessorCheck(state, ts.post(state) & sat_operand)
                    for state in states
                )
                emit(CTLPredecessorStep(
                    formula=node,
                    target_states=sat_operand,
                    satisfying_states=sat_formula,
                    checks=checks,
                ))
            return record_result(node, sat_formula, "ex", ((child, sat_operand),),
                          f"Sat({node}) = {{s ∈ S | Post(s) ∩ Sat({child}) ≠ ∅}}")
        if isinstance(node, Exists) and isinstance(node.operand, Until):
            path = node.operand
            sat_left = evaluate(path.left)
            sat_right = evaluate(path.right)
            sat_formula = _exists_until(
                ts, node, sat_left, sat_right,
                on_step=emit if detail == "reasoning" else None,
            )
            return record_result(node, sat_formula, "eu",
                          ((path.left, sat_left), (path.right, sat_right)),
                          "Sat(EU) is the least fixed point of "
                          "T ↦ Sat(right) ∪ (Sat(left) ∩ Pre(T))")
        if isinstance(node, Exists) and isinstance(node.operand, Always):
            child = node.operand.operand
            sat_operand = evaluate(child)
            sat_formula = _exists_globally(
                ts, node, sat_operand,
                on_step=emit if detail == "reasoning" else None,
            )
            return record_result(node, sat_formula, "eg", ((child, sat_operand),),
                          "Sat(EG) is the greatest fixed point of "
                          "T ↦ Sat(operand) ∩ Pre(T)")
        raise TypeError(f"Unknown CTL formula node: {type(node).__name__}")

    satisfying_states = evaluate(formula)
    # Additional output: retain Sat and expose the initial-state verdict and violations.
    return CTLModelCheckingResult(
        formula=formula,
        satisfying_states=satisfying_states,
        initial_states=initial_states,
        subformula_sets=tuple(subformula_steps),
    )


def trace_ctl_model_checking(
    ts: TransitionSystem[State, Action, str],
    formula: CTLStateFormula,
    *,
    detail: Detail = "sets",
) -> AlgorithmTrace[CTLModelCheckingResult[State], CTLModelCheckingStep[State]]:
    """Collect the model checker's callback events into an ``AlgorithmTrace``."""
    # Retain the callback events without adding any algorithm iterations.
    steps: list[CTLModelCheckingStep[State]] = []
    result = model_check_ctl(ts, formula, detail=detail, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


__all__ = [
    "CTLFixedPointStep", "CTLPredecessorStep", "CTLModelCheckingResult",
    "CTLModelCheckingStep", "CTLSubformulaStep", "CTLSuccessorCheck",
    "model_check_ctl", "trace_ctl_model_checking",
]
