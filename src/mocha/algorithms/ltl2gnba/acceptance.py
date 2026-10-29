"""Build generalized Büchi acceptance sets that discharge UNTIL obligations.

Local elementary-set and transition rules can keep an UNTIL obligation pending
forever. One acceptance set per UNTIL formula rules out such runs by requiring
infinitely many states where the obligation is absent or its right operand
holds. Decisions retain the supplied state order for explanations.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from mocha.logic.ltl import LTLFormula, Until

from ..trace import AlgorithmTrace
from .elementary_set_validation import _validate_elementary_sets


@dataclass(frozen=True)
class AcceptanceDecision:
    """Explain one state's membership in a particular UNTIL acceptance set.

    ``state_index`` is the zero-based position of ``state`` in the supplied
    collection; display labels add one to obtain B1, B2, etc. ``included`` says
    whether the state belongs to this acceptance set. ``reason`` distinguishes
    an absent obligation (``until_absent``), a fulfilled obligation
    (``right_present``), and an unfulfilled obligation (``until_pending``).
    ``message`` provides the corresponding explanation for display.
    """

    state_index: int
    state: frozenset[LTLFormula]
    included: bool
    reason: Literal["until_absent", "right_present", "until_pending"]
    message: str


@dataclass(frozen=True)
class AcceptanceCondition:
    """The generalized Büchi set associated with one ``formula`` of form ψ U χ.

    ``accepting_states`` contains exactly the elementary sets B for which
    ψ U χ is absent or χ is present. ``state_indices`` identifies those same
    states by their zero-based positions in the supplied collection. An
    accepting infinite run must visit this set infinitely often.
    """

    formula: Until
    accepting_states: frozenset[frozenset[LTLFormula]]
    state_indices: frozenset[int]


@dataclass(frozen=True)
class AcceptanceStep:
    """One UNTIL acceptance set, with a decision for every elementary set.

    If no UNTIL occurs, a single explanatory step has ``condition=None``.
    Its ``decisions`` tuple is empty. Otherwise, decisions follow the original
    elementary-set order and ``condition`` contains the resulting acceptance
    set. ``iteration`` is zero-based, following UNTIL formulas sorted by their
    string representations; ``message`` explains the membership rule.
    """

    iteration: int
    condition: AcceptanceCondition | None
    decisions: tuple[AcceptanceDecision, ...]
    message: str

    def to_markdown(self) -> str:
        """Render the rule, per-state decisions, and resulting set using B labels.

        An empty acceptance set is rendered as ``F = {}``. The no-UNTIL step
        instead renders only its explanation, since it defines no set.
        """
        lines = [self.message, ""]
        lines.extend(f"- {decision.message}" for decision in self.decisions)
        if self.condition is not None:
            names = ", ".join(f"B{i + 1}" for i in sorted(self.condition.state_indices))
            lines.extend(["", f"F = {{{names}}}."])
        return "\n".join(lines).rstrip()


@dataclass(frozen=True)
class AcceptanceResult:
    """Retain the ordered acceptance conditions and expose their GNBA family.

    ``conditions`` has one entry per UNTIL formula, sorted by formula string,
    even when several entries have identical accepting states. With no UNTIL
    formulas it is empty. ``accepting_sets`` deduplicates equal state sets for
    use in the automaton without losing the per-formula explanations here.
    """

    conditions: tuple[AcceptanceCondition, ...]

    @property
    def accepting_sets(self) -> frozenset[frozenset[frozenset[LTLFormula]]]:
        """Return the distinct acceptance sets, preserving any empty member set."""
        return frozenset(condition.accepting_states for condition in self.conditions)


def compute_acceptance_sets(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
    *,
    on_step: Callable[[AcceptanceStep], None] | None = None,
) -> AcceptanceResult:
    """For each ψ U χ, build F = {B | ψ U χ ∉ B or χ ∈ B}.

    These sets must each be visited infinitely often; they are not terminal
    states. With no UNTIL subformulas the acceptance family is empty, so every
    infinite run meets it. This differs from a family containing an empty set,
    which no run can meet. Indices retain the elementary-set order (zero-based).

    The formula's closure supplies the UNTIL obligations, including those whose
    positive formula is absent from every supplied state. Each state is checked
    and frozen, and duplicates are rejected before callbacks begin. No
    enumeration, completeness check, initial-state selection, or transition
    construction is performed. For the full GNBA, supply all elementary sets.
    A subset, including an empty collection, yields acceptance sets restricted
    to those states; completeness can be verified separately with
    ``check_elementary_set_collection``.

    Args:
        formula: Formula already normalized by ``normalize_ltl``. Its closure
            determines the UNTIL formulas, independently of the supplied states.
        elementary_sets: Iterable of states containing formula objects, checked
            with ``check_elementary_set``. Double negations and negated constants
            are simplified as in the checker. Use a list or tuple for predictable
            state indices; input iterators are consumed once.
        on_step: Optional synchronous callback, called once per UNTIL formula
            in formula-string order with all state decisions. With no UNTIL
            formulas, it receives one explanatory step with no condition.

    Returns:
        One condition per UNTIL formula, retaining duplicate state sets so that
        each obligation can be inspected independently.

    Raises:
        TypeError: If the formula or a state member has the wrong type.
        ValueError: If the formula is not normalized, a state is not elementary,
            or states are duplicated after simplifying equivalent spellings.
    """
    closure, states = _validate_elementary_sets(formula, elementary_sets)
    untils = sorted((node for node in closure if isinstance(node, Until)), key=str)
    conditions = []
    for iteration, node in enumerate(untils):
        decisions = []
        indices = set()
        for index, state in enumerate(states):
            reason: Literal["until_absent", "right_present", "until_pending"]
            if node not in state:
                included, reason = True, "until_absent"
                explanation = f"({node}) is absent; there is no pending obligation."
            elif node.right in state:
                included, reason = True, "right_present"
                explanation = f"({node.right}) is present; the UNTIL obligation is fulfilled."
            else:
                included, reason = False, "until_pending"
                explanation = f"({node}) is present but ({node.right}) is absent; the obligation is pending."
            if included:
                indices.add(index)
            action = "Include" if included else "Exclude"
            decisions.append(AcceptanceDecision(index, state, included, reason,
                                                f"{action} B{index + 1}: {explanation}"))
        condition = AcceptanceCondition(node,
                                        frozenset(states[i] for i in indices),
                                        frozenset(indices))
        conditions.append(condition)
        if on_step is not None:
            on_step(AcceptanceStep(iteration, condition, tuple(decisions),
                                   f"For ({node}), include B in F if the UNTIL formula is absent "
                                   f"or its right operand ({node.right}) is present."))
    if not untils and on_step is not None:
        on_step(AcceptanceStep(0, None, (),
                               "There are no UNTIL formulas. The acceptance family is empty; "
                               "every infinite run satisfies its acceptance condition."))
    return AcceptanceResult(tuple(conditions))


def trace_acceptance_sets(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
) -> AlgorithmTrace[AcceptanceResult, AcceptanceStep]:
    """Collect the acceptance result and all membership explanations in order.

    Inputs and validation match ``compute_acceptance_sets``. The trace has one
    step per UNTIL formula in the input's closure, or one explanatory step if
    none occur. Each step's state decisions follow supplied order. Collection
    completeness is a separate check.
    """
    steps: list[AcceptanceStep] = []
    result = compute_acceptance_sets(formula, elementary_sets, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = [
    "AcceptanceCondition", "AcceptanceDecision", "AcceptanceResult", "AcceptanceStep",
    "compute_acceptance_sets", "trace_acceptance_sets",
]
