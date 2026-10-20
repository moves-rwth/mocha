"""Check GNBA construction stages and language agreement on small lasso words.

An independent finite-product acceptance check compares the constructed GNBA
with direct LTL evaluation, including derived operators and multiple obligations.
"""

import unittest
from unittest.mock import patch

from mocha import (
    compute_acceptance_sets, compute_initial_states, enumerate_elementary_sets,
    ltl_to_gnba, trace_acceptance_sets, trace_initial_states, trace_ltl_to_gnba,
)
from mocha.io import parse_ltl
from mocha.algorithms.ltl_transformations import trace_normalize_ltl
from mocha.algorithms.ltl2gnba import trace_elementary_sets, trace_transition_relation
from mocha.logic.ltl import BooleanConstant, Next, Not, Proposition, Until
from test_ltl import _evaluate


def accepts_lasso(automaton, word, loop_start):
    """Check GNBA acceptance of a nonempty ultimately periodic valuation word.

    Positions before ``loop_start`` occur once; the suffix repeats forever.
    Build the reachable product of automaton states and word positions, then
    identify strongly connected components by mutual reachability. Acceptance
    requires a cyclic component intersecting every generalized Büchi set.
    This avoids using the production automaton-emptiness implementation.
    """
    initial = {(state, 0) for state in automaton.initial_states}
    graph = {}
    todo = list(initial)
    while todo:
        state, position = node = todo.pop()
        if node in graph:
            continue
        next_position = position + 1 if position + 1 < len(word) else loop_start
        successors = {(target, next_position) for target in automaton.post(state, word[position])}
        graph[node] = successors
        todo.extend(successors - graph.keys())

    # Reachability in both directions identifies SCCs without using a library
    # acceptance algorithm (these examples have only small product graphs).
    def reachable(start):
        visited = set()
        pending = [start]
        while pending:
            node = pending.pop()
            if node not in visited:
                visited.add(node)
                pending.extend(graph[node] - visited)
        return visited

    reach = {node: reachable(node) for node in graph}
    for node in graph:
        component = {other for other in reach[node] if node in reach[other]}
        cyclic = len(component) > 1 or node in graph[node]
        if cyclic and all(any(state in accepting for state, _ in component)
                          for accepting in automaton.accepting_sets):
            return True
    return False


class LTLGNBATests(unittest.TestCase):
    def test_components_accept_manual_states_without_enumeration_or_other_stages(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        states = [{p, Not(q), formula}, {Not(p), q, formula},
                  {p, Not(q), Not(formula)}, {Not(p), Not(q), Not(formula)}]
        initial_steps, acceptance_steps = [], []
        with patch(
            "mocha.algorithms.ltl2gnba.elementary_set_enumeration.ElementaryTableRow",
            side_effect=AssertionError("Components must not enumerate states"),
        ), patch(
            "mocha.algorithms.ltl2gnba.transitions.compute_transition_relation",
            side_effect=AssertionError("Initial and accepting states do not require transitions"),
        ):
            initial = compute_initial_states(
                formula, (iter(state) for state in states), on_step=initial_steps.append,
            )
            acceptance = compute_acceptance_sets(
                formula, (iter(state) for state in states), on_step=acceptance_steps.append,
            )
            initial_trace = trace_initial_states(formula, states)
            acceptance_trace = trace_acceptance_sets(formula, states)
        self.assertEqual(initial.state_indices, {0, 1})
        self.assertEqual(initial.initial_states, set(map(frozenset, states[:2])))
        self.assertEqual(acceptance.conditions[0].state_indices, {1, 2, 3})
        self.assertEqual([step.state_index for step in initial_steps], list(range(4)))
        self.assertEqual([decision.reason for decision in acceptance_steps[0].decisions],
                         ["until_pending", "right_present", "until_absent", "until_absent"])
        self.assertEqual(initial_trace.result, initial)
        self.assertEqual(initial_trace.steps, tuple(initial_steps))
        self.assertEqual(acceptance_trace.result, acceptance)
        self.assertEqual(acceptance_trace.steps, tuple(acceptance_steps))
        states[0].clear()
        self.assertEqual(initial_steps[0].state, {p, Not(q), formula})

    def test_components_simplify_equivalent_state_members_before_membership_checks(self):
        p, true = Proposition("p"), BooleanConstant(True)
        formula = Until(p, true)
        alias = Not(BooleanConstant(False))
        states = [{Not(Not(p)), alias, Until(Not(Not(p)), alias)},
                  {Not(p), alias, Until(p, alias)}]
        canonical = {frozenset({p, true, formula}), frozenset({Not(p), true, formula})}
        initial = compute_initial_states(formula, states)
        acceptance = compute_acceptance_sets(formula, states)
        self.assertEqual(initial.initial_states, canonical)
        self.assertEqual(initial.state_indices, {0, 1})
        self.assertEqual(acceptance.conditions[0].accepting_states, canonical)
        self.assertEqual(acceptance.conditions[0].state_indices, {0, 1})

    def test_acceptance_obligations_come_from_formula_not_present_state_members(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        state = frozenset({Not(p), Not(q), Not(formula)})
        result = compute_acceptance_sets(formula, [state])
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0].formula, formula)
        self.assertEqual(result.conditions[0].accepting_states, {state})
        self.assertEqual(result.conditions[0].state_indices, {0})

    def test_components_handle_empty_collections_without_dropping_obligations(self):
        p, q = Proposition("p"), Proposition("q")
        formula = Until(p, q)
        initial = trace_initial_states(formula, [])
        self.assertEqual(initial.steps, ())
        self.assertEqual(initial.result.initial_states, frozenset())
        self.assertEqual(initial.result.state_indices, frozenset())
        acceptance = trace_acceptance_sets(formula, [])
        self.assertEqual(len(acceptance.steps), 1)
        self.assertEqual(acceptance.steps[0].decisions, ())
        self.assertEqual(acceptance.result.accepting_sets, {frozenset()})
        no_until = trace_acceptance_sets(p, [])
        self.assertEqual(no_until.result.accepting_sets, frozenset())
        self.assertIsNone(no_until.steps[0].condition)

    def test_components_validate_states_before_callbacks(self):
        p = Proposition("p")
        for compute in (compute_initial_states, compute_acceptance_sets):
            with self.subTest(function=compute.__name__):
                reported = []
                with self.assertRaisesRegex(ValueError, "B2 is not an elementary set"):
                    compute(p, [{p}, {p, Not(p)}], on_step=reported.append)
                self.assertEqual(reported, [])
                with self.assertRaisesRegex(ValueError, "duplicates elementary set B1"):
                    compute(p, [{p}, {Not(Not(p))}])
                with self.assertRaisesRegex(TypeError, "candidate members must be LTLFormula"):
                    compute(p, [{"p"}])
                with self.assertRaisesRegex(ValueError, "not normalized"):
                    compute(parse_ltl('F"p"'), [])

    def test_component_interfaces_require_formula_and_collection(self):
        p = Proposition("p")
        enumeration = enumerate_elementary_sets(p)
        for compute in (compute_initial_states, trace_initial_states,
                        compute_acceptance_sets, trace_acceptance_sets):
            with self.subTest(function=compute.__name__):
                with self.assertRaises(TypeError):
                    compute(p)
                with self.assertRaises(TypeError):
                    compute(enumeration)
                with self.assertRaisesRegex(TypeError, "formula must be an LTLFormula"):
                    compute(enumeration, enumeration.elementary_sets)

    def exercise(self):
        """Return the worked formula shared by initial, transition, and acceptance tests."""
        return parse_ltl('(!("a" & X"b") & !("a" & "b")) U (("a" & X"b") & !("a" & "b"))')

    def test_initial_and_acceptance_sets_match_exercise(self):
        enumeration = enumerate_elementary_sets(self.exercise())
        initial = trace_initial_states(enumeration.formula, enumeration.elementary_sets)
        self.assertEqual({i + 1 for i in initial.result.state_indices}, {2, 4, 6, 8, 10, 11})
        self.assertEqual(len(initial.steps), 13)
        for index, step in enumerate(initial.steps):
            self.assertEqual(step.state_index, index)
            self.assertEqual(step.state, enumeration.elementary_sets[index])
            self.assertEqual(step.is_initial, index in initial.result.state_indices)
            self.assertIn(f"B{index + 1}", step.message)
        acceptance = trace_acceptance_sets(enumeration.formula, enumeration.elementary_sets)
        self.assertEqual(len(acceptance.result.conditions), 1)
        condition = acceptance.result.conditions[0]
        self.assertEqual(condition.formula, enumeration.formula)
        self.assertEqual({i + 1 for i in condition.state_indices}, {1, 3, 5, 7, 9, 11, 12, 13})
        decisions = acceptance.steps[0].decisions
        self.assertEqual(decisions[0].reason, "until_absent")
        self.assertEqual(decisions[1].reason, "until_pending")
        self.assertEqual(decisions[10].reason, "right_present")
        for index, decision in enumerate(decisions):
            self.assertEqual(decision.included, index in condition.state_indices)
            self.assertEqual(decision.state, enumeration.elementary_sets[index])
        self.assertIn("F = {B1, B3, B5, B7, B9, B11, B12, B13}", acceptance.steps[0].to_markdown())

    def test_standalone_callbacks_match_traces(self):
        enumeration = enumerate_elementary_sets(self.exercise())
        for compute, trace in ((compute_initial_states, trace_initial_states),
                               (compute_acceptance_sets, trace_acceptance_sets)):
            reported = []
            result = compute(enumeration.formula, enumeration.elementary_sets, on_step=reported.append)
            collected = trace(enumeration.formula, enumeration.elementary_sets)
            self.assertEqual(result, collected.result)
            self.assertEqual(tuple(reported), collected.steps)

    def test_no_until_has_empty_family_and_explanation(self):
        for source in ('X"p"', "true", "false"):
            enumeration = enumerate_elementary_sets(parse_ltl(source))
            trace = trace_acceptance_sets(enumeration.formula, enumeration.elementary_sets)
            self.assertEqual(trace.result.conditions, ())
            self.assertEqual(trace.result.accepting_sets, frozenset())
            self.assertIsNone(trace.steps[0].condition)
            self.assertIn("every infinite run", trace.steps[0].message)
        self.assertFalse(compute_initial_states(enumeration.formula, enumeration.elementary_sets).initial_states)
        true_states = enumerate_elementary_sets(parse_ltl("true"))
        self.assertEqual(compute_initial_states(true_states.formula, true_states.elementary_sets).state_indices, {0})

    def test_one_condition_per_until_even_when_sets_coincide(self):
        enumeration = enumerate_elementary_sets(parse_ltl('("p" U true) & ("q" U true)'))
        trace = trace_acceptance_sets(enumeration.formula, enumeration.elementary_sets)
        self.assertEqual(len(trace.result.conditions), 2)
        self.assertEqual(len(trace.steps), 2)
        self.assertEqual(len(trace.result.accepting_sets), 1)
        for condition in trace.result.conditions:
            self.assertEqual(condition.accepting_states, set(enumeration.elementary_sets))

    def test_full_pipeline_reuses_stage_traces_and_builds_gnba(self):
        formula = parse_ltl('!("a" W X"b")')
        trace = trace_ltl_to_gnba(formula)
        result = trace.result
        stages = (
            ("normalization", trace_normalize_ltl(formula)),
            ("elementary_sets", trace_elementary_sets(result.normalized_formula)),
            ("initial_states", trace_initial_states(
                result.normalized_formula, result.elementary_sets.elementary_sets,
            )),
            ("transitions", trace_transition_relation(
                result.normalized_formula, result.elementary_sets.elementary_sets,
            )),
            ("acceptance", trace_acceptance_sets(
                result.normalized_formula, result.elementary_sets.elementary_sets,
            )),
        )
        expected = [(name, detail) for name, stage in stages for detail in stage.steps]
        self.assertEqual([(step.stage, step.detail) for step in trace.steps], expected)
        self.assertEqual([step.iteration for step in trace.steps], list(range(len(trace.steps))))
        reported = []
        direct = ltl_to_gnba(formula, on_step=reported.append)
        self.assertEqual(tuple(reported), trace.steps)
        self.assertEqual(frozenset(direct.automaton.transitions()), frozenset(result.automaton.transitions()))
        self.assertEqual(result.automaton.states, set(result.elementary_sets.elementary_sets))
        self.assertEqual(result.automaton.initial_states, result.initial_states.initial_states)
        self.assertEqual(result.automaton.accepting_sets, result.acceptance.accepting_sets)
        self.assertEqual(frozenset(result.automaton.transitions()), result.transition_relation.transitions)

    def test_full_exercise(self):
        result = ltl_to_gnba(self.exercise())
        self.assertEqual(len(result.automaton.states), 13)
        self.assertEqual(len(tuple(result.automaton.transitions())), 52)
        self.assertEqual(len(result.automaton.initial_states), 6)
        self.assertEqual(len(result.automaton.accepting_sets), 1)

    def test_gnba_agrees_with_ltl_on_small_lassos(self):
        from itertools import product

        valuations = (frozenset(), frozenset({"p"}), frozenset({"q"}), frozenset({"p", "q"}))
        for source in ("true", "false", '"p"', 'X"p"', '"p" U "q"',
                       'G F "p"', '(F"p") & (F"q")', '"p" W "q"',
                       '!("p" U "q")', 'X("p" U "q")'):
            formula = parse_ltl(source)
            automaton = ltl_to_gnba(formula).automaton
            names = set().union(*automaton.alphabet)
            alphabet = {valuation & names for valuation in valuations}
            for word in product(alphabet, repeat=2):
                for loop_start in (0, 1):
                    with self.subTest(source=source, word=word, loop_start=loop_start):
                        self.assertEqual(accepts_lasso(automaton, word, loop_start),
                                         _evaluate(formula, word, loop_start, 0))


if __name__ == "__main__":
    unittest.main()
