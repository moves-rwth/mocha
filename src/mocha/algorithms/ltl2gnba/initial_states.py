"""Select GNBA initial states from a formula and supplied elementary sets.

An elementary set is initial exactly when it contains the normalized input
formula. Decisions cover every supplied state and preserve its position,
including states that are not selected or are unreachable in the final GNBA.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from mocha.logic.ltl import LTLFormula

from ..trace import AlgorithmTrace
from .elementary_set_validation import _validate_elementary_sets


@dataclass(frozen=True)
class InitialStateStep:
    """Explain whether one elementary set is an initial state.

    ``iteration`` and ``state_index`` both give the zero-based position of
    ``state`` in the supplied collection. Its display name is B followed by
    that index plus one. ``is_initial`` records membership of the normalized
    input formula in the state, and ``message`` explains the resulting decision.
    """

    iteration: int
    state_index: int
    state: frozenset[LTLFormula]
    is_initial: bool
    message: str


@dataclass(frozen=True)
class InitialStatesResult:
    """Initial states selected for the normalized ``formula``.

    ``initial_states`` contains the elementary sets that include the formula;
    ``state_indices`` identifies those same sets by zero-based positions in
    the supplied collection. Both collections can be empty, for example for
    the constant false formula.
    """

    formula: LTLFormula
    initial_states: frozenset[frozenset[LTLFormula]]
    state_indices: frozenset[int]


def compute_initial_states(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
    *,
    on_step: Callable[[InitialStateStep], None] | None = None,
) -> InitialStatesResult:
    """Select exactly the elementary sets containing the normalized formula.

    State indices are zero-based and retain supplied order as B1, B2, etc.
    Each state is validated and frozen before callbacks begin; duplicate states
    are rejected. No enumeration, completeness check, transition construction,
    or reachability filtering is performed. For the full GNBA, the caller must
    supply all elementary sets. Subsets and empty collections are accepted for
    partial analysis; completeness can be verified separately using
    ``check_elementary_set_collection``.

    Args:
        formula: Formula already normalized by ``normalize_ltl``. Membership of
            this formula determines which supplied elementary sets are initial.
        elementary_sets: Iterable of states containing formula objects, checked
            using ``check_elementary_set``. Double negations and negated constants
            are simplified as in the checker. Use a list or tuple for predictable
            state indices; input iterators are consumed once.
        on_step: Optional synchronous callback receiving one decision per
            elementary set, in supplied order, including excluded states.

    Returns:
        The normalized formula, selected states, and their original indices.

    Raises:
        TypeError: If the formula or a state member has the wrong type.
        ValueError: If the formula is not normalized, a state is not elementary,
            or states are duplicated after simplifying equivalent spellings.
    """
    _, states = _validate_elementary_sets(formula, elementary_sets)
    indices = set()
    for index, state in enumerate(states):
        selected = formula in state
        if selected:
            indices.add(index)
        if on_step is not None:
            membership = "contains" if selected else "does not contain"
            status = "initial" if selected else "not initial"
            on_step(InitialStateStep(
                index, index, state, selected,
                f"B{index + 1} {membership} ({formula}), so it is {status}.",
            ))
    return InitialStatesResult(formula,
                               frozenset(states[i] for i in indices),
                               frozenset(indices))


def trace_initial_states(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
) -> AlgorithmTrace[InitialStatesResult, InitialStateStep]:
    """Return the initial-state selection and retain every membership decision.

    Inputs and validation match ``compute_initial_states``. Steps follow the
    supplied order, with one decision per state, including noninitial states.
    Collection completeness is a separate check.
    """
    steps: list[InitialStateStep] = []
    result = compute_initial_states(formula, elementary_sets, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = ["InitialStateStep", "InitialStatesResult", "compute_initial_states", "trace_initial_states"]
