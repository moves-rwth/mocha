"""Immutable LTL syntax trees and formatting.

Precedence, from strongest to weakest: ``! X F G``, ``U W R``, ``&``, ``|``,
``->``, ``<->``. Chained implications and combinations of ``U``, ``W``, and
``R`` require explicit parentheses. The other binary operators associate to
the left. Parentheses override precedence. Both ASCII and textbook Unicode
operator spellings are accepted; string output uses the latter.
Propositions must be double-quoted. ASCII unary temporal operators may be
adjacent, as in ``XX"p"`` or ``GF("p")``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ._syntax import LTL_KEYWORDS as _KEYWORDS, LTL_TEMPORAL_CHAIN as _TEMPORAL_CHAIN


class LTLFormula:
    """Base type for an LTL syntax tree."""

    def __str__(self) -> str:
        """Return textbook display notation; use to_source() for parser input."""
        return _format_formula(self)

    def to_source(self) -> str:
        """Serialize with quoted propositions for :func:`mocha.io.ltl.parse_ltl`."""
        return _format_formula(self, quote_propositions=True)


@dataclass(frozen=True, slots=True)
class BooleanConstant(LTLFormula):
    value: bool


@dataclass(frozen=True, slots=True)
class Proposition(LTLFormula):
    name: str


@dataclass(frozen=True, slots=True)
class Not(LTLFormula):
    operand: LTLFormula


@dataclass(frozen=True, slots=True)
class Next(LTLFormula):
    operand: LTLFormula


@dataclass(frozen=True, slots=True)
class Eventually(LTLFormula):
    operand: LTLFormula


@dataclass(frozen=True, slots=True)
class Always(LTLFormula):
    operand: LTLFormula


@dataclass(frozen=True, slots=True)
class And(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class Or(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class Implies(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class Equiv(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class Until(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class WeakUntil(LTLFormula):
    left: LTLFormula
    right: LTLFormula


@dataclass(frozen=True, slots=True)
class Release(LTLFormula):
    left: LTLFormula
    right: LTLFormula


_UnaryFormula = Not | Next | Eventually | Always
_BinaryFormula = And | Or | Implies | Equiv | Until | WeakUntil | Release


_BINARY_PRINT: dict[type[_BinaryFormula], tuple[int, str, bool]] = {
    And: (4, "∧", False),
    Or: (3, "∨", False),
    Implies: (2, "→", True),
    Equiv: (1, "↔", False),
    Until: (5, "U", True),
    WeakUntil: (5, "W", True),
    Release: (5, "R", True),
}
_UNARY_PRINT: dict[type[_UnaryFormula], str] = {
    Not: "¬", Next: "◯", Eventually: "◇", Always: "□",
}


def _format_formula(
    formula: LTLFormula, minimum_precedence: int = 0, *, quote_propositions: bool = False,
) -> str:
    if isinstance(formula, BooleanConstant):
        return "true" if formula.value else "false"
    if isinstance(formula, Proposition):
        if not quote_propositions and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", formula.name) and (
            formula.name not in _KEYWORDS
            and not _TEMPORAL_CHAIN.fullmatch(formula.name)
        ):
            return formula.name
        return json.dumps(formula.name, ensure_ascii=False)
    for unary_type, symbol in _UNARY_PRINT.items():
        if isinstance(formula, unary_type):
            result = symbol + _format_formula(formula.operand, 6, quote_propositions=quote_propositions)
            return f"({result})" if 6 < minimum_precedence else result
    for binary_type, (precedence, symbol, non_associative) in _BINARY_PRINT.items():
        if isinstance(formula, binary_type):
            left_minimum = precedence + 1 if non_associative else precedence
            right_minimum = precedence + 1
            left = _format_formula(formula.left, left_minimum, quote_propositions=quote_propositions)
            right = _format_formula(formula.right, right_minimum, quote_propositions=quote_propositions)
            result = f"{left} {symbol} {right}"
            return f"({result})" if precedence < minimum_precedence else result
    raise TypeError(f"Unknown LTL formula node: {type(formula).__name__}")


def complement(formula: LTLFormula) -> LTLFormula:
    """Negate a formula, cancelling an outer negation or flipping a constant.

    Other formulas are wrapped in ``Not`` without further normalization.
    """
    if isinstance(formula, Not):
        return formula.operand
    if isinstance(formula, BooleanConstant):
        return BooleanConstant(not formula.value)
    return Not(formula)


def propositions(formula: LTLFormula) -> frozenset[str]:
    """Return the atomic proposition names referenced by a formula."""
    if isinstance(formula, Proposition):
        return frozenset({formula.name})
    if isinstance(formula, BooleanConstant):
        return frozenset()
    if isinstance(formula, (Not, Next, Eventually, Always)):
        return propositions(formula.operand)
    if isinstance(formula, (And, Or, Implies, Equiv, Until, WeakUntil, Release)):
        return propositions(formula.left) | propositions(formula.right)
    raise TypeError(f"Unknown LTL formula node: {type(formula).__name__}")


__all__ = [
    "Always", "And", "BooleanConstant", "Equiv", "Eventually", "Implies",
    "LTLFormula", "Next", "Not", "Or", "Proposition",
    "Release", "Until", "WeakUntil", "complement", "propositions",
]
