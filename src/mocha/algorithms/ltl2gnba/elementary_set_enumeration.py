"""Enumerate elementary sets for normalized LTL formulas using a choice table.

Each column represents a formula and its complement. A cell value of ``1``
means the elementary set includes the column formula; ``0`` means it includes
the complement instead. For a column ``p``, these choices select ``p`` and
``not p``, respectively. An ``x`` means the choice is unresolved. Internally,
these values are stored as ``True``, ``False``, and ``None``, respectively.

Rows start with all choices for atomic propositions and NEXT formulas; Boolean
and local UNTIL rules then resolve or split the remaining choices. Completed
rows represent elementary sets over the input formula's closure, including
sets that do not contain the input formula itself.

Enumeration can emit immutable snapshots with stable row IDs, split ancestry,
and cell changes so that callers can display or inspect each rule application.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from itertools import product

from mocha.logic.ltl import (
    And, BooleanConstant, LTLFormula, Next, Not, Proposition, Until, complement,
)

from ..trace import AlgorithmTrace
from .elementary_set_validation import check_elementary_set


@dataclass(frozen=True)
class ElementaryTableRow:
    """An immutable assignment of choices to a table's ordered columns.

    Attributes:
        id: Stable identifier within one enumeration, independent of the row's
            display position. Filling cells preserves this ID; splitting a row
            replaces it with two children that receive fresh IDs.
        values: One entry per table column. ``True`` selects the column formula,
            ``False`` selects its complement, and ``None`` leaves the choice
            unresolved. The tuple has the same order as ``ElementaryTable.columns``.
        parent_id: ID of the row from which this row was split, or ``None`` for
            an initial row. The parent can be found in earlier snapshots and
            need not be present in the current table.

    The frozen dataclass prevents field reassignment. Enumeration creates new
    row objects when filling cells, preserving previously emitted snapshots.
    """

    id: int
    values: tuple[bool | None, ...]
    parent_id: int | None = None


@dataclass(frozen=True)
class ElementaryTable:
    """An immutable snapshot of partial or completed elementary set choices.

    A Markdown cell ``1`` (``True``) selects its column formula, ``0``
    (``False``) selects the complement, and ``x`` (``None``) is unresolved.
    Once every cell is resolved, each row represents one elementary set.

    Attributes:
        columns: Ordered formula representatives, one per complement pair in
            the closure. A false cell selects the representative's complement.
        rows: Assignments in enumeration order, with one value per column.
            Splits replace a row in place with its false child, then its true
            child; their stable IDs retain the link to the original row.

    """

    columns: tuple[LTLFormula, ...]
    rows: tuple[ElementaryTableRow, ...]

    @property
    def is_complete(self) -> bool:
        """Whether every cell has chosen its column formula or its complement."""
        return all(value is not None for row in self.rows for value in row.values)

    def to_markdown(self, aliases: Mapping[LTLFormula, str] | None = None) -> str:
        """Render a table, optionally abbreviating columns with a formula legend.

        Completed rows are numbered B1, B2, ... in result order. Stable row IDs
        and split ancestry remain available on the row objects for trace UIs.

        Args:
            aliases: Optional formula-to-label mapping used for column headers.
                Aliased columns also receive a legend below the table. Other
                columns use their formula's string representation.

        Returns:
            A Markdown table where ``1`` selects the column formula, ``0``
            selects its complement, and ``x`` marks an unresolved choice.
            If any cell is unresolved, all rows use plain positional numbers
            instead of B labels. Backslashes and pipes are escaped, and
            newlines in headers and legend entries are replaced with spaces.
        """
        aliases = aliases or {}

        def escape(text: str) -> str:
            return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")

        headers = [escape(aliases.get(column, str(column))) for column in self.columns]
        lines = ["| " + " | ".join(["B" if self.is_complete else "#", *headers]) + " |",
                 "| " + " | ".join(["---"] * (len(headers) + 1)) + " |"]
        for index, row in enumerate(self.rows, 1):
            label = f"B{index}" if self.is_complete else str(index)
            cells = ["x" if value is None else str(int(value)) for value in row.values]
            lines.append("| " + " | ".join([label, *cells]) + " |")
        legend = [f"{escape(aliases[column])} = {escape(str(column))}"
                  for column in self.columns if column in aliases]
        if legend:
            lines.extend(["", *[f"- {entry}" for entry in legend]])
        return "\n".join(lines)


@dataclass(frozen=True)
class ElementaryTableChange:
    """A cell assignment made by one enumeration step.

    Attributes:
        row_id: Stable ID of the affected row in the step's new snapshot.
            For a split, this identifies a child rather than its parent.
        column: Zero-based index into the snapshot's columns.
        before: Previous choice, or ``None`` if unresolved. A split compares
            against the parent's values; initial choices compare against an
            entirely unresolved row.
        after: Resolved choice in the new snapshot.
    """

    row_id: int
    column: int
    before: bool | None
    after: bool


@dataclass(frozen=True)
class ElementaryTableStep:
    """One rule application and the immutable table snapshot it produces.

    Attributes:
        iteration: Zero-based step number within one enumeration.
        rule: Machine-readable rule name, such as ``simple_choices``,
            ``conjunction``, ``until_choices``, or ``complete``.
        message: Human-readable explanation of the rule application.
        table: Table after applying the rule, including any newly split rows.
        changes: Assignments made by this step. This can be empty when a rule
            has no effect or when the step announces completion.
        formula: Formula whose column is being processed, or ``None`` for the
            initial choices and completion steps.
    """

    iteration: int
    rule: str
    message: str
    table: ElementaryTable
    changes: tuple[ElementaryTableChange, ...]
    formula: LTLFormula | None = None


@dataclass(frozen=True)
class ElementarySetEnumeration:
    """The completed table and the elementary sets derived from its rows.

    Attributes:
        formula: Normalized input formula used to build the closure.
        closure: Input subformulas together with their complements.
        table: Final table, with every cell resolved.
        elementary_sets: Validated elementary sets in the same order as the
            table's rows. Each set selects exactly one member of every
            complement pair; it need not contain the input formula.
    """

    formula: LTLFormula
    closure: frozenset[LTLFormula]
    table: ElementaryTable
    elementary_sets: tuple[frozenset[LTLFormula], ...]


def _columns(formula: LTLFormula, closure: frozenset[LTLFormula]) -> tuple[LTLFormula, ...]:
    """Choose one representative per complement pair in evaluation order.

    Propositions come first, followed by NEXT formulas, each group sorted by
    string representation. A left-to-right traversal then adds conjunctions
    and UNTIL formulas after their dependencies, with ``true`` representing
    the constant pair when needed. Negations use their operand's column.
    NEXT choices remain independent of their operands, whose subformulas are
    still visited to include the rest of the closure.
    """
    # NEXT is an independent choice even when its operand is compound. Still
    # traverse that operand: its subformulas also belong to the closure.
    simple = sorted((node for node in closure if isinstance(node, Proposition)), key=str)
    simple += sorted((node for node in closure if isinstance(node, Next)), key=str)
    ordered: list[LTLFormula] = list(simple)
    visited: set[LTLFormula] = set()

    def visit(node: LTLFormula) -> None:
        if node in visited:
            return
        visited.add(node)
        if isinstance(node, (Not, Next)):
            visit(node.operand)
        elif isinstance(node, (And, Until)):
            visit(node.left)
            visit(node.right)
            ordered.append(node)
        elif isinstance(node, BooleanConstant) and BooleanConstant(True) not in ordered:
            ordered.append(BooleanConstant(True))

    visit(formula)
    return tuple(ordered)


def enumerate_elementary_sets(
    formula: LTLFormula, *, on_step: Callable[[ElementaryTableStep], None] | None = None,
) -> ElementarySetEnumeration:
    """Build elementary sets from atomic/NEXT choices, Boolean rules and UNTIL.

    Each column represents a formula and its complement. A cell displayed as
    ``1`` selects the column formula for the elementary set; ``0`` excludes it
    and selects its complement instead. For example, in a column for ``p``,
    ``1`` selects ``p`` and ``0`` selects ``not p``. An ``x`` marks an unresolved
    choice. These cell values are stored as ``True``, ``False``, and ``None``,
    respectively.

    Simple columns are ordered by name (atomics first, then NEXT), with 0 before
    1. Compound columns follow dependency order, using left-to-right traversal
    to break ties. Each UNTIL is processed with two separate local rules, then
    remaining choices split into two child rows: one selecting the complement
    (0), then one selecting the UNTIL formula (1). Boolean evaluation resumes
    as needed for nested formulas. No restriction to sets containing the input
    is made.

    For an UNTIL formula, a selected right operand forces inclusion, while
    excluding both operands forces exclusion. If only the left operand is
    selected, both choices are locally consistent and the row splits.
    NEXT formulas have no local constraint tying them to their operands.

    Args:
        formula: Formula already normalized by ``normalize_ltl`` to AND, NOT,
            NEXT, UNTIL, propositions, and constants, without double negations
            or negated constants. No automatic normalization is performed.
        on_step: Optional synchronous callback receiving each rule application
            as an ``ElementaryTableStep``, including initial choices and final
            completion. Steps include immutable snapshots and changed cells,
            even when a rule changes no cells. Snapshots can be retained safely.

    Returns:
        The input formula, its closure, the completed table, and all elementary
        sets in row order. Each set is independently validated by
        ``check_elementary_set`` before the completion step is emitted.

    Raises:
        TypeError: If ``formula`` is not an ``LTLFormula``.
        ValueError: If ``formula`` is not in the required normal form.
        RuntimeError: If a dependency remains unresolved or a completed row
            fails elementary-set validation, indicating an internal error.
    """
    closure = check_elementary_set(formula, ()).closure
    columns = _columns(formula, closure)
    indices = {column: index for index, column in enumerate(columns)}
    simple_count = sum(isinstance(column, (Proposition, Next)) for column in columns)
    rows = [ElementaryTableRow(index, (*values, *((None,) * (len(columns) - simple_count))))
            for index, values in enumerate(product((False, True), repeat=simple_count), 1)]
    next_id = len(rows) + 1
    iteration = 0

    def emit(rule: str, message: str, changes: list[ElementaryTableChange],
             node: LTLFormula | None = None) -> None:
        nonlocal iteration
        if on_step is not None:
            on_step(ElementaryTableStep(iteration, rule, message,
                                       ElementaryTable(columns, tuple(rows)), tuple(changes), node))
        iteration += 1

    def value(node: LTLFormula, row: ElementaryTableRow) -> bool:
        if isinstance(node, Not):
            return not value(node.operand, row)
        if isinstance(node, BooleanConstant):
            return node.value
        result = row.values[indices[node]]
        if result is None:
            raise RuntimeError(f"Unresolved dependency: {node}")
        return result

    def fill(index: int, decide: Callable[[ElementaryTableRow], bool | None]) -> list[ElementaryTableChange]:
        changes = []
        for position, row in enumerate(rows):
            selected = decide(row)
            if selected is not None and selected != row.values[index]:
                changes.append(ElementaryTableChange(row.id, index, row.values[index], selected))
                values = list(row.values)
                values[index] = selected
                rows[position] = ElementaryTableRow(row.id, tuple(values), row.parent_id)
        return changes

    emit("simple_choices", "Choose each atomic proposition and NEXT formula or its negation.",
         [ElementaryTableChange(row.id, index, None, row.values[index])
          for row in rows for index in range(simple_count)])

    for index, node in enumerate(columns[simple_count:], simple_count):
        if isinstance(node, BooleanConstant):
            emit("constant", "true must be included; false must be excluded.",
                 fill(index, lambda row: True), node)
        elif isinstance(node, And):
            emit("conjunction", f"Include {node} exactly when both operands are included.",
                 fill(index, lambda row: value(node.left, row) and value(node.right, row)), node)
        elif isinstance(node, Until):
            emit("until_fulfilled", f"If {node.right} is included, include {node}.",
                 fill(index, lambda row: True if value(node.right, row) else None), node)
            emit("until_pending", f"If neither ({node.left}) nor ({node.right}) is included, "
                 f"exclude {node}: a pending UNTIL requires its left operand.",
                 fill(index, lambda row: False if not value(node.right, row)
                      and not value(node.left, row) else None), node)
            expanded = []
            changes = []
            for row in rows:
                if row.values[index] is not None:
                    expanded.append(row)
                    continue
                for selected in (False, True):
                    values = list(row.values)
                    values[index] = selected
                    expanded.append(ElementaryTableRow(next_id, tuple(values), row.id))
                    changes.append(ElementaryTableChange(next_id, index, None, selected))
                    next_id += 1
            rows = expanded
            emit("until_choices", f"Where ({node.left}) is included and ({node.right}) is excluded, "
                 f"both choices for {node} are locally consistent; split each such row.", changes, node)

    table = ElementaryTable(columns, tuple(rows))
    sets = tuple(frozenset(column if selected else complement(column)
                           for column, selected in zip(columns, row.values)) for row in rows)
    for candidate in sets:
        if not check_elementary_set(formula, candidate).is_elementary:
            raise RuntimeError("Enumeration produced a non-elementary set")
    emit("complete", "Every completed row passes the elementary-set checker.", [])
    return ElementarySetEnumeration(formula, closure, table, sets)


def trace_elementary_sets(formula: LTLFormula) -> AlgorithmTrace[ElementarySetEnumeration, ElementaryTableStep]:
    """Enumerate elementary sets and retain every step in an ``AlgorithmTrace``.

    ``formula`` has the same normalization requirements as
    ``enumerate_elementary_sets``. The trace's ``result`` contains the completed
    enumeration, and its ``steps`` tuple contains the callback snapshots in
    order, from initial choices through completion. All snapshots are retained
    in memory, including those for rules that change no cells.
    """
    steps: list[ElementaryTableStep] = []
    result = enumerate_elementary_sets(formula, on_step=steps.append)
    return AlgorithmTrace(result, tuple(steps))


__all__ = [
    "ElementarySetEnumeration", "ElementaryTable", "ElementaryTableRow",
    "ElementaryTableChange", "ElementaryTableStep", "enumerate_elementary_sets",
    "trace_elementary_sets",
]
