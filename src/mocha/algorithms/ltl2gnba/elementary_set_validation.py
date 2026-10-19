"""Validate elementary sets for normalized LTL formulas."""

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


__all__ = ["ElementarySetResult", "ElementarySetViolation", "check_elementary_set"]
