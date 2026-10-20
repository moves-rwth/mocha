"""Test LTL satisfiability and validity, including evidence for each verdict.

Satisfiability asks whether at least one infinite word satisfies a formula.
Validity asks whether every infinite word satisfies it, checked by testing the
negated formula for unsatisfiability. These checks take a formula directly and
do not require a transition system.

A word is a sequence of valuations, each listing the proposition names true at
that position. Infinite witnesses are represented finitely by a prefix followed
by a nonempty repeating loop. ``witness[:loop_start]`` occurs once, and
``witness[loop_start:]`` repeats forever. An invalid formula has a counterexample
word satisfying its negation.

Witness tests check both the returned nondeterministic Büchi automaton (NBA)
run and the word's meaning with an independent LTL evaluator. Trace tests check
formula translation and the nested depth-first search for an accepting cycle.
"""

import unittest
from unittest.mock import patch

from mocha import (
    check_ltl_satisfiability, check_ltl_validity,
    trace_ltl_satisfiability, trace_ltl_validity,
)
from mocha.io import parse_ltl
from mocha.logic.ltl import Not
from test_ltl import _evaluate


class LTLSatisfiabilityAndValidityTests(unittest.TestCase):
    """Check formula verdicts, infinite-word evidence, and optional trace output."""

    def test_checks_without_callbacks_skip_persistence_snapshots(self):
        """Both checks return verdicts without constructing search trace records."""
        with patch(
            "mocha.algorithms.persistence.PersistenceStep",
            side_effect=AssertionError("Persistence snapshots require a callback"),
        ):
            self.assertTrue(check_ltl_satisfiability(parse_ltl('F"p"')).satisfiable)
            self.assertFalse(check_ltl_satisfiability(parse_ltl("false")).satisfiable)
            self.assertTrue(check_ltl_validity(parse_ltl("true")).valid)
            self.assertFalse(check_ltl_validity(parse_ltl('"p"')).valid)

    def assert_satisfying_witness(self, formula, result):
        """Check that the returned infinite word satisfies ``formula``.

        ``result.run`` is an NBA path whose last state repeats the state at
        ``result.loop_start``. ``result.witness`` has one valuation per edge,
        without an extra valuation for the repeated endpoint. Its suffix from
        that index repeats forever. Verify that the run starts in an initial
        state, follows edges labelled by these valuations, and visits an
        accepting state on its loop. Independently evaluate the formula at
        position zero of the resulting infinite word.
        """
        self.assertTrue(result.satisfiable)
        self.assertIsNotNone(result.witness)
        self.assertIsNotNone(result.run)
        self.assertIsNotNone(result.loop_start)
        self.assertEqual(len(result.witness), len(result.run) - 1)
        self.assertEqual(result.run[result.loop_start], result.run[-1])
        self.assertIn(result.run[0], result.nba.initial_states)
        self.assertTrue(any(state in result.nba.accepting_states
                            for state in result.run[result.loop_start:-1]))
        for source, letter, target in zip(result.run, result.witness, result.run[1:]):
            self.assertIn(target, result.nba.post(source, letter))
        self.assertTrue(_evaluate(formula, result.witness, result.loop_start, 0))

    def test_satisfiable_formulas_return_words_that_satisfy_them(self):
        """Every positive verdict includes an accepting run and a satisfying word."""
        for source in ("true", '"p"', 'X"p"', 'F"p" & F"q"', 'G"p"',
                       '"p" U "q"'):
            with self.subTest(source=source):
                formula = parse_ltl(source)
                self.assert_satisfying_witness(formula, check_ltl_satisfiability(formula))

    def test_unsatisfiable_formulas_return_no_run_word_or_loop_index(self):
        """An empty NBA language yields a negative verdict with no witness fields."""
        for source in ("false", '"p" & !"p"', 'G"p" & F!"p"'):
            with self.subTest(source=source):
                result = check_ltl_satisfiability(parse_ltl(source))
                self.assertFalse(result.satisfiable)
                self.assertTrue(result.emptiness.satisfies)
                self.assertIsNone(result.run)
                self.assertIsNone(result.witness)
                self.assertIsNone(result.loop_start)

    def test_valid_formulas_have_unsatisfiable_negations_and_no_counterexample(self):
        """Validity retains the explicit negation and its unsatisfiable result."""
        for source in ("true", '"p" | !"p"', 'G"p" -> F"p"'):
            with self.subTest(source=source):
                formula = parse_ltl(source)
                result = check_ltl_validity(formula)
                self.assertTrue(result.valid)
                self.assertEqual(result.negated_formula, Not(formula))
                self.assertEqual(result.satisfiability.formula, Not(formula))
                self.assertIsNone(result.counterexample)

    def test_invalid_formula_returns_a_word_that_falsifies_it(self):
        """The negation's satisfying witness must falsify the original formula."""
        formula = parse_ltl('"p" -> X"p"')
        result = check_ltl_validity(formula)
        self.assertFalse(result.valid)
        self.assert_satisfying_witness(Not(formula), result.satisfiability)
        self.assertFalse(_evaluate(formula, result.counterexample, result.loop_start, 0))

    def test_satisfiability_and_validity_traces_include_construction_and_search(self):
        """Trace helpers retain ordered events from translation through the verdict.

        Satisfiability callbacks agree with its collected trace, including the
        accepting-cycle event. Validity wraps the satisfiability events between
        an initial negation and its own verdict, using consecutive step numbers.
        """
        formula = parse_ltl('F"p"')
        reported = []
        direct = check_ltl_satisfiability(formula, on_step=reported.append)
        trace = trace_ltl_satisfiability(formula)
        self.assertEqual(tuple(reported), trace.steps)
        self.assertEqual(direct.satisfiable, trace.result.satisfiable)
        self.assertEqual([step.iteration for step in trace.steps], list(range(len(trace.steps))))
        self.assertEqual(trace.steps[-1].stage, "verdict")
        self.assertIn("translation", {step.stage for step in trace.steps})
        self.assertIn("cycle_found", {step.detail.operation for step in trace.steps
                                      if step.stage == "emptiness" and step.detail is not None})

        validity = trace_ltl_validity(parse_ltl('"p"'))
        self.assertEqual(validity.steps[0].stage, "negation")
        self.assertEqual(validity.steps[-1].stage, "verdict")
        self.assertTrue(any(step.stage == "satisfiability" for step in validity.steps))
        self.assertEqual([step.iteration for step in validity.steps], list(range(len(validity.steps))))


if __name__ == "__main__":
    unittest.main()
