"""CTL normal forms and traces of their local rewrite steps.

Formula types and formatting live in :mod:`mocha.logic.ctl`. These
transformations require no automaton construction or decision procedures.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from mocha.logic.ctl import (
    Always, And, BooleanConstant, CTLFormula, CTLStateFormula,
    Eventually, Exists, ForAll, Next, Not, Proposition, Until, WeakUntil,
    is_ctl_formula,
)

from .trace import AlgorithmTrace


@dataclass(frozen=True, slots=True)
class CTLRewriteStep:
    """One full-formula snapshot after a local normalization rewrite.

    ``path`` locates ``before`` in the preceding formula, using ``operand``,
    ``left``, and ``right`` as path components. The initial snapshot has no
    local ``before`` or ``after`` formula.
    """

    iteration: int
    rule: str
    formula: CTLStateFormula
    path: tuple[str, ...]
    before: CTLStateFormula | None
    after: CTLStateFormula | None


def _local_rewrite(formula: CTLFormula) -> tuple[str, CTLStateFormula] | None:
    if isinstance(formula, BooleanConstant) and not formula.value:
        return "eliminate_false", Not(BooleanConstant(True))
    if isinstance(formula, Not) and isinstance(formula.operand, Not):
        return "double_negation", formula.operand.operand
    if isinstance(formula, Exists):
        path = formula.operand
        if isinstance(path, Eventually):
            return "eliminate_ef", Exists(Until(BooleanConstant(True), path.operand))
        if isinstance(path, WeakUntil):
            # E(p W q) = E(p U q) ∨ EG p; express disjunction using Not/And.
            return "eliminate_ew", Not(And(
                Not(Exists(Until(path.left, path.right))), Not(Exists(Always(path.left))),
            ))
    if isinstance(formula, ForAll):
        path = formula.operand
        if isinstance(path, Next):
            return "eliminate_ax", Not(Exists(Next(Not(path.operand))))
        if isinstance(path, Eventually):
            return "eliminate_af", Not(Exists(Always(Not(path.operand))))
        if isinstance(path, Always):
            return "eliminate_ag", Not(Exists(Until(BooleanConstant(True), Not(path.operand))))
        if isinstance(path, Until):
            not_right = Not(path.right)
            return "eliminate_au", And(
                Not(Exists(Until(not_right, And(Not(path.left), not_right)))),
                Not(Exists(Always(not_right))),
            )
        if isinstance(path, WeakUntil):
            not_right = Not(path.right)
            return "eliminate_aw", Not(Exists(Until(
                And(path.left, not_right),
                And(Not(path.left), not_right),
            )))
    return None


def _first_rewrite(
    formula: CTLFormula,
) -> tuple[CTLFormula, tuple[str, ...], str, CTLStateFormula, CTLStateFormula] | None:
    """Find the first local rewrite and embed it in the whole formula."""
    local = _local_rewrite(formula)
    if local is not None:
        rule, replacement = local
        assert isinstance(formula, CTLStateFormula)
        return replacement, (), rule, formula, replacement

    if isinstance(formula, (Not, Exists, ForAll, Next, Always, Eventually)):
        nested = _first_rewrite(formula.operand)
        if nested is None:
            return None
        child, path, rule, before, after = nested
        return replace(formula, operand=child), ("operand",) + path, rule, before, after
    if isinstance(formula, (And, Until, WeakUntil)):
        for side in ("left", "right"):
            nested = _first_rewrite(getattr(formula, side))
            if nested is not None:
                child, path, rule, before, after = nested
                return replace(formula, **{side: child}), (side,) + path, rule, before, after
        return None
    if isinstance(formula, (BooleanConstant, Proposition)):
        return None
    raise TypeError(f"Unknown CTL formula node: {type(formula).__name__}")


def to_existential_normal_form(
    formula: CTLStateFormula,
    *,
    on_step: Callable[[CTLRewriteStep], None] | None = None,
) -> CTLStateFormula:
    """Rewrite a CTL formula into existential normal form.

    The result uses only ``true``, propositions, ``Not``, ``And``, and
    ``Exists`` wrapping ``Next``, ``Until``, or ``Always``.
    Negation may apply to any state formula. Equivalence
    assumes infinite paths, as in transition systems without terminal states.
    ``on_step`` receives the initial formula and each local rewrite snapshot.
    """
    if not isinstance(formula, CTLStateFormula):
        raise TypeError("Expected a CTL state formula")
    if not is_ctl_formula(formula):
        raise ValueError("Expected a state formula in the supported CTL fragment")
    if on_step is not None:
        on_step(CTLRewriteStep(0, "initial", formula, (), None, None))
    current = formula
    iteration = 0
    while rewrite := _first_rewrite(current):
        rewritten, path, rule, before, after = rewrite
        assert isinstance(rewritten, CTLStateFormula)
        current = rewritten
        iteration += 1
        if on_step is not None:
            on_step(CTLRewriteStep(iteration, rule, current, path, before, after))
    return current


def trace_existential_normal_form(
    formula: CTLStateFormula,
) -> AlgorithmTrace[CTLStateFormula, CTLRewriteStep]:
    """Return the existential-normal-form formula and every rewrite snapshot."""
    steps: list[CTLRewriteStep] = []
    result = to_existential_normal_form(formula, on_step=steps.append)
    return AlgorithmTrace(result=result, steps=tuple(steps))


__all__ = [
    "CTLRewriteStep", "to_existential_normal_form", "trace_existential_normal_form",
]
