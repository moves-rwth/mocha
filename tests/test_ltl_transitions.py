"""Check temporal transition restrictions, their intersections, and rendered explanations.

The worked example fixes the exact labelled relation. Nested formulas are also
checked directly against the NEXT and UNTIL transition equivalences.
"""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

from mocha import (
    compute_transition_relation, enumerate_elementary_sets,
    trace_transition_relation,
)
from mocha.io import parse_ltl
from mocha.logic.ltl import BooleanConstant, Next, Not, Proposition, Until


class LTLTransitionTests(unittest.TestCase):
    def test_manual_next_states_preserve_order_labels_and_trace(self):
        p = Proposition("p")
        formula = Next(p)
        states = [{p, formula}, {Not(p), formula},
                  {p, Not(formula)}, {Not(p), Not(formula)}]
        reported = []
        result = compute_transition_relation(formula, states, on_step=reported.append)
        expected = {(source, target) for source in (0, 1) for target in (0, 2)}
        expected |= {(source, target) for source in (2, 3) for target in (1, 3)}
        self.assertEqual(result.table.allowed_pairs, expected)
        self.assertEqual(result.table.states, tuple(map(frozenset, states)))
        self.assertEqual(result.table.source_labels,
                         (frozenset({"p"}), frozenset(), frozenset({"p"}), frozenset()))
        trace = trace_transition_relation(
            formula=formula, elementary_sets=(iter(state) for state in states),
        )
        self.assertEqual(trace.result, result)
        self.assertEqual(trace.steps, tuple(reported))
        self.assertEqual([step.source_index for step in trace.steps], list(range(4)))
        states[0].clear()
        self.assertEqual(result.table.states[0], {p, formula})

    def test_manual_until_subset_uses_only_supplied_targets(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        states = [{p, Not(q), formula}, {p, Not(q), Not(formula)},
                  {Not(p), Not(q), Not(formula)}, {Not(p), q, formula}]
        trace = trace_transition_relation(formula, states)
        self.assertEqual([step.targets for step in trace.steps],
                         [frozenset({0, 3}), frozenset({1, 2}),
                          frozenset(range(4)), frozenset(range(4))])
        self.assertEqual([step.restrictions[0].rule for step in trace.steps],
                         ["until_pending", "until_excluded", "until_inactive", "until_fulfilled"])
        self.assertEqual(trace.result.table.states, tuple(map(frozenset, states)))

    def test_temporal_rules_come_from_formula_even_when_absent_in_supplied_states(self):
        p = Proposition("p")
        formula = Next(p)
        state = {p, Not(formula)}
        trace = trace_transition_relation(formula, [state])
        self.assertFalse(trace.result.transitions)
        self.assertEqual(trace.steps[0].restrictions[0].rule, "next_excluded")
        self.assertEqual(trace.result.alphabet, {frozenset(), frozenset({"p"})})

    def test_generated_states_preserve_formula_order_and_trace(self):
        for source in ('X!"p"', '("p" U "q") U "p"', "X true", "X false", "false"):
            with self.subTest(source=source):
                enumeration = enumerate_elementary_sets(parse_ltl(source))
                result = compute_transition_relation(enumeration.formula, enumeration.elementary_sets)
                trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
                self.assertEqual(trace.result, result)
                self.assertEqual(result.formula, enumeration.formula)
                self.assertEqual(result.table.states, enumeration.elementary_sets)
                self.assertEqual(tuple(step.source for step in trace.steps), enumeration.elementary_sets)

    def test_manual_states_use_checker_equivalence_for_negations_and_constants(self):
        p = Proposition("p")
        formula = Next(p)
        result = compute_transition_relation(
            formula, [{Not(Not(p)), Next(Not(Not(p)))}],
        )
        self.assertEqual(result.table.states, (frozenset({p, formula}),))
        self.assertEqual(result.table.allowed_pairs, {(0, 0)})
        true = BooleanConstant(True)
        negated_false = Not(BooleanConstant(False))
        result = compute_transition_relation(
            Next(true), [{negated_false, Next(negated_false)}],
        )
        self.assertEqual(result.table.states, (frozenset({true, Next(true)}),))
        self.assertEqual(result.table.allowed_pairs, {(0, 0)})

    def test_invalid_manual_states_are_rejected_before_callbacks(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        reported = []
        with self.assertRaisesRegex(ValueError, "B2 is not an elementary set"):
            compute_transition_relation(formula, [{p, Not(q), formula}, {Not(p), Not(q), formula}],
                                        on_step=reported.append)
        self.assertEqual(reported, [])
        for state in (set(), {p, Not(p)}, {q}):
            with self.subTest(state=state):
                with self.assertRaisesRegex(ValueError, "B1 is not an elementary set"):
                    compute_transition_relation(p, [state])
        with self.assertRaisesRegex(TypeError, "candidate members must be LTLFormula"):
            compute_transition_relation(p, [{"p"}])
        with self.assertRaisesRegex(TypeError, "formula must be an LTLFormula"):
            compute_transition_relation("p", [{p}])
        with self.assertRaisesRegex(ValueError, "not normalized"):
            compute_transition_relation(parse_ltl('F"p"'), [])

    def test_manual_states_reject_duplicates_after_simplifying_spellings(self):
        p = Proposition("p")
        for duplicate in ({p}, {Not(Not(p))}):
            with self.subTest(duplicate=duplicate):
                with self.assertRaisesRegex(ValueError, "B2 duplicates elementary set B1"):
                    compute_transition_relation(p, [{p}, duplicate])

    def test_partial_collection_builds_transitions_without_enumerating(self):
        p = Proposition("p")
        reported = []
        with patch(
            "mocha.algorithms.ltl2gnba.elementary_set_enumeration.ElementaryTableRow",
            side_effect=AssertionError("Transition construction must not enumerate states"),
        ):
            result = compute_transition_relation(p, [{p}], on_step=reported.append)
            trace = trace_transition_relation(p, [{p}])
        self.assertEqual(result.table.allowed_pairs, {(0, 0)})
        self.assertEqual(result, trace.result)
        self.assertEqual(tuple(reported), trace.steps)

    def test_complete_collection_accepts_equivalent_spellings_and_preserves_order(self):
        p = Proposition("p")
        states = [{Not(p)}, {Not(Not(p))}]
        trace = trace_transition_relation(p, (iter(state) for state in states))
        self.assertEqual(trace.result.table.states, (frozenset({Not(p)}), frozenset({p})))
        self.assertEqual([step.source_index for step in trace.steps], [0, 1])
        self.assertEqual(trace.result.table.allowed_pairs, {(0, 0), (0, 1), (1, 0), (1, 1)})

    def test_subsets_still_reject_invalid_states_and_duplicates(self):
        p = Proposition("p")
        with self.assertRaisesRegex(ValueError, "not an elementary set"):
            compute_transition_relation(p, [{p, Not(p)}])
        with self.assertRaisesRegex(ValueError, "duplicates elementary set"):
            compute_transition_relation(p, [{p}, {p}])

    def test_empty_manual_collection(self):
        p = Proposition("p")
        trace = trace_transition_relation(p, [])
        self.assertEqual(trace.steps, ())
        self.assertEqual(trace.result.table.states, ())
        self.assertEqual(trace.result.transitions, frozenset())
        self.assertEqual(trace.result.alphabet, {frozenset(), frozenset({"p"})})

    def test_formula_and_collection_are_required_and_enumeration_shortcut_is_rejected(self):
        p = Proposition("p")
        enumeration = enumerate_elementary_sets(p)
        for compute in (compute_transition_relation, trace_transition_relation):
            with self.subTest(function=compute.__name__):
                with self.assertRaises(TypeError):
                    compute(p)
                with self.assertRaises(TypeError):
                    compute(enumeration)
                with self.assertRaisesRegex(TypeError, "formula must be an LTLFormula"):
                    compute(enumeration, enumeration.elementary_sets)

    def exercise(self):
        """Enumerate the worked UNTIL example used for exact matrix expectations."""
        return enumerate_elementary_sets(parse_ltl(
            '(!("a" & X"b") & !("a" & "b")) U (("a" & X"b") & !("a" & "b"))'
        ))

    def targets(self, table, source):
        """Return one-based target labels for a one-based source label.

        The transition table stores zero-based index pairs; converting both
        ends lets expectations use the exercise's displayed B1, B2, ... labels.
        """
        return {target + 1 for row, target in table.allowed_pairs if row == source - 1}

    def test_exact_exercise_transition_matrix_and_labels(self):
        enumeration = self.exercise()
        result = compute_transition_relation(enumeration.formula, enumeration.elementary_sets)
        expected = (
            {1, 3, 9}, {2, 4, 10, 11}, {5, 7, 12, 13}, {6, 8},
            {1, 3, 9}, {2, 4, 10, 11}, {5, 7, 12, 13}, {6, 8},
            {1, 3, 9}, {2, 4, 10, 11}, {5, 6, 7, 8, 12, 13},
            {1, 2, 3, 4, 9, 10, 11}, {5, 6, 7, 8, 12, 13},
        )
        self.assertEqual(tuple(self.targets(result.table, i) for i in range(1, 14)), expected)
        self.assertEqual(len(result.transitions), 52)
        self.assertEqual(result.table.states, enumeration.elementary_sets)
        labels = (frozenset(),) * 4 + (frozenset({"b"}),) * 4
        labels += (frozenset({"a"}),) * 3 + (frozenset({"a", "b"}),) * 2
        self.assertEqual(result.table.source_labels, labels)
        self.assertEqual(result.alphabet, frozenset(labels))
        expected_transitions = {
            (enumeration.elementary_sets[i - 1], labels[i - 1], enumeration.elementary_sets[j - 1])
            for i, targets in enumerate(expected, 1) for j in targets
        }
        self.assertEqual(result.transitions, expected_transitions)

    def test_source_derivations_match_exercise(self):
        enumeration = self.exercise()
        trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
        self.assertEqual(len(trace.steps), 13)

        def restriction(source, index):
            return trace.steps[source - 1].restrictions[index]

        def targets(source, index):
            return {i + 1 for i in restriction(source, index).allowed_targets}

        for source in (3, 4, 7, 8, 11, 13):
            self.assertEqual(targets(source, 0), {5, 6, 7, 8, 12, 13})
            self.assertEqual(restriction(source, 0).rule, "next_included")
        for source in (1, 2, 5, 6, 9, 10, 12):
            self.assertEqual(targets(source, 0), {1, 2, 3, 4, 9, 10, 11})
            self.assertEqual(restriction(source, 0).rule, "next_excluded")
        for source in (2, 4, 6, 8, 10):
            self.assertEqual(targets(source, 1), {2, 4, 6, 8, 10, 11})
            self.assertEqual(restriction(source, 1).rule, "until_pending")
        self.assertEqual(targets(11, 1), set(range(1, 14)))
        self.assertEqual(restriction(11, 1).rule, "until_fulfilled")
        self.assertIn("no restriction", restriction(11, 1).message)
        for source in (1, 3, 5, 7, 9):
            self.assertEqual(targets(source, 1), {1, 3, 5, 7, 9, 12, 13})
            self.assertEqual(restriction(source, 1).rule, "until_excluded")
        for source in (12, 13):
            self.assertEqual(targets(source, 1), set(range(1, 14)))
            self.assertEqual(restriction(source, 1).rule, "until_inactive")
            self.assertIn("no restriction", restriction(source, 1).message)

    def test_trace_intersections_removed_cells_and_callbacks(self):
        enumeration = self.exercise()
        trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
        reported = []
        self.assertEqual(compute_transition_relation(
            enumeration.formula, enumeration.elementary_sets, on_step=reported.append,
        ), trace.result)
        self.assertEqual(tuple(reported), trace.steps)
        for index, step in enumerate(trace.steps):
            self.assertEqual(step.iteration, index)
            self.assertEqual(step.source_index, index)
            self.assertEqual(step.source, enumeration.elementary_sets[index])
            self.assertEqual(step.input, trace.result.table.source_labels[index])
            self.assertEqual(len(step.restrictions), 2)
            previous = frozenset(range(13))
            for restriction in step.restrictions:
                self.assertTrue(restriction.message)
                self.assertEqual(restriction.remaining_targets, previous & restriction.allowed_targets)
                self.assertEqual(restriction.removed_targets, previous - restriction.allowed_targets)
                if restriction.required_formula is None:
                    self.assertIsNone(restriction.required_present)
                    self.assertEqual(restriction.allowed_targets, set(range(13)))
                else:
                    expected = {i for i, target in enumerate(enumeration.elementary_sets)
                                if (restriction.required_formula in target) == restriction.required_present}
                    self.assertEqual(restriction.allowed_targets, expected)
                previous = restriction.remaining_targets
            self.assertEqual(step.targets, previous)
            self.assertEqual({i + 1 for i in step.targets}, self.targets(trace.result.table, index + 1))
        with self.assertRaises(FrozenInstanceError):
            trace.steps[0].input = frozenset()
        with self.assertRaises(FrozenInstanceError):
            trace.steps[0].restrictions[0].rule = "changed"

    def test_nested_formulas_agree_with_transition_equivalences(self):
        for source in ('XX"p"', 'X!"p"', 'X("p" U "q")',
                       '("p" U "q") U ("q" U "p")',
                       '("p" U "q") & X("q" U "p")'):
            with self.subTest(source=source):
                enumeration = enumerate_elementary_sets(parse_ltl(source))
                result = compute_transition_relation(enumeration.formula, enumeration.elementary_sets)
                nexts = [node for node in enumeration.closure if isinstance(node, Next)]
                untils = [node for node in enumeration.closure if isinstance(node, Until)]
                for i, before in enumerate(enumeration.elementary_sets):
                    for j, after in enumerate(enumeration.elementary_sets):
                        permitted = all((node in before) == (node.operand in after) for node in nexts)
                        permitted &= all((node in before) == (node.right in before or
                                         (node.left in before and node in after)) for node in untils)
                        self.assertEqual((i, j) in result.table.allowed_pairs, permitted)
                for transition in result.transitions:
                    self.assertEqual(transition.symbol, frozenset(
                        node.name for node in transition.source if isinstance(node, Proposition)))

    def test_without_temporal_operators_all_pairs_are_allowed(self):
        for source in ('"p"', '"p" & !"p"', "true", "false"):
            with self.subTest(source=source):
                enumeration = enumerate_elementary_sets(parse_ltl(source))
                trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
                self.assertEqual(len(trace.result.transitions), len(enumeration.elementary_sets) ** 2)
                self.assertEqual(len(trace.steps), len(enumeration.elementary_sets))
                for step in trace.steps:
                    self.assertFalse(step.restrictions)
                    self.assertEqual(step.targets, set(range(len(enumeration.elementary_sets))))
        self.assertEqual(trace.result.alphabet, {frozenset()})

    def test_pending_until_cycles_remain_for_acceptance_stage(self):
        formula = parse_ltl('"p" U "q"')
        enumeration = enumerate_elementary_sets(formula)
        result = compute_transition_relation(formula, enumeration.elementary_sets)
        pending = next(i for i, state in enumerate(enumeration.elementary_sets)
                       if formula in state and parse_ltl('"q"') not in state)
        self.assertIn((pending, pending), result.table.allowed_pairs)

    def test_markdown_distinguishes_empty_valuation_from_no_transition(self):
        enumeration = self.exercise()
        result = compute_transition_relation(enumeration.formula, enumeration.elementary_sets)
        first_row = result.table.to_markdown().splitlines()[2].split("|")[1:-1]
        self.assertEqual([cell.strip() for cell in first_row],
                         ["B1", "∅", "", "∅", "", "", "", "", "", "∅", "", "", "", ""])
        self.assertNotIn("✓", result.table.to_markdown())
        unusual = enumerate_elementary_sets(parse_ltl('"a|b"'))
        self.assertIn('"a\\|b"', compute_transition_relation(
            unusual.formula, unusual.elementary_sets,
        ).table.to_markdown())

    def test_rendered_source_explanation_starts_with_input_then_restrictions(self):
        enumeration = self.exercise()
        trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
        step = trace.steps[1]
        text = step.to_markdown()
        self.assertIn("Transitions from B2", text)
        self.assertIn("Input: ∅", text)
        self.assertLess(text.index("Input:"), text.index("1."))
        self.assertIn("(◯b) is excluded from B2", text)
        self.assertIn("Remaining targets: {B2, B4, B10, B11}", text)
        self.assertIn("Result: B2 —∅→ {B2, B4, B10, B11}", text)
        self.assertIn("Input: {a}", trace.steps[10].to_markdown())

    def test_every_temporal_formula_is_explained_even_after_targets_become_empty(self):
        enumeration = enumerate_elementary_sets(parse_ltl('X false & X"p" & X!"p"'))
        trace = trace_transition_relation(enumeration.formula, enumeration.elementary_sets)
        temporal = {node for node in enumeration.closure if isinstance(node, Next)}
        for step in trace.steps:
            self.assertEqual({restriction.formula for restriction in step.restrictions}, temporal)
            self.assertEqual(len(step.restrictions), len(temporal))
        impossible = [step for step in trace.steps if not step.targets]
        self.assertTrue(impossible)
        self.assertTrue(any(not step.restrictions[0].remaining_targets for step in impossible))
        for step in impossible:
            self.assertIn("→ ∅", step.to_markdown())


if __name__ == "__main__":
    unittest.main()
