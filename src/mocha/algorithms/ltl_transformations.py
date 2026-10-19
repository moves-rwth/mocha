"""LTL normal forms and traces of their local rewrite steps.

Formula types and formatting live in :mod:`mocha.logic.ltl`. These
transformations require no automaton construction or decision procedures.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Literal

from mocha.logic.ltl import (
    Always, And, BooleanConstant, Equiv, Eventually, Implies,
    LTLFormula, Next, Not, Or, Proposition, Release, Until, WeakUntil,
)

from .trace import AlgorithmTrace


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


def trace_normalize_ltl(
    formula: LTLFormula,
) -> AlgorithmTrace[LTLFormula, LTLRewriteStep]:
    """Return the core-operator formula and every local rewrite snapshot."""
    steps: list[LTLRewriteStep] = []
    result = normalize_ltl(formula, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


def trace_weak_until_pnf(
    formula: LTLFormula,
) -> AlgorithmTrace[LTLFormula, LTLRewriteStep]:
    """Return weak-until PNF and every local rewrite snapshot."""
    steps: list[LTLRewriteStep] = []
    result = to_weak_until_pnf(formula, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


def trace_release_pnf(
    formula: LTLFormula,
) -> AlgorithmTrace[LTLFormula, LTLRewriteStep]:
    """Return release PNF and every local rewrite snapshot."""
    steps: list[LTLRewriteStep] = []
    result = to_release_pnf(formula, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


__all__ = [
    "LTLRewriteStep",
    "normalize_ltl",
    "to_release_pnf",
    "to_weak_until_pnf",
    "trace_normalize_ltl",
    "trace_release_pnf",
    "trace_weak_until_pnf",
]
