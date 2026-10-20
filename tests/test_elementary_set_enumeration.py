"""Check elementary-set completeness, deterministic table order, and trace ancestry.

Small closures are enumerated exhaustively against the independent validator;
the worked example also fixes row order, split history, and Markdown output.
"""

from dataclasses import FrozenInstanceError
from itertools import combinations
import unittest

from mocha.algorithms.ltl2gnba.elementary_set_enumeration import (
    enumerate_elementary_sets,
    trace_elementary_sets,
)
from mocha.algorithms.ltl2gnba.elementary_set_validation import check_elementary_set
from mocha.io import parse_ltl
from mocha.logic.ltl import And, Not, Until


class ElementaryTableTests(unittest.TestCase):
    def exercise(self):
        """Return the worked UNTIL formula and its four compound dependencies."""
        psi1 = parse_ltl('"a" & X "b"')
        psi2 = parse_ltl('"a" & "b"')
        psi3 = And(Not(psi1), Not(psi2))
        psi4 = And(psi1, Not(psi2))
        formula = Until(psi3, psi4)
        return formula, (psi1, psi2, psi3, psi4)

    def test_exercise_tables_and_final_order(self):
        formula, compounds = self.exercise()
        trace = trace_elementary_sets(formula)
        result = trace.result
        self.assertEqual(result.table.columns,
                         (*map(parse_ltl, ('"a"', '"b"', 'X "b"')), *compounds, formula))
        self.assertEqual([step.rule for step in trace.steps], [
            "simple_choices", "conjunction", "conjunction", "conjunction", "conjunction",
            "until_fulfilled", "until_pending", "until_choices", "complete",
        ])
        boolean_rows = (
            (0, 0, 0, 0, 0, 1, 0),
            (0, 0, 1, 0, 0, 1, 0),
            (0, 1, 0, 0, 0, 1, 0),
            (0, 1, 1, 0, 0, 1, 0),
            (1, 0, 0, 0, 0, 1, 0),
            (1, 0, 1, 1, 0, 0, 1),
            (1, 1, 0, 0, 1, 0, 0),
            (1, 1, 1, 1, 1, 0, 0),
        )
        self.assertEqual(tuple(row.values for row in trace.steps[4].table.rows),
                         tuple((*row, None) for row in boolean_rows))
        self.assertEqual(tuple(row.values[-1] for row in trace.steps[5].table.rows),
                         (None, None, None, None, None, True, None, None))
        self.assertEqual(tuple(row.values[-1] for row in trace.steps[6].table.rows),
                         (None, None, None, None, None, True, False, False))
        expected = tuple((*row, choice) for row in boolean_rows[:5] for choice in (0, 1))
        expected += ((*boolean_rows[5], 1), (*boolean_rows[6], 0), (*boolean_rows[7], 0))
        self.assertEqual(tuple(row.values for row in result.table.rows), expected)
        self.assertEqual(len(result.elementary_sets), 13)
        self.assertEqual([i for i, candidate in enumerate(result.elementary_sets, 1)
                          if formula in candidate], [2, 4, 6, 8, 10, 11])
        for row, candidate in zip(result.table.rows, result.elementary_sets):
            self.assertTrue(check_elementary_set(formula, candidate).is_elementary)
            for column, selected in zip(result.table.columns, row.values):
                self.assertEqual(column in candidate, selected)

    def test_exhaustive_checker_agreement_for_nested_and_boundary_cases(self):
        sources = ("true", "false", '"p"', '!"p"', '"p" & !"p"', "true U false",
                   '"p" U "q"', '!("p" U "q")', '("p" U "q") & "p"', '("p" U "q") U "p"',
                   '"p" U ("p" U "q")', '("p" U "q") & ("q" U "p")', 'X ("p" U "q")',
                   'X X "p"', 'X !"p"', '("p" U "p") & ("p" U "p")', 'false & X "p"')
        for source in sources:
            with self.subTest(source=source):
                formula = parse_ltl(source)
                result = enumerate_elementary_sets(formula)
                expected = {
                    frozenset(candidate)
                    for size in range(len(result.closure) + 1)
                    for candidate in combinations(result.closure, size)
                    if check_elementary_set(formula, candidate).is_elementary
                }
                self.assertEqual(set(result.elementary_sets), expected)
                self.assertEqual(len(result.elementary_sets), len(expected))
                self.assertTrue(result.table.is_complete)

    def test_next_and_operand_are_independent_simple_choices(self):
        trace = trace_elementary_sets(parse_ltl('X ("p" U "q")'))
        self.assertEqual(trace.steps[0].table.columns[:3], tuple(map(parse_ltl, ('"p"', '"q"', 'X ("p" U "q")'))))
        self.assertEqual(len(trace.steps[0].table.rows), 8)
        self.assertEqual(len(trace.result.elementary_sets), 10)

    def test_dependency_order_resumes_boolean_evaluation_after_until(self):
        trace = trace_elementary_sets(parse_ltl('("p" U "q") & "p"'))
        self.assertEqual([step.rule for step in trace.steps], [
            "simple_choices", "until_fulfilled", "until_pending", "until_choices",
            "conjunction", "complete",
        ])
        self.assertTrue(all(row.values[-1] is None for row in trace.steps[3].table.rows))

    def test_changes_and_parent_ids_explain_every_snapshot(self):
        trace = trace_elementary_sets(parse_ltl('("p" U "q") U ("q" U "p")'))
        previous = {}
        for iteration, step in enumerate(trace.steps):
            self.assertEqual(step.iteration, iteration)
            self.assertTrue(step.message)
            current = {row.id: row for row in step.table.rows}
            self.assertEqual(len(current), len(step.table.rows))
            changes = {(change.row_id, change.column): change for change in step.changes}
            for row in step.table.rows:
                before = previous.get(row.id)
                if before is None and previous:
                    self.assertIn(row.parent_id, previous)
                    before = previous[row.parent_id]
                old_values = before.values if before is not None else (None,) * len(row.values)
                for column, (old, new) in enumerate(zip(old_values, row.values)):
                    if old != new:
                        change = changes.pop((row.id, column))
                        self.assertEqual((change.before, change.after), (old, new))
            self.assertEqual(changes, {})
            previous = current

    def test_callback_matches_trace_and_snapshots_are_immutable(self):
        formula, _ = self.exercise()
        steps = []
        result = enumerate_elementary_sets(formula, on_step=steps.append)
        trace = trace_elementary_sets(formula)
        self.assertEqual(result, trace.result)
        self.assertEqual(tuple(steps), trace.steps)
        self.assertEqual(result.table, steps[-1].table)
        self.assertEqual(len(steps[0].table.rows), 8)
        with self.assertRaises(FrozenInstanceError):
            steps[0].table.rows[0].values = ()

    def test_markdown_renders_unknowns_final_names_and_aliases(self):
        trace = trace_elementary_sets(parse_ltl('"p" U "q"'))
        self.assertEqual(trace.steps[0].table.to_markdown(),
                         "| # | p | q | p U q |\n| --- | --- | --- | --- |\n"
                         "| 1 | 0 | 0 | x |\n| 2 | 0 | 1 | x |\n"
                         "| 3 | 1 | 0 | x |\n| 4 | 1 | 1 | x |")
        rendered = trace.result.table.to_markdown({parse_ltl('"p" U "q"'): "φ"})
        self.assertIn("| B | p | q | φ |", rendered)
        self.assertIn("| B5 | 1 | 1 | 1 |", rendered)
        self.assertIn("- φ = p U q", rendered)
        self.assertIn('"a\\|b"', enumerate_elementary_sets(parse_ltl('"a|b"')).table.to_markdown())

    def test_input_requires_explicit_normalization(self):
        for source in ('"p" | "q"', 'G "p"', '"p" W "q"', '"p" R "q"'):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "normalize_ltl"):
                    enumerate_elementary_sets(parse_ltl(source))


if __name__ == "__main__":
    unittest.main()
