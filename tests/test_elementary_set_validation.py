from dataclasses import FrozenInstanceError
from itertools import combinations
import unittest

from mocha import normalize_ltl
from mocha.algorithms.ltl2gnba.elementary_set_validation import check_elementary_set
from mocha.io import parse_ltl


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


if __name__ == "__main__":
    unittest.main()
