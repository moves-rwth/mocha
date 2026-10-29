"""Test whether all initial infinite system runs satisfy a supplied LTL formula.

For a failed property, check the returned counterexample both as a path in the
original system and as a word falsifying the formula with an independent LTL
evaluator. Its finite prefix is followed by a repeating cycle; the last state
duplicates the state at ``loop_start`` and is omitted when forming the word.

Coverage includes initial label alignment, branching runs, extra proposition
names, product dead ends, input validation, and nested persistence traces.
"""

import unittest
from unittest.mock import patch

from mocha import check_ltl, trace_ltl
from mocha.io import parse_ltl
from mocha.logic.ltl import Not
from mocha.models import TransitionSystem
from test_ltl import _evaluate


def system(labels, edges, *, initial=("s0",), propositions=("p", "q", "extra")):
    """Build a test system from state labels and unlabelled source/target pairs.

    Label-map keys define the states, every edge uses action ``step``, and the
    declared propositions may include names that never appear in any label.
    """
    states = set(labels)
    return TransitionSystem.from_components(
        states=states, actions={"step"},
        transitions={(source, "step", target) for source, target in edges},
        initial_states=set(initial), atomic_propositions=set(propositions),
        labels={state: set(values) for state, values in labels.items()},
    )


class LTLModelCheckingTests(unittest.TestCase):
    """Check universal verdicts, rejecting examples, and construction/search traces."""

    def test_direct_checks_do_not_build_persistence_snapshots(self):
        ts = system({"s0": {"p"}}, {("s0", "s0")})

        with patch(
            "mocha.algorithms.persistence.PersistenceStep",
            side_effect=AssertionError("Persistence snapshots require a callback"),
        ):
            self.assertTrue(check_ltl(ts, parse_ltl('G"p"')).satisfies)
            self.assertFalse(check_ltl(ts, parse_ltl("false")).satisfies)

    def assert_valid_counterexample(self, ts, formula, result):
        """Validate the projected lasso as an initial path falsifying the formula.

        Check every system edge, the repeated endpoint, agreement with the
        accepting product lasso, and direct LTL evaluation on state labels.
        Omit the repeated final state when forming the finite valuation word.
        """
        self.assertFalse(result.satisfies)
        path = result.counterexample
        self.assertIsNotNone(path)
        self.assertIn(path[0], ts.initial_states)
        self.assertEqual(path[result.loop_start], path[-1])
        self.assertGreater(len(path), result.loop_start + 1)
        for source, target in zip(path, path[1:]):
            self.assertIn(target, ts.post(source))
        word = tuple(ts.labels(state) for state in path[:-1])
        self.assertFalse(_evaluate(formula, word, result.loop_start, 0))
        product_path = result.product_counterexample
        self.assertEqual(tuple(state for state, _ in product_path), path)
        self.assertIn(product_path[result.loop_start][1], result.nba.accepting_states)
        self.assertEqual(result.negated_formula, Not(formula))
        self.assertEqual(result.translation.formula, Not(formula))

    def test_initial_negation_and_violating_lasso(self):
        ts = system({"s0": {"p", "extra"}, "s1": {"p"}, "s2": set()},
                    {("s0", "s1"), ("s1", "s2"), ("s2", "s2")})
        formula = parse_ltl('G"p"')
        trace = trace_ltl(ts, formula)
        self.assertEqual(trace.steps[0].stage, "negation")
        self.assertEqual(trace.steps[0].detail, Not(formula))
        self.assertIn("Negate", trace.steps[0].message)
        self.assertEqual(trace.steps[-1].stage, "verdict")
        self.assertEqual([step.iteration for step in trace.steps], list(range(len(trace.steps))))
        self.assert_valid_counterexample(ts, formula, trace.result)
        self.assertEqual(trace.result.nba.alphabet,
                         frozenset({frozenset(), frozenset({"p"})}))
        self.assertEqual(trace.result.product.initial_states,
                         frozenset(state for state in trace.result.product.initial_states
                                   if state[0] == "s0"))
        self.assertEqual({step.stage for step in trace.steps},
                         {"negation", "translation", "nba_conversion", "product", "emptiness", "verdict"})

    def test_satisfied_property_and_callback(self):
        ts = system({"s0": {"p"}}, {("s0", "s0")})
        formula = parse_ltl('G"p"')
        reported = []
        result = check_ltl(ts, formula, on_step=reported.append)
        trace = trace_ltl(ts, formula)
        self.assertTrue(result.satisfies)
        self.assertIsNone(result.counterexample)
        self.assertIsNone(result.loop_start)
        self.assertTrue(result.emptiness.satisfies)
        self.assertEqual(tuple(reported), trace.steps)
        self.assertEqual(result.translation.normalized_formula, trace.result.translation.normalized_formula)
        self.assertEqual(result.product_counterexample, None)

    def test_branching_counterexample_and_eventually(self):
        ts = system({"s0": set(), "good": {"p"}, "bad": set()},
                    {("s0", "good"), ("s0", "bad"), ("good", "good"), ("bad", "bad")})
        self.assert_valid_counterexample(ts, parse_ltl('F"p"'), check_ltl(ts, parse_ltl('F"p"')))
        always_good = system({"s0": set(), "good": {"p"}},
                             {("s0", "good"), ("good", "good")})
        self.assertTrue(check_ltl(always_good, parse_ltl('F"p"')).satisfies)

    def test_boolean_constants_and_empty_initial_set(self):
        ts = system({"s0": set()}, {("s0", "s0")})
        self.assertTrue(check_ltl(ts, parse_ltl("true")).satisfies)
        self.assert_valid_counterexample(ts, parse_ltl("false"), check_ltl(ts, parse_ltl("false")))
        empty_initial = system({"s0": set()}, {("s0", "s0")}, initial=())
        self.assertTrue(check_ltl(empty_initial, parse_ltl("false")).satisfies)

    def test_until_property_with_extra_system_propositions(self):
        ts = system({"s0": {"p", "extra"}, "s1": {"p"}, "s2": {"q"}},
                    {("s0", "s1"), ("s1", "s2"), ("s2", "s2")})
        self.assertTrue(check_ltl(ts, parse_ltl('"p" U "q"')).satisfies)
        bad = system({"s0": {"p", "extra"}, "s1": set()},
                     {("s0", "s1"), ("s1", "s1")})
        formula = parse_ltl('"p" U "q"')
        self.assert_valid_counterexample(bad, formula, check_ltl(bad, formula))

    def test_initial_letter_and_next_are_aligned(self):
        ts = system({"s0": {"p"}, "s1": set()},
                    {("s0", "s1"), ("s1", "s1")})
        self.assertTrue(check_ltl(ts, parse_ltl('"p"')).satisfies)
        self.assert_valid_counterexample(ts, parse_ltl('X"p"'), check_ltl(ts, parse_ltl('X"p"')))
        reverse = system({"s0": set(), "s1": {"p"}},
                         {("s0", "s1"), ("s1", "s1")})
        self.assert_valid_counterexample(reverse, parse_ltl('"p"'),
                                         check_ltl(reverse, parse_ltl('"p"')))
        self.assertTrue(check_ltl(reverse, parse_ltl('X"p"')).satisfies)

    def test_two_eventualities_require_both_acceptance_sets(self):
        alternating = system({"s0": {"p"}, "s1": {"q"}},
                             {("s0", "s1"), ("s1", "s0")})
        formula = parse_ltl('F"p" & F"q"')
        self.assertTrue(check_ltl(alternating, formula).satisfies)
        missing_q = system({"s0": {"p"}}, {("s0", "s0")})
        self.assert_valid_counterexample(missing_q, formula, check_ltl(missing_q, formula))

    def test_rejects_undeclared_proposition_terminal_state_and_non_string_ap(self):
        ts = system({"s0": set()}, {("s0", "s0")}, propositions=("p",))
        with self.assertRaisesRegex(ValueError, "Unknown atomic propositions"):
            check_ltl(ts, parse_ltl('"missing"'))
        terminal = system({"s0": set()}, set())
        with self.assertRaisesRegex(ValueError, "without terminal states"):
            check_ltl(terminal, parse_ltl("true"))
        numeric = TransitionSystem.from_components(
            states={"s0"}, actions={"step"}, transitions={("s0", "step", "s0")},
            initial_states={"s0"}, atomic_propositions={1}, labels={"s0": {1}},
        )
        with self.assertRaisesRegex(TypeError, "string atomic proposition"):
            check_ltl(numeric, parse_ltl("true"))

    def test_partial_nba_product_is_completed_only_for_persistence_search(self):
        ts = system({"s0": {"p"}, "s1": set()},
                    {("s0", "s1"), ("s1", "s1")})
        result = trace_ltl(ts, parse_ltl('G"p"')).result
        self.assertTrue(result.satisfies is False)
        self.assertTrue(result.product.terminal_states)
        self.assertTrue(result.search_product.is_non_blocking())
        self.assertEqual(result.search_product.initial_states, result.product.initial_states)
        self.assert_valid_counterexample(ts, parse_ltl('G"p"'), result)

    def test_trace_uses_persistence_nested_dfs_steps(self):
        ts = system({"s0": {"p"}, "s1": set()},
                    {("s0", "s1"), ("s1", "s1")})
        trace = trace_ltl(ts, parse_ltl('G"p"'))
        operations = [step.detail.operation for step in trace.steps
                      if step.stage == "emptiness" and step.detail is not None]
        self.assertIn("outer_push", operations)
        self.assertIn("inner_push", operations)
        self.assertIn("cycle_found", operations)
        self.assertFalse(trace.result.emptiness.satisfies)


if __name__ == "__main__":
    unittest.main()
