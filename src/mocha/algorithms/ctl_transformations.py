"""CTL normal forms and traces of their local rewrite steps.

Formula types and formatting live in :mod:`mocha.logic.ctl`. These
transformations require no automaton construction or decision procedures.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from mocha.logic.ctl import (
    Always, And, BooleanConstant, CTLFormula, CTLPathFormula, CTLStateFormula,
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
    """Apply one equivalence at the root; operands are normalized separately."""
    if isinstance(formula, BooleanConstant) and not formula.value:
        return "eliminate_false", Not(BooleanConstant(True))
    if isinstance(formula, Not) and isinstance(formula.operand, Not):
        return "double_negation", formula.operand.operand
    if isinstance(formula, Exists):
        path = formula.operand
        if isinstance(path, Eventually):
            # EF p ≡ E(true U p).
            return "eliminate_ef", Exists(Until(BooleanConstant(True), path.operand))
        if isinstance(path, WeakUntil):
            # E(p W q) ≡ E(p U q) ∨ EG p. Encode a ∨ b as ¬(¬a ∧ ¬b).
            until = Exists(Until(path.left, path.right))
            globally = Exists(Always(path.left))
            return "eliminate_ew", Not(And(Not(until), Not(globally)))
    if isinstance(formula, ForAll):
        path = formula.operand
        if isinstance(path, Next):
            # AX p ≡ ¬EX ¬p.
            return "eliminate_ax", Not(Exists(Next(Not(path.operand))))
        if isinstance(path, Eventually):
            # AF p ≡ ¬EG ¬p.
            return "eliminate_af", Not(Exists(Always(Not(path.operand))))
        if isinstance(path, Always):
            # AG p ≡ ¬E(true U ¬p).
            return "eliminate_ag", Not(Exists(Until(BooleanConstant(True), Not(path.operand))))
        if isinstance(path, Until):
            # A(p U q) fails if p fails before q, or q never occurs.
            not_right = Not(path.right)
            bad_prefix = Exists(Until(not_right, And(Not(path.left), not_right)))
            never_right = Exists(Always(not_right))
            return "eliminate_au", And(Not(bad_prefix), Not(never_right))
        if isinstance(path, WeakUntil):
            # A(p W q) permits q never occurring; only a bad prefix refutes it.
            not_right = Not(path.right)
            bad_prefix = Exists(Until(
                And(path.left, not_right),
                And(Not(path.left), not_right),
            ))
            return "eliminate_aw", Not(bad_prefix)
    return None


def _first_rewrite(
    formula: CTLFormula,
) -> tuple[CTLFormula, tuple[str, ...], str, CTLStateFormula, CTLStateFormula] | None:
    """Search root first, then operands from left to right, for one rewrite.

    Rebuild the surrounding tree and record the changed subtree's location.
    Taking one step at a time makes every equivalence visible in the trace.
    """
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
        if isinstance(formula, (Exists, ForAll)):
            assert isinstance(child, CTLPathFormula)
            return replace(formula, operand=child), ("operand",) + path, rule, before, after
        assert isinstance(child, CTLStateFormula)
        return replace(formula, operand=child), ("operand",) + path, rule, before, after
    if isinstance(formula, (And, Until, WeakUntil)):
        nested = _first_rewrite(formula.left)
        if nested is not None:
            child, path, rule, before, after = nested
            assert isinstance(child, CTLStateFormula)
            return replace(formula, left=child), ("left",) + path, rule, before, after
        nested = _first_rewrite(formula.right)
        if nested is not None:
            child, path, rule, before, after = nested
            assert isinstance(child, CTLStateFormula)
            return replace(formula, right=child), ("right",) + path, rule, before, after
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
