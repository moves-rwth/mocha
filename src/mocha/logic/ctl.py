"""Immutable CTL syntax trees and formatting.

Following the notation of Definition 6.1 in *Principles of Model Checking*,
the supported grammar, including derived operators, is::

    Φ ::= true | false | a | Φ₁ ∧ Φ₂ | ¬Φ | ∃φ | ∀φ
    φ ::= ◯Φ | Φ₁ U Φ₂ | ◇Φ | □Φ | Φ₁ W Φ₂

Here ``a ∈ AP``, uppercase ``Φ`` denotes a state formula, and lowercase ``φ``
denotes a path formula. These correspond to ``CTLStateFormula`` and
``CTLPathFormula``. A complete CTL formula is a state formula.

Each path formula contains one temporal operator with state-formula operands.
Temporal nesting therefore passes through another path quantifier:
``∀□∀◇a`` is valid CTL, whereas ``∀□◇a`` is not.

Construct the syntax tree with explicit quantifier and temporal nodes:
``∃◯a`` is ``Exists(Next(Proposition("a")))``. ASCII input spells this
``EX "a"`` or ``E X "a"``. The other temporal operators use ``F``, ``G``,
``U``, and ``W``, and universal quantification uses ``A``. Proposition names
must be double-quoted in source. ``to_source()`` produces parseable Unicode
notation; the parser's concrete grammar lives in :mod:`mocha.io.ctl`.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re

from ._syntax import CTL_KEYWORDS as _KEYWORDS, CTL_OPERATOR_CHAIN as _OPERATOR_CHAIN
from .formula import Formula, PathFormula, StateFormula


# The basic grammar uses true, a, ∧, ¬, ∃, ∀, ◯, and U as the primitive syntax.
# We also keep false, ◇, □, and W as explicit nodes for readable input and
# rewrite traces. Normalization eliminates them as required by the target form.


class CTLFormula(Formula):
    """Base type for CTL state and path syntax trees."""

    def __str__(self) -> str:
        return _format_formula(self)

    def to_source(self) -> str:
        """Serialize this tree; state formulae can be read by ``parse_ctl``."""
        return _format_formula(self, quote_propositions=True)


class CTLStateFormula(CTLFormula, StateFormula):
    """A state formula ``Φ``, evaluated at a state of a transition system."""


class CTLPathFormula(CTLFormula, PathFormula):
    """A path formula ``φ``: one temporal operator with state-formula operands."""


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
    """The next state on the path satisfies ``operand``."""

    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Always(CTLPathFormula):
    """Every state on the path, including the first, satisfies ``operand``."""

    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Eventually(CTLPathFormula):
    """Some state on the path, possibly the first, satisfies ``operand``."""

    operand: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.operand)


@dataclass(frozen=True, slots=True)
class Until(CTLPathFormula):
    """``right`` eventually holds, and ``left`` holds at every earlier state."""

    left: CTLStateFormula
    right: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.left)
        _require_state_formula(self.right)


@dataclass(frozen=True, slots=True)
class WeakUntil(CTLPathFormula):
    """Until, also allowing ``left`` to hold forever without ``right`` occurring."""

    left: CTLStateFormula
    right: CTLStateFormula

    def __post_init__(self) -> None:
        _require_state_formula(self.left)
        _require_state_formula(self.right)


@dataclass(frozen=True, slots=True)
class Exists(CTLStateFormula):
    """Some infinite path from the current state satisfies ``operand``."""

    operand: CTLPathFormula

    def __post_init__(self) -> None:
        if not isinstance(self.operand, CTLPathFormula):
            raise TypeError("Exists requires a CTL path formula")


@dataclass(frozen=True, slots=True)
class ForAll(CTLStateFormula):
    """Every infinite path from the current state satisfies ``operand``."""

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
