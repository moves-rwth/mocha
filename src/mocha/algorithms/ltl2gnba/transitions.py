"""Derive GNBA edges by propagating NEXT and UNTIL choices between states.

Supply a normalized formula and a collection of elementary sets. The collection
is checked for valid members and duplicates. Completeness is a precondition for
full GNBA construction and can be verified separately.
Temporal rules restrict possible targets for each source; every surviving edge
is labelled with the atomic propositions present in that source. UNTIL
acceptance is handled separately, so locally consistent pending obligations
can form cycles.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import product

from mocha.logic.ltl import LTLFormula, Next, Proposition, Until, propositions
from mocha.models.automaton import AutomatonTransition

from ..trace import AlgorithmTrace
from .elementary_set_validation import _validate_elementary_sets

ElementarySet = frozenset[LTLFormula]
Valuation = frozenset[str]
StatePair = tuple[int, int]


@dataclass(frozen=True)
class TransitionRelationTable:
    """Source rows and target columns retain the supplied elementary-set order.

    ``allowed_pairs`` uses zero-based indices into ``states``. Intermediate
    tables show ticks; labelled tables show source valuations. A blank cell
    means no transition, whereas ∅ means a transition on the empty valuation.

    Attributes:
        states: Elementary sets in their supplied order.
        allowed_pairs: Permitted (source, target) index pairs into ``states``.
        source_labels: Valuations aligned with ``states``, each containing the
            names of atomic propositions present in the corresponding source.
        labelled: Whether rendering uses source valuations instead of ticks.
    """

    states: tuple[ElementarySet, ...]
    allowed_pairs: frozenset[StatePair]
    source_labels: tuple[Valuation, ...]
    labelled: bool = False

    def to_markdown(self) -> str:
        """Render the transition matrix with B1, B2, ... row and column labels.

        Allowed cells contain a tick or source valuation according to
        ``labelled``. Forbidden cells remain blank. Proposition names in
        valuations are sorted and escaped for Markdown table cells.
        """
        headers = [f"B{index + 1}" for index in range(len(self.states))]
        lines = ["| source / target | " + " | ".join(headers) + " |",
                 "| " + " | ".join(["---"] * (len(headers) + 1)) + " |"]
        for source, label in enumerate(self.source_labels):
            if self.labelled:
                names = [str(Proposition(name)).replace("\\", "\\\\")
                         .replace("|", "\\|").replace("\n", " ") for name in sorted(label)]
                cell = "{" + ", ".join(names) + "}" if names else "∅"
            else:
                cell = "✓"
            cells = [cell if (source, target) in self.allowed_pairs else ""
                     for target in range(len(self.states))]
            lines.append("| " + " | ".join([headers[source], *cells]) + " |")
        return "\n".join(lines)


@dataclass(frozen=True)
class TransitionRestriction:
    """One temporal formula's restriction for a fixed source elementary set.

    Target indices are zero-based. ``allowed_targets`` considers this formula
    alone; ``remaining_targets`` intersects it with all preceding restrictions.
    A missing ``required_formula`` means this formula imposes no restriction.

    Attributes:
        formula: NEXT or UNTIL formula being considered in the source.
        rule: Machine-readable case name, such as ``next_included`` or
            ``until_pending``.
        message: Explanation specialized to the source's formula memberships.
        required_formula: Formula whose membership is constrained in the target,
            or ``None`` if every target satisfies this rule.
        required_present: Required membership of that formula; ``None`` when
            no target constraint is imposed.
        allowed_targets: Targets satisfying this formula alone.
        remaining_targets: Targets surviving this and all earlier restrictions.
        removed_targets: Previously surviving targets eliminated by this rule.
    """

    formula: LTLFormula
    rule: str
    message: str
    required_formula: LTLFormula | None
    required_present: bool | None
    allowed_targets: frozenset[int]
    remaining_targets: frozenset[int]
    removed_targets: frozenset[int]


def _target_names(targets: frozenset[int]) -> str:
    """Format zero-based target indices as ordered B labels, or ∅ if empty."""
    return "{" + ", ".join(f"B{index + 1}" for index in sorted(targets)) + "}" if targets else "∅"


def _valuation_text(valuation: Valuation) -> str:
    """Format a valuation using sorted proposition names, or ∅ if empty."""
    return "{" + ", ".join(str(Proposition(name)) for name in sorted(valuation)) + "}" if valuation else "∅"


@dataclass(frozen=True)
class TransitionRelationStep:
    """A complete derivation of outgoing transitions for one elementary set.

    ``input`` is the valuation labelling every outgoing transition.
    ``restrictions`` visits each NEXT and UNTIL formula once, specializing its
    rule to this source. ``targets`` is the final intersection. Source and
    target indices refer to the supplied state order and are zero-based.

    ``iteration`` equals ``source_index`` because each source produces exactly
    one step. ``source`` retains the elementary set itself. Restrictions list
    NEXT formulas first, then UNTIL formulas, with each group sorted by string
    representation, including rules considered after no targets remain.
    """

    iteration: int
    source_index: int
    source: ElementarySet
    input: Valuation
    restrictions: tuple[TransitionRestriction, ...]
    targets: frozenset[int]

    def to_markdown(self) -> str:
        """Explain the input and successive target restrictions for this source."""
        name = f"B{self.source_index + 1}"
        label = _valuation_text(self.input)
        lines = [f"### Transitions from {name}", "",
                 f"Input: {label} (the atomic propositions in {name}).", "",
                 "Start with all elementary sets as possible targets.", ""]
        for index, restriction in enumerate(self.restrictions, 1):
            lines.extend([
                f"{index}. {restriction.message}",
                f"   Targets allowed by this formula: {_target_names(restriction.allowed_targets)}.",
                f"   Remaining targets: {_target_names(restriction.remaining_targets)}.", "",
            ])
        if not self.restrictions:
            lines.extend(["There are no NEXT or UNTIL formulas, so every target is allowed.", ""])
        lines.append(f"Result: {name} —{label}→ {_target_names(self.targets)}.")
        return "\n".join(lines)


@dataclass(frozen=True)
class TransitionRelationResult:
    """The labelled edges and full alphabet for ``formula`` and supplied states.

    ``table`` retains the supplied state order and the permitted source/target
    pairs, with valuation rendering enabled. ``transitions`` gives the same
    relation as automaton edges labelled by source valuations. ``alphabet`` is
    the powerset of all proposition names in the formula, including valuations
    that label no surviving edge. Initial and accepting states are determined
    by separate construction stages.
    """

    formula: LTLFormula
    table: TransitionRelationTable
    alphabet: frozenset[Valuation]
    transitions: frozenset[AutomatonTransition[ElementarySet, Valuation]]


def compute_transition_relation(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
    *,
    on_step: Callable[[TransitionRelationStep], None] | None = None,
) -> TransitionRelationResult:
    """Derive outgoing transitions one elementary set at a time.

    Call ``compute_transition_relation(formula, elementary_sets)`` with the
    normalized formula and ordered states. Each state is validated, but no
    enumeration, completeness check, or initial-state selection is performed.
    To verify completeness explicitly, call
    ``validate_elementary_set_collection`` separately.

    Supplied order determines B1, B2, ... labels and zero-based state indices;
    use a list or tuple when that order matters. For each source, determine the
    input valuation (the set of proposition names true in that source), then
    specialize every NEXT and UNTIL rule to its formula memberships. Record
    each rule's target restriction, including unrestricted cases, and the
    remaining targets after applying it. The alphabet is 2^AP: all subsets of
    the proposition names AP occurring in the formula.

    For example, the complete manually supplied collection for ``X p`` is::

        from mocha.logic.ltl import Next, Not, Proposition

        p = Proposition("p")
        formula = Next(p)
        states = [{p, formula}, {p, Not(formula)},
                  {Not(p), formula}, {Not(p), Not(formula)}]
        result = compute_transition_relation(formula, states)

    Sources containing ``X p`` allow exactly the targets containing ``p``;
    sources containing its negation allow exactly the targets excluding ``p``.

    For a source B and target B', the restrictions enforce both equivalences:
    ``X ψ ∈ B`` iff ``ψ ∈ B'``, and ``ψ U χ ∈ B`` iff ``χ ∈ B`` or
    (``ψ ∈ B`` and ``ψ U χ ∈ B'``). All source/target pairs are considered,
    including self-loops and states unreachable from the eventual initial set.

    This constructs only the transition relation; UNTIL acceptance sets are
    a separate stage. In particular, a pending UNTIL may continue on a cycle.

    Args:
        formula: Formula already normalized by ``normalize_ltl``. Its closure
            supplies all temporal rules, even when their positive formulas are
            absent from every supplied state.
        elementary_sets: Iterable of elementary sets containing formula objects,
            each validated by ``check_elementary_set`` and stored as a frozenset.
            Double negations and negated constants are simplified as in the
            checker. Distinct states retain input order. A full GNBA requires
            all elementary sets over the formula's closure; the caller supplies
            that guarantee. A subset, including an empty collection, is also
            accepted for partial analysis: only edges between supplied states
            are built, which need not recognize the formula's full language.
        on_step: Optional synchronous callback receiving one derivation per
            source in supplied order, including sources with no targets. All
            supplied states are validated before the first callback.

    Returns:
        The normalized formula, labelled transition table, full valuation
        alphabet, and permitted automaton edges.

    Raises:
        TypeError: If the formula or a candidate member has the wrong type.
        ValueError: If the formula is not normalized, a supplied set fails the
            elementary-set conditions, or two supplied states are identical
            after simplifying equivalent spellings.
    """
    closure, states = _validate_elementary_sets(formula, elementary_sets)
    labels = tuple(frozenset(node.name for node in state if isinstance(node, Proposition))
                   for state in states)
    all_targets = frozenset(range(len(states)))
    allowed: set[StatePair] = set()
    nexts = sorted((node for node in closure if isinstance(node, Next)), key=str)
    untils = sorted((node for node in closure if isinstance(node, Until)), key=str)
    for source_index, source in enumerate(states):
        name = f"B{source_index + 1}"
        remaining = all_targets
        restrictions = []
        for node in (*nexts, *untils):
            required: LTLFormula | None = None
            present: bool | None = None
            if isinstance(node, Next):
                required, present = node.operand, node in source
                rule = "next_included" if present else "next_excluded"
                membership = "included in" if present else "excluded from"
                message = (f"({node}) is {membership} {name}, so ({node.operand}) "
                           f"must be {membership} the target set.")
            elif node.right in source:
                rule = "until_fulfilled"
                message = (f"({node}) and its right operand ({node.right}) are included in {name}. "
                           "The UNTIL obligation is already fulfilled, so it imposes no restriction on the target.")
            elif node in source:
                rule = "until_pending"
                required, present = node, True
                message = (f"({node}) is included in {name}, but ({node.right}) is excluded. "
                           f"Its left operand ({node.left}) holds, so the obligation must continue: "
                           f"include ({node}) in the target set.")
            elif node.left in source:
                rule = "until_excluded"
                required, present = node, False
                message = (f"({node}) is excluded from {name}, while ({node.left}) is included "
                           f"and ({node.right}) is excluded. To keep UNTIL false, "
                           f"exclude ({node}) from the target set.")
            else:
                rule = "until_inactive"
                message = (f"({node}) and both operands are excluded from {name}. "
                           "UNTIL is false regardless of the target, so it imposes no restriction.")
            permitted = all_targets if required is None else frozenset(
                index for index, target in enumerate(states) if (required in target) == present
            )
            removed = remaining - permitted
            remaining = remaining & permitted
            restrictions.append(TransitionRestriction(
                node, rule, message, required, present, permitted, remaining, removed,
            ))
        allowed.update((source_index, target) for target in remaining)
        if on_step is not None:
            on_step(TransitionRelationStep(source_index, source_index, source, labels[source_index],
                                           tuple(restrictions), remaining))

    transitions = frozenset(AutomatonTransition(states[i], labels[i], states[j]) for i, j in allowed)
    names = sorted(propositions(formula))
    alphabet = frozenset(frozenset(name for name, selected in zip(names, bits) if selected)
                         for bits in product((False, True), repeat=len(names)))
    return TransitionRelationResult(formula,
                                    TransitionRelationTable(states, frozenset(allowed), labels, True),
                                    alphabet, transitions)


def trace_transition_relation(
    formula: LTLFormula,
    elementary_sets: Iterable[Iterable[LTLFormula]],
) -> AlgorithmTrace[TransitionRelationResult, TransitionRelationStep]:
    """Record the input and ordered formula restrictions for each source set.

    Accepts ``(formula, elementary_sets)`` with the same validation and ordering
    rules as ``compute_transition_relation``.
    Individual states and duplicates are checked; collection completeness is
    a separate operation, ``validate_elementary_set_collection``.
    The trace's ``result`` is the computed relation; ``steps`` retains one
    immutable derivation per supplied source in input order, including removed
    targets and unrestricted formulas.
    """
    steps: list[TransitionRelationStep] = []
    result = compute_transition_relation(formula, elementary_sets, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = [
    "TransitionRestriction",
    "TransitionRelationTable", "TransitionRelationStep", "TransitionRelationResult",
    "compute_transition_relation", "trace_transition_relation",
]
