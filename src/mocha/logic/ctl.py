"""Immutable CTL syntax trees and formatting.

The supported abstract syntax is given by the mutually recursive grammar::

    state ::= BooleanConstant(bool)
            | Proposition(str)
            | Not(state)
            | And(state, state)
            | Exists(path)
            | ForAll(path)

    path ::= Next(state)
           | Always(state)
           | Eventually(state)
           | Until(state, state)
           | WeakUntil(state, state)

Here ``bool`` and ``str`` denote Python values. Only ``state`` is a complete
CTL formula; ``path`` is the operand of a quantifier. Every temporal operator
takes state formulae, so temporal nesting must pass through a quantifier:
``ForAll(Always(ForAll(Eventually(p))))`` is valid, whereas
``ForAll(Always(Eventually(p)))`` is not.

In source notation, the existential productions are ``EX``, ``EF``, ``EG``,
``E(φ U ψ)``, and ``E(φ W ψ)``. Universal productions are ``AX``, ``AF``,
``AG``, ``A(φ U ψ)``, and ``A(φ W ψ)``, where ``φ`` and ``ψ`` are state
formulae. Both quantifiers accept the same path grammar.
Propositions must be double-quoted in source. ASCII and textbook Unicode
operators are accepted; ``to_source()`` produces parseable Unicode notation.

State formulae and path formulae have distinct types. Construct quantified
formulae explicitly, for example ``Exists(Next(Proposition("p")))`` for
``EX "p"``. CTL temporal operators take state formulae as operands.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ._syntax import CTL_KEYWORDS as _KEYWORDS, CTL_OPERATOR_CHAIN as _OPERATOR_CHAIN
from .formula import Formula, PathFormula, StateFormula


class CTLFormula(Formula):
    """Base type for CTL state and path syntax trees."""

    def __str__(self) -> str:
        return _format_formula(self)

    def to_source(self) -> str:
        """Serialize this tree; state formulae can be read by ``parse_ctl``."""
        return _format_formula(self, quote_propositions=True)


class CTLStateFormula(CTLFormula, StateFormula):
    """A CTL formula evaluated at a state."""


class CTLPathFormula(CTLFormula, PathFormula):
    """A temporal operator applied to CTL state formulae."""


@dataclass(frozen=True, slots=True)
class BooleanConstant(CTLStateFormula):
    value: bool


@dataclass(frozen=True, slots=True)
class Proposition(CTLStateFormula):
    name: str


@dataclass(frozen=True, slots=True)
class Not(CTLStateFormula):
    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class And(CTLStateFormula):
    left: CTLStateFormula
    right: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.left)
        _require_state_formula(self.right)


@dataclass(frozen=True, slots=True)
class Next(CTLPathFormula):
    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Always(CTLPathFormula):
    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Eventually(CTLPathFormula):
    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Until(CTLPathFormula):
    left: CTLStateFormula
    right: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.left)
        _require_state_formula(self.right)


@dataclass(frozen=True, slots=True)
class WeakUntil(CTLPathFormula):
    left: CTLStateFormula
    right: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.left)
        _require_state_formula(self.right)


@dataclass(frozen=True, slots=True)
class Exists(CTLStateFormula):
    """Existential path quantifier."""

    operand: CTLPathFormula

    def __post_init__(self) -> None:
        if not isinstance(self.operand, CTLPathFormula):
            raise TypeError("Exists requires a CTL path formula")


@dataclass(frozen=True, slots=True)
class ForAll(CTLStateFormula):
    """Universal path quantifier."""

    operand: CTLPathFormula

    def __post_init__(self) -> None:
        if not isinstance(self.operand, CTLPathFormula):
            raise TypeError("ForAll requires a CTL path formula")


def _require_state_formula(formula: CTLStateFormula) -> None:
    if not isinstance(formula, CTLStateFormula):
        raise TypeError("Expected a CTL state formula")


def is_ctl_formula(formula: Formula) -> bool:
    """Whether a tree belongs to the supported CTL state-formula fragment.

    Each quantifier must wrap exactly one temporal operator whose operands
    are themselves CTL state formulae. Bare path formulae and formulae from
    other logics are rejected. This check does not require normal form.
    """
    if isinstance(formula, (BooleanConstant, Proposition)):
        return True
    if isinstance(formula, Not):
        return is_ctl_formula(formula.operand)
    if isinstance(formula, And):
        return is_ctl_formula(formula.left) and is_ctl_formula(formula.right)
    if isinstance(formula, (Exists, ForAll)):
        path = formula.operand
        if isinstance(path, (Next, Always, Eventually)):
            return is_ctl_formula(path.operand)
        if isinstance(path, (Until, WeakUntil)):
            return is_ctl_formula(path.left) and is_ctl_formula(path.right)
    return False


def _format_formula(
    formula: CTLFormula, minimum_precedence: int = 0, *, quote_propositions: bool = False,
) -> str:
    if isinstance(formula, BooleanConstant):
        return "true" if formula.value else "false"
    if isinstance(formula, Proposition):
        if not quote_propositions and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", formula.name) and (
            formula.name not in _KEYWORDS and not _OPERATOR_CHAIN.fullmatch(formula.name)
        ):
            return formula.name
        return json.dumps(formula.name, ensure_ascii=False)
    if isinstance(formula, And):
        result = (
            f"{_format_formula(formula.left, 1, quote_propositions=quote_propositions)} ∧ "
            f"{_format_formula(formula.right, 2, quote_propositions=quote_propositions)}"
        )
        return f"({result})" if minimum_precedence > 1 else result
    if isinstance(formula, Not):
        result = "¬" + _format_formula(formula.operand, 3, quote_propositions=quote_propositions)
    elif isinstance(formula, (Exists, ForAll)):
        quantifier = "∃" if isinstance(formula, Exists) else "∀"
        result = quantifier + _format_formula(formula.operand, 3, quote_propositions=quote_propositions)
    elif isinstance(formula, (Next, Always, Eventually)):
        if isinstance(formula, Next):
            operator = "◯"
        elif isinstance(formula, Always):
            operator = "□"
        else:
            operator = "◇"
        result = operator + _format_formula(formula.operand, 3, quote_propositions=quote_propositions)
    elif isinstance(formula, (Until, WeakUntil)):
        operator = "U" if isinstance(formula, Until) else "W"
        result = (
            "("
            + _format_formula(formula.left, quote_propositions=quote_propositions)
            + f" {operator} "
            + _format_formula(formula.right, quote_propositions=quote_propositions)
            + ")"
        )
    else:
        raise TypeError(f"Unknown CTL formula node: {type(formula).__name__}")
    return f"({result})" if minimum_precedence > 3 else result


def propositions(formula: CTLFormula) -> frozenset[str]:
    """Return proposition names referenced by a CTL formula."""
    if isinstance(formula, Proposition):
        return frozenset({formula.name})
    if isinstance(formula, BooleanConstant):
        return frozenset()
    if isinstance(formula, (Not, Exists, ForAll, Next, Always, Eventually)):
        return propositions(formula.operand)
    if isinstance(formula, (And, Until, WeakUntil)):
        return propositions(formula.left) | propositions(formula.right)
    raise TypeError(f"Unknown CTL formula node: {type(formula).__name__}")


__all__ = [
    "Always", "And", "BooleanConstant", "CTLFormula",
    "CTLPathFormula", "CTLStateFormula", "Eventually",
    "Exists", "ForAll", "Next", "Not", "Proposition", "Until", "WeakUntil",
    "is_ctl_formula", "propositions",
]
