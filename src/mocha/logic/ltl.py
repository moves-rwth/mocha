"""Immutable LTL syntax trees, formatting, and transformations.

Precedence, from strongest to weakest: ``! X F G``, ``U W R``, ``&``, ``|``,
``->``, ``<->``. Unary operators, ``U``, ``W``, ``R``, and ``->`` associate to the
right. Parentheses override precedence. Both ASCII and textbook Unicode
operator spellings are accepted; string output uses the latter.
Propositions must be double-quoted. ASCII unary temporal operators may be
adjacent, as in ``XX"p"`` or ``GF("p")``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Callable, Literal

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


@dataclass(frozen=True, slots=True)
class LTLRewriteStep:
    """One immutable snapshot in a formula transformation.

    ``formula`` is the entire formula after the rewrite. ``path`` locates the
    replaced subformula in the preceding snapshot, using ``operand``, ``left``,
    and ``right`` as path components. The initial snapshot has rule ``initial``
    and no local ``before`` or ``after`` formula.
    """

    iteration: int
    rule: str
    formula: LTLFormula
    path: tuple[str, ...]
    before: LTLFormula | None
    after: LTLFormula | None


_BINARY_PRINT = {
    And: (4, "∧", False),
    Or: (3, "∨", False),
    Implies: (2, "→", True),
    Equiv: (1, "↔", False),
    Until: (5, "U", True),
    WeakUntil: (5, "W", True),
    Release: (5, "R", True),
}
_UNARY_PRINT = {Not: "¬", Next: "◯", Eventually: "◇", Always: "□"}


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
    for node_type, symbol in _UNARY_PRINT.items():
        if isinstance(formula, node_type):
            result = symbol + _format_formula(formula.operand, 6, quote_propositions=quote_propositions)
            return f"({result})" if 6 < minimum_precedence else result
    for node_type, (precedence, symbol, right_associative) in _BINARY_PRINT.items():
        if isinstance(formula, node_type):
            left_minimum = precedence + 1 if right_associative else precedence
            right_minimum = precedence if right_associative else precedence + 1
            left = _format_formula(formula.left, left_minimum, quote_propositions=quote_propositions)
            right = _format_formula(formula.right, right_minimum, quote_propositions=quote_propositions)
            result = f"{left} {symbol} {right}"
            return f"({result})" if precedence < minimum_precedence else result
    raise TypeError(f"Unknown LTL formula node: {type(formula).__name__}")


_Mode = Literal["core", "weak_until", "release"]


def _local_rewrite(
    formula: LTLFormula,
    mode: _Mode,
) -> tuple[str, LTLFormula] | None:
    """Apply one rule at the current node, before visiting its children."""
    if isinstance(formula, Not):
        operand = formula.operand
        if isinstance(operand, BooleanConstant):
            return "negate_constant", BooleanConstant(not operand.value)
        if isinstance(operand, Not):
            return "double_negation", operand.operand
        if mode != "core":
            if isinstance(operand, And):
                return "de_morgan_and", Or(Not(operand.left), Not(operand.right))
            if isinstance(operand, Or):
                return "de_morgan_or", And(Not(operand.left), Not(operand.right))
            if isinstance(operand, Next):
                return "negate_next", Next(Not(operand.operand))
            if isinstance(operand, Until):
                if mode == "release":
                    return "negate_until", Release(
                        Not(operand.left), Not(operand.right)
                    )
                not_right = Not(operand.right)
                return "negate_until", WeakUntil(
                    And(operand.left, not_right),
                    And(Not(operand.left), not_right),
                )
            if isinstance(operand, WeakUntil):
                not_right = Not(operand.right)
                return "negate_weak_until", Until(
                    And(operand.left, not_right),
                    And(Not(operand.left), not_right),
                )
            if isinstance(operand, Release):
                return "negate_release", Until(
                    Not(operand.left), Not(operand.right)
                )
            if isinstance(operand, Eventually):
                negative_child = Not(operand.operand)
                if mode == "weak_until":
                    return "negate_eventually", WeakUntil(
                        negative_child, BooleanConstant(False)
                    )
                return "negate_eventually", Release(
                    BooleanConstant(False), negative_child
                )
            if isinstance(operand, Always):
                return "negate_always", Until(
                    BooleanConstant(True), Not(operand.operand)
                )
            if isinstance(operand, Implies):
                return "negate_implication", And(
                    operand.left, Not(operand.right)
                )
            if isinstance(operand, Equiv):
                return "negate_equivalence", Or(
                    And(operand.left, Not(operand.right)),
                    And(Not(operand.left), operand.right),
                )

    if mode == "core":
        if isinstance(formula, Or):
            return "eliminate_or", Not(And(Not(formula.left), Not(formula.right)))
        if isinstance(formula, Implies):
            return "eliminate_implication", Not(
                And(formula.left, Not(formula.right))
            )
        if isinstance(formula, Equiv):
            return "eliminate_equivalence", And(
                Not(And(formula.left, Not(formula.right))),
                Not(And(formula.right, Not(formula.left))),
            )
        if isinstance(formula, Eventually):
            return "eliminate_eventually", Until(
                BooleanConstant(True), formula.operand
            )
        if isinstance(formula, Always):
            return "eliminate_always", Not(
                Until(BooleanConstant(True), Not(formula.operand))
            )
        if isinstance(formula, WeakUntil):
            not_right = Not(formula.right)
            return "eliminate_weak_until", Not(Until(
                And(formula.left, not_right),
                And(Not(formula.left), not_right),
            ))
        if isinstance(formula, Release):
            return "eliminate_release", Not(Until(
                Not(formula.left), Not(formula.right)
            ))
    else:
        if isinstance(formula, Implies):
            return "eliminate_implication", Or(Not(formula.left), formula.right)
        if isinstance(formula, Equiv):
            return "eliminate_equivalence", Or(
                And(formula.left, formula.right),
                And(Not(formula.left), Not(formula.right)),
            )
        if isinstance(formula, Eventually):
            return "eliminate_eventually", Until(
                BooleanConstant(True), formula.operand
            )
        if isinstance(formula, Always):
            if mode == "weak_until":
                return "eliminate_always", WeakUntil(
                    formula.operand, BooleanConstant(False)
                )
            return "eliminate_always", Release(
                BooleanConstant(False), formula.operand
            )
        if isinstance(formula, WeakUntil) and mode == "release":
            return "eliminate_weak_until", Release(
                formula.right, Or(formula.left, formula.right)
            )
        if isinstance(formula, Release) and mode == "weak_until":
            return "eliminate_release", WeakUntil(
                And(Not(formula.left), formula.right),
                And(formula.left, formula.right),
            )
    return None


def _first_rewrite(
    formula: LTLFormula,
    mode: _Mode,
) -> tuple[LTLFormula, tuple[str, ...], str, LTLFormula, LTLFormula] | None:
    """Find the first rewrite and embed it in the entire current formula."""
    local = _local_rewrite(formula, mode)
    if local is not None:
        rule, replacement = local
        return replacement, (), rule, formula, replacement

    if isinstance(formula, (Not, Next, Eventually, Always)):
        nested = _first_rewrite(formula.operand, mode)
        if nested is None:
            return None
        child, path, rule, before, after = nested
        return replace(formula, operand=child), ("operand",) + path, rule, before, after
    if isinstance(formula, (And, Or, Implies, Equiv, Until, WeakUntil, Release)):
        for side in ("left", "right"):
            nested = _first_rewrite(getattr(formula, side), mode)
            if nested is not None:
                child, path, rule, before, after = nested
                return (replace(formula, **{side: child}),
                        (side,) + path, rule, before, after)
        return None
    if isinstance(formula, (BooleanConstant, Proposition)):
        return None
    raise TypeError(f"Unknown LTL formula node: {type(formula).__name__}")


def _transform(
    formula: LTLFormula,
    mode: _Mode,
    on_step: Callable[[LTLRewriteStep], None] | None,
) -> LTLFormula:
    if on_step is not None:
        on_step(LTLRewriteStep(0, "initial", formula, (), None, None))
    current = formula
    iteration = 0
    while rewrite := _first_rewrite(current, mode):
        current, path, rule, before, after = rewrite
        iteration += 1
        if on_step is not None:
            on_step(LTLRewriteStep(iteration, rule, current, path, before, after))
    return current


def normalize_ltl(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLRewriteStep], None] | None = None,
) -> LTLFormula:
    """Rewrite a formula using only ``&``, ``!``, ``X``, and ``U``.

    Boolean constants and atomic propositions remain as leaves. This is an
    operator normalization, not positive normal form: negation may still apply
    to an ``Until`` formula. The result is equivalent on infinite words and
    applying this function again leaves it unchanged. ``on_step`` receives an
    initial snapshot and one snapshot after every local rewrite.
    """
    return _transform(formula, "core", on_step)


def to_weak_until_pnf(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLRewriteStep], None] | None = None,
) -> LTLFormula:
    """Return weak-until PNF: negation only on atoms, using ``U`` and ``W``.

    Other permitted nodes are Boolean constants, propositions, ``And``,
    ``Or``, and ``Next``. This follows Definition 5.20 in *Principles of Model
    Checking*. The result is equivalent to ``formula`` on infinite words.
    ``on_step`` receives an initial snapshot and each local rewrite.
    """
    return _transform(formula, "weak_until", on_step)


def to_release_pnf(
    formula: LTLFormula,
    *,
    on_step: Callable[[LTLRewriteStep], None] | None = None,
) -> LTLFormula:
    """Return release PNF: negation only on atoms, using ``U`` and ``R``.

    Other permitted nodes are Boolean constants, propositions, ``And``,
    ``Or``, and ``Next``. This follows Definition 5.23 in *Principles of Model
    Checking*. The result is equivalent to ``formula`` on infinite words.
    ``on_step`` receives an initial snapshot and each local rewrite.
    """
    return _transform(formula, "release", on_step)


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
    "LTLFormula", "LTLRewriteStep", "Next", "Not",
    "Or", "Proposition",
    "Release", "Until", "WeakUntil", "normalize_ltl",
    "propositions", "to_release_pnf", "to_weak_until_pnf",
]
