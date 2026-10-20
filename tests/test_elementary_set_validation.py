"""Check individual elementary sets and feedback on full computed collections.

Collection checks retain per-state violations, report duplicates and omissions,
and return canonical ordered states through the raising validator.
"""

from dataclasses import FrozenInstanceError
from itertools import combinations
import unittest

from mocha import (
    ElementarySetCollectionResult, check_elementary_set_collection,
    compute_transition_relation, enumerate_elementary_sets, normalize_ltl,
    validate_elementary_set_collection,
)
from mocha.algorithms.ltl2gnba.elementary_set_validation import check_elementary_set
from mocha.io import parse_ltl
from mocha.logic.ltl import BooleanConstant, Next, Not, Proposition, Until


def formulas(*sources):
    return frozenset(parse_ltl(source) for source in sources)


class ElementarySetTests(unittest.TestCase):
    def check(self, source, *candidate):
        return check_elementary_set(parse_ltl(source), formulas(*candidate))

    def test_until_feedback_identifies_missing_left_operand(self):
        result = self.check('"p" U "q"', '!"p"', '!"q"', '"p" U "q"')
        self.assertFalse(result.is_elementary)
        self.assertEqual(len(result.violations), 1)
        violation = result.violations[0]
        self.assertEqual(violation.condition, "local_consistency")
        self.assertEqual(violation.rule, "until_pending")
        self.assertEqual(violation.formulas, tuple(map(parse_ltl, ('"p" U "q"', '"p"', '"q"'))))
        self.assertIn("p must be included", violation.message)

    def test_all_subsets_match_the_five_until_elementary_sets(self):
        formula = parse_ltl('"p" U "q"')
        expected = {
            formulas('!"p"', '!"q"', '!("p" U "q")'),
            formulas('!"p"', '"q"', '"p" U "q"'),
            formulas('"p"', '!"q"', '!("p" U "q")'),
            formulas('"p"', '!"q"', '"p" U "q"'),
            formulas('"p"', '"q"', '"p" U "q"'),
        }
        closure = check_elementary_set(formula, ()).closure
        self.assertEqual(closure, formulas('"p"', '!"p"', '"q"', '!"q"', '"p" U "q"', '!("p" U "q")'))
        actual = {
            frozenset(candidate)
            for size in range(len(closure) + 1)
            for candidate in combinations(closure, size)
            if check_elementary_set(formula, candidate).is_elementary
        }
        self.assertEqual(actual, expected)

    def test_book_example_has_exactly_six_elementary_sets(self):
        formula = parse_ltl('"a" U (!"a" & "b")')
        expected = {
            formulas('"a"', '"b"', '!(!"a" & "b")', '"a" U (!"a" & "b")'),
            formulas('"a"', '"b"', '!(!"a" & "b")', '!("a" U (!"a" & "b"))'),
            formulas('"a"', '!"b"', '!(!"a" & "b")', '"a" U (!"a" & "b")'),
            formulas('"a"', '!"b"', '!(!"a" & "b")', '!("a" U (!"a" & "b"))'),
            formulas('!"a"', '!"b"', '!(!"a" & "b")', '!("a" U (!"a" & "b"))'),
            formulas('!"a"', '"b"', '!"a" & "b"', '"a" U (!"a" & "b")'),
        }
        closure = check_elementary_set(formula, ()).closure
        self.assertEqual(len(closure), 8)
        actual = {
            frozenset(candidate)
            for size in range(len(closure) + 1)
            for candidate in combinations(closure, size)
            if check_elementary_set(formula, candidate).is_elementary
        }
        self.assertEqual(actual, expected)

    def test_conjunction_both_directions(self):
        for candidate in (('"p"', '!"q"', '"p" & "q"'), ('"p"', '"q"', '!("p" & "q")')):
            with self.subTest(candidate=candidate):
                result = self.check('"p" & "q"', *candidate)
                self.assertEqual([v.rule for v in result.violations], ["conjunction"])

    def test_fulfilled_until_must_be_present(self):
        result = self.check('"p" U "q"', '!"p"', '"q"', '!("p" U "q")')
        self.assertEqual([v.rule for v in result.violations], ["until_fulfilled"])

    def test_all_failures_are_reported_once_and_deterministically(self):
        candidate = list(formulas('"p"', '!"p"', '"r"'))
        result = check_elementary_set(parse_ltl('"p" & "q"'), candidate)
        self.assertEqual(result, check_elementary_set(parse_ltl('"p" & "q"'), reversed(candidate)))
        self.assertCountEqual([v.rule for v in result.violations],
                              ["outside_closure", "contradiction", "missing_choice", "missing_choice"])
        self.assertEqual(result.violations[0].formulas, (parse_ltl('"r"'),))

    def test_constants(self):
        for source in ("true", "false"):
            with self.subTest(source=source):
                self.assertTrue(self.check(source, "true").is_elementary)
                self.assertEqual(self.check(source, "true").closure, formulas("true", "false"))
                self.assertEqual([v.rule for v in self.check(source, "false").violations], ["true_required"])
                self.assertFalse(self.check(source, "true", "false").is_elementary)

    def test_next_has_no_local_restriction_and_formula_need_not_be_included(self):
        for candidate in (('"p"', 'X "p"'), ('!"p"', 'X "p"'),
                          ('"p"', '!X "p"'), ('!"p"', '!X "p"')):
            with self.subTest(candidate=candidate):
                self.assertTrue(self.check('X "p"', *candidate).is_elementary)

    def test_closure_traverses_children_of_negated_compound(self):
        result = self.check('!("p" & X "q")')
        self.assertEqual(result.closure, formulas(
            '"p"', '!"p"', '"q"', '!"q"', 'X "q"', '!X "q"', '"p" & X "q"', '!("p" & X "q")'))

    def test_candidate_negation_representatives_preserve_submission(self):
        result = self.check('"p" & X "q"', '!!"p"', '"q"', 'X !!"q"', '!!("p" & X "q")')
        self.assertTrue(result.is_elementary)
        self.assertIn(parse_ltl('!!"p"'), result.candidate)
        self.assertTrue(self.check("true", "!false").is_elementary)
        self.assertTrue(self.check("false", "!false").is_elementary)

    def test_derived_candidate_operator_is_not_silently_expanded(self):
        result = self.check('true U "p"', "true", '"p"', 'F "p"')
        self.assertFalse(result.is_elementary)
        self.assertIn("outside_closure", [v.rule for v in result.violations])

    def test_formula_must_already_be_normalized(self):
        for source in ('"p" | "q"', 'F "p"', 'G "p"', '"p" W "q"', '"p" R "q"', '!!"p"', "!true"):
            with self.subTest(source=source):
                with self.assertRaisesRegex(ValueError, "normalize_ltl"):
                    self.check(source)
                check_elementary_set(normalize_ltl(parse_ltl(source)), ())

    def test_type_errors_and_immutable_snapshot(self):
        with self.assertRaises(TypeError):
            check_elementary_set("p", ())
        with self.assertRaises(TypeError):
            check_elementary_set(parse_ltl('"p"'), ["p"])
        candidate = [parse_ltl('"p"')]
        result = check_elementary_set(parse_ltl('"p"'), iter(candidate))
        candidate.clear()
        self.assertEqual(result.candidate, formulas('"p"'))
        with self.assertRaises(FrozenInstanceError):
            result.candidate = frozenset()


class ElementarySetCollectionTests(unittest.TestCase):
    def test_reports_invalid_duplicates_and_missing_states_together(self):
        p, q = Proposition("p"), Proposition("q")
        states = [{p}, {Not(Not(p))}, {p, Not(p)}, {q}, set()]
        result = check_elementary_set_collection(p, states)
        self.assertIsInstance(result, ElementarySetCollectionResult)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.is_complete)
        self.assertEqual([state.is_elementary for state in result.state_results],
                         [True, True, False, False, False])
        self.assertEqual(result.duplicate_indices, ((0, 1),))
        self.assertEqual(result.missing_sets, (frozenset({Not(p)}),))
        self.assertEqual(result.state_results[1].candidate, {Not(Not(p))})
        self.assertIn("contradiction", {v.rule for v in result.state_results[2].violations})
        self.assertIn("outside_closure", {v.rule for v in result.state_results[3].violations})
        self.assertIn("missing_choice", {v.rule for v in result.state_results[4].violations})

    def test_coverage_does_not_hide_invalid_or_duplicate_entries(self):
        p = Proposition("p")
        result = check_elementary_set_collection(p, [{p}, {Not(p)}, {p}, {p, Not(p)}])
        self.assertTrue(result.is_complete)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.missing_sets, ())
        self.assertEqual(result.duplicate_indices, ((0, 2),))
        self.assertFalse(result.state_results[-1].is_elementary)

    def test_complete_collection_preserves_order_and_equivalent_spellings(self):
        p = Proposition("p")
        states = [{Not(p)}, {Not(Not(p))}]
        checked = check_elementary_set_collection(p, (iter(state) for state in states))
        self.assertTrue(checked.is_valid)
        self.assertTrue(checked.is_complete)
        self.assertEqual([state.candidate for state in checked.state_results], states)
        validated = validate_elementary_set_collection(p, (iter(state) for state in states))
        self.assertEqual(validated, (frozenset({Not(p)}), frozenset({p})))
        result = compute_transition_relation(p, validated)
        self.assertEqual(result.table.states, validated)

    def test_empty_collection_reports_all_required_states(self):
        p = Proposition("p")
        result = check_elementary_set_collection(p, [])
        self.assertFalse(result.is_valid)
        self.assertEqual(result.state_results, ())
        self.assertEqual(set(result.missing_sets), {frozenset({p}), frozenset({Not(p)})})
        with self.assertRaisesRegex(ValueError, "missing 2 elementary sets"):
            validate_elementary_set_collection(p, [])

    def test_false_formula_still_requires_its_noninitial_elementary_state(self):
        false, true = BooleanConstant(False), BooleanConstant(True)
        result = check_elementary_set_collection(false, [])
        self.assertEqual(result.missing_sets, (frozenset({true}),))
        self.assertTrue(check_elementary_set_collection(false, [{true}]).is_valid)

    def test_completeness_requires_states_excluding_the_input_formula(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        initial_states = [{p, q, formula}, {Not(p), q, formula}, {p, Not(q), formula}]
        result = check_elementary_set_collection(formula, initial_states)
        self.assertTrue(all(state.is_elementary for state in result.state_results))
        self.assertEqual(set(result.missing_sets),
                         {frozenset({p, Not(q), Not(formula)}),
                          frozenset({Not(p), Not(q), Not(formula)})})
        self.assertTrue(check_elementary_set_collection(
            formula, [*initial_states, *result.missing_sets],
        ).is_valid)

    def test_raising_validator_includes_all_feedback(self):
        p = Proposition("p")
        with self.assertRaises(ValueError) as caught:
            validate_elementary_set_collection(p, [{p}, {p}, {p, Not(p)}])
        message = str(caught.exception)
        self.assertIn("B3 is not an elementary set", message)
        self.assertIn("B2 duplicates elementary set B1", message)
        self.assertIn("missing 1 elementary set (", message)
        self.assertIn("¬p", message)

    def test_generated_collections_are_valid_for_nested_and_constant_formulas(self):
        for source in ('X!"p"', '("p" U "q") U "p"', "X true", "X false", "false"):
            with self.subTest(source=source):
                formula = parse_ltl(source)
                states = enumerate_elementary_sets(formula).elementary_sets
                self.assertTrue(check_elementary_set_collection(formula, states).is_valid)
        true = BooleanConstant(True)
        alias = Not(BooleanConstant(False))
        self.assertEqual(validate_elementary_set_collection(
            Next(true), [{alias, Next(alias)}, {alias, Not(Next(alias))}],
        ), (frozenset({true, Next(true)}), frozenset({true, Not(Next(true))})))

    def test_input_types_and_normal_form_are_checked(self):
        p = Proposition("p")
        for check in (check_elementary_set_collection, validate_elementary_set_collection):
            with self.subTest(check=check.__name__):
                with self.assertRaisesRegex(TypeError, "formula must be an LTLFormula"):
                    check("p", [])
                with self.assertRaisesRegex(TypeError, "candidate members must be LTLFormula"):
                    check(p, [{"p"}])
                with self.assertRaisesRegex(ValueError, "not normalized"):
                    check(parse_ltl('F"p"'), [])


if __name__ == "__main__":
    unittest.main()
