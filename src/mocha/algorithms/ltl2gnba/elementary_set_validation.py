"""Validate individual elementary sets and full collections for normalized LTL.

Individual checks report closure, Boolean, local UNTIL, and maximality
violations. Collection checks add duplicate and completeness feedback for
computed solutions, retaining every submitted state and its individual result.
Completeness verification recomputes the full enumeration and can be expensive;
transition construction uses only individual checks and duplicate detection.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from mocha.logic.ltl import (
    And, BooleanConstant, LTLFormula, Next, Not, Until, complement,
)

from ..ltl_transformations import normalize_ltl

ElementarySetCondition = Literal[
    "closure", "propositional_consistency", "local_consistency", "maximality"
]


@dataclass(frozen=True)
class ElementarySetViolation:
    """A failed condition, its witness formulas, and a readable explanation."""

    condition: ElementarySetCondition
    rule: str
    formulas: tuple[LTLFormula, ...]
    message: str


@dataclass(frozen=True)
class ElementarySetResult:
    """Immutable feedback, retaining the submitted candidate."""

    formula: LTLFormula
    candidate: frozenset[LTLFormula]
    closure: frozenset[LTLFormula]
    violations: tuple[ElementarySetViolation, ...]

    @property
    def is_elementary(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class ElementarySetCollectionResult:
    """Feedback on a submitted collection, retaining every individual check.

    Attributes:
        formula: Normalized formula whose elementary sets are required.
        state_results: Individual checker results in submission order, including
            invalid entries and their violations. Each retains the original set.
        duplicate_indices: Pairs (first index, repeated index) identifying valid
            states with identical choices after simplifying equivalent spellings.
            Indices are zero-based; add one to obtain display labels B1, B2, etc.
        missing_sets: Required elementary sets absent from the valid submitted
            states, in the enumeration's deterministic order.

    ``is_complete`` describes coverage only. ``is_valid`` additionally requires
    every submitted state to be elementary and each state to occur exactly once.
    """

    formula: LTLFormula
    state_results: tuple[ElementarySetResult, ...]
    duplicate_indices: tuple[tuple[int, int], ...]
    missing_sets: tuple[frozenset[LTLFormula], ...]

    @property
    def is_complete(self) -> bool:
        """Whether the valid submitted states cover every required elementary set."""
        return not self.missing_sets

    @property
    def is_valid(self) -> bool:
        """Whether the submission contains exactly all elementary sets, once each."""
        return (self.is_complete and not self.duplicate_indices
                and all(result.is_elementary for result in self.state_results))


def _representative(formula: LTLFormula) -> LTLFormula:
    """Identify double negation and negated constants within core syntax."""
    if isinstance(formula, Not):
        return complement(_representative(formula.operand))
    if isinstance(formula, Next):
        return Next(_representative(formula.operand))
    if isinstance(formula, (And, Until)):
        return type(formula)(_representative(formula.left), _representative(formula.right))
    return formula


def _closure(formula: LTLFormula) -> frozenset[LTLFormula]:
    subformulas: set[LTLFormula] = set()

    def visit(node: LTLFormula) -> None:
        if node in subformulas:
            return
        subformulas.add(node)
        if isinstance(node, (Not, Next)):
            visit(node.operand)
        elif isinstance(node, (And, Until)):
            visit(node.left)
            visit(node.right)

    visit(formula)
    return frozenset(subformulas | {complement(node) for node in subformulas})


def check_elementary_set(
    formula: LTLFormula, candidate: Iterable[LTLFormula],
) -> ElementarySetResult:
    """Check the elementary-set conditions from *Principles of Model Checking*.

    ``formula`` must already be normalized by ``normalize_ltl``: only AND,
    NOT, NEXT, UNTIL, propositions, and constants are allowed, without double
    negations or negated constants. No automatic normalization is performed.

    Candidates use formula objects (e.g. from ``parse_ltl``). Membership
    identifies double negations and negated constants within core syntax;
    derived operators are not expanded. The original candidate is retained.
    Every failed condition is reported, in deterministic order. Elementary
    sets need not contain ``formula``; NEXT has no local temporal condition.
    """
    if not isinstance(formula, LTLFormula):
        raise TypeError("formula must be an LTLFormula")
    normalized = normalize_ltl(formula)
    if normalized != formula:
        raise ValueError(
            f"Formula '{formula}' is not normalized. Elementary-set checking requires "
            "only AND, NOT, NEXT, UNTIL, propositions, and constants, with no double "
            "negations or negated constants. Call normalize_ltl(formula) first; "
            f"the normalized formula is '{normalized}'."
        )
    submitted = tuple(candidate)
    if any(not isinstance(item, LTLFormula) for item in submitted):
        raise TypeError("candidate members must be LTLFormula objects")
    original = frozenset(submitted)
    members = frozenset(_representative(item) for item in original)
    closure = _closure(formula)
    violations: list[ElementarySetViolation] = []

    def report(
        condition: ElementarySetCondition, rule: str,
        formulas: tuple[LTLFormula, ...], message: str,
    ) -> None:
        violations.append(ElementarySetViolation(condition, rule, formulas, message))

    for item in sorted(members - closure, key=str):
        report("closure", "outside_closure", (item,),
               f"{item} is not in the closure of {formula}.")

    pairs_seen: set[frozenset[LTLFormula]] = set()
    for item in sorted(closure, key=str):
        opposite = complement(item)
        pair = frozenset((item, opposite))
        if pair not in pairs_seen:
            pairs_seen.add(pair)
            if item in members and opposite in members:
                report("propositional_consistency", "contradiction", (item, opposite),
                       f"Both {item} and its complement {opposite} are included.")
            elif item not in members and opposite not in members:
                report("maximality", "missing_choice", (item, opposite),
                       f"Neither {item} nor its complement {opposite} is included; include one.")

        if isinstance(item, BooleanConstant) and item.value and item not in members:
            report("propositional_consistency", "true_required", (item,),
                   "true belongs to the closure and must be included.")
        elif isinstance(item, And):
            operands_present = item.left in members and item.right in members
            if (item in members) != operands_present:
                report("propositional_consistency", "conjunction", (item, item.left, item.right),
                       f"{item} must be included if and only if both operands "
                       f"({item.left}) and ({item.right}) are included.")
        elif isinstance(item, Until):
            if item.right in members and item not in members:
                report("local_consistency", "until_fulfilled", (item, item.right),
                       f"{item.right} is included, so {item} must be included.")
            if item in members and item.right not in members and item.left not in members:
                report("local_consistency", "until_pending", (item, item.left, item.right),
                       f"{item} is included but {item.right} is absent, "
                       f"so {item.left} must be included.")

    return ElementarySetResult(formula, original, closure, tuple(violations))


def _validate_elementary_sets(
    formula: LTLFormula, elementary_sets: Iterable[Iterable[LTLFormula]],
) -> tuple[frozenset[LTLFormula], tuple[frozenset[LTLFormula], ...]]:
    """Validate and freeze supplied states without checking collection completeness.

    Return the formula's closure and the states in input order. Simplify the
    equivalent spellings accepted by the checker before detecting duplicates,
    so every zero-based state position identifies a distinct elementary set.
    """
    closure = check_elementary_set(formula, ()).closure
    states = []
    seen: dict[frozenset[LTLFormula], int] = {}
    for index, candidate in enumerate(elementary_sets):
        checked = check_elementary_set(formula, candidate)
        if not checked.is_elementary:
            reasons = "; ".join(violation.message for violation in checked.violations)
            raise ValueError(f"B{index + 1} is not an elementary set: {reasons}")
        state = frozenset(normalize_ltl(node) for node in checked.candidate)
        if state in seen:
            raise ValueError(f"B{index + 1} duplicates elementary set B{seen[state] + 1}")
        seen[state] = index
        states.append(state)
    return closure, tuple(states)


def check_elementary_set_collection(
    formula: LTLFormula, elementary_sets: Iterable[Iterable[LTLFormula]],
) -> ElementarySetCollectionResult:
    """Report invalid, repeated, and missing states in a computed solution.

    ``formula`` must already be normalized. Check every submitted state using
    ``check_elementary_set``, retaining its original formulas and all violations.
    Valid states are compared after simplifying double negations and negated
    constants. Invalid states do not count toward coverage of required states.
    Unlike the raising validator, this returns all mathematical errors together
    so callers can give feedback on a student's full submission.

    Completeness checking recomputes the entire elementary-set enumeration and
    can take exponential time and space. Transition construction does not invoke
    this check. A full collection includes states excluding the input formula.

    Returns:
        Immutable feedback with one individual result per submitted state,
        zero-based duplicate indices, and all missing states in enumeration order.

    Raises:
        TypeError: If the formula or a candidate member has the wrong type.
        ValueError: If the input formula is not normalized. Invalid mathematical
            solutions are reported in the result rather than raising an error.
    """
    # Enumeration imports the individual checker, so load it only for completeness.
    from .elementary_set_enumeration import enumerate_elementary_sets

    check_elementary_set(formula, ())
    results = tuple(check_elementary_set(formula, candidate) for candidate in elementary_sets)
    seen: dict[frozenset[LTLFormula], int] = {}
    duplicates = []
    for index, result in enumerate(results):
        if not result.is_elementary:
            continue
        state = frozenset(normalize_ltl(node) for node in result.candidate)
        if state in seen:
            duplicates.append((seen[state], index))
        else:
            seen[state] = index
    expected = enumerate_elementary_sets(formula).elementary_sets
    missing = tuple(state for state in expected if state not in seen)
    return ElementarySetCollectionResult(formula, results, tuple(duplicates), missing)


def validate_elementary_set_collection(
    formula: LTLFormula, elementary_sets: Iterable[Iterable[LTLFormula]],
) -> tuple[frozenset[LTLFormula], ...]:
    """Require exactly all elementary sets over a normalized formula's closure.

    This is the raising counterpart of ``check_elementary_set_collection``.
    It recomputes the full elementary-set enumeration and can take exponential
    time and space. For student feedback, use the checker to inspect individual
    violations, duplicate positions, and missing states without raising.

    Args:
        formula: Formula already normalized by ``normalize_ltl``.
        elementary_sets: Iterable of states containing formula objects. All
            elementary sets are required, including those excluding ``formula``.
            Double negations and negated constants are simplified as in the
            individual checker. Supply a list or tuple for a predictable order.

    Returns:
        The validated states as frozensets in supplied order, allowing reuse
        even when the original input was a generator. This tuple can be passed
        directly to ``compute_transition_relation(formula, states)``.

    Raises:
        TypeError: If the formula or a state member has the wrong type.
        ValueError: If the formula is not normalized, a state is not elementary,
            states are duplicated after simplification, or any state is missing.
            An incomplete collection's error includes a count and an example.
    """
    result = check_elementary_set_collection(formula, elementary_sets)
    errors = []
    for index, state_result in enumerate(result.state_results):
        if not state_result.is_elementary:
            reasons = "; ".join(violation.message for violation in state_result.violations)
            errors.append(f"B{index + 1} is not an elementary set: {reasons}")
    for first, repeated in result.duplicate_indices:
        errors.append(f"B{repeated + 1} duplicates elementary set B{first + 1}")
    if result.missing_sets:
        example = ", ".join(sorted(map(str, result.missing_sets[0])))
        noun = "elementary set" if len(result.missing_sets) == 1 else "elementary sets"
        errors.append(
            f"Incomplete elementary-set collection: missing {len(result.missing_sets)} "
            f"{noun} (for example, {{{example}}})"
        )
    if errors:
        raise ValueError(". ".join(errors))
    return tuple(frozenset(normalize_ltl(node) for node in state_result.candidate)
                 for state_result in result.state_results)


__all__ = [
    "ElementarySetResult", "ElementarySetViolation", "check_elementary_set",
    "ElementarySetCollectionResult", "check_elementary_set_collection",
    "validate_elementary_set_collection",
]
