import unittest

from mocha import (
    CTLFixedPointStep, CTLPredecessorStep, CTLSubformulaStep,
    model_check_ctl, trace_ctl_model_checking,
    to_existential_normal_form,
)
from mocha.io import parse_ctl
from mocha.algorithms.trace import AlgorithmTrace
from mocha.models import TransitionSystem
from mocha.logic import PathFormula, StateFormula, ltl
from mocha.logic.ctl import (
    Always, CTLPathFormula, CTLStateFormula, Exists, ForAll, Next,
    Proposition, Until,
)


def _system() -> TransitionSystem[str, str, str]:
    return TransitionSystem.from_edges(
        states={"s0", "s1", "s2", "s3", "s4"},
        edges={
            ("s0", "s1"), ("s0", "s2"), ("s1", "s1"),
            ("s2", "s3"), ("s3", "s3"), ("s4", "s4"),
        },
        action="go",
        initial_states={"s0"},
        atomic_propositions={"p", "q"},
        labels={
            "s0": {"p"}, "s1": {"p"}, "s2": {"p"},
            "s3": {"q"}, "s4": {"q"},
        },
    )


class CTLModelCheckingTests(unittest.TestCase):
    def test_eventually_and_weak_until_after_normalization(self) -> None:
        system = _system()
        for source, expected in (
            ('EF "q"', {"s0", "s2", "s3", "s4"}),
            ('E("p" W "q")', system.states),
            ('E("p" W false)', {"s0", "s1"}),
            ('E(false W "q")', {"s3", "s4"}),
            ('EF false', set()),
        ):
            with self.subTest(source=source):
                formula = parse_ctl(source)
                with self.assertRaisesRegex(ValueError, "existential normal form"):
                    model_check_ctl(system, formula)
                normalized = to_existential_normal_form(formula)
                result = model_check_ctl(system, normalized)
                self.assertEqual(result.satisfying_states, expected)

    def test_separated_nodes_keep_satisfaction_sets_on_state_formulae(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        formula = Exists(Until(p, Exists(Next(q))))
        trace = trace_ctl_model_checking(_system(), formula, detail="reasoning")
        self.assertEqual(trace.result.satisfying_states, frozenset({"s0", "s2", "s3", "s4"}))
        self.assertTrue(trace.result.satisfies)
        for row in trace.result.subformula_sets:
            self.assertIsInstance(row.formula, StateFormula)
            self.assertNotIsInstance(row.formula, PathFormula)
            for premise, _ in row.premises:
                self.assertIsInstance(premise, StateFormula)
        self.assertEqual(
            model_check_ctl(_system(), Exists(Always(p))).satisfying_states,
            frozenset({"s0", "s1"}),
        )

    def test_rejects_formulae_outside_the_ctl_state_fragment(self) -> None:
        p = Proposition("p")
        for formula in (
            Next(p), Always(p), Until(p, p),
            ltl.Always(ltl.Proposition("p")),
            CTLStateFormula(), ForAll(CTLPathFormula()),
            Exists(Next(CTLStateFormula())),
        ):
            steps = []
            with self.subTest(node=type(formula).__name__), self.assertRaisesRegex(ValueError, "CTL fragment"):
                model_check_ctl(_system(), formula, on_step=steps.append)
            self.assertEqual(steps, [])

    def test_reports_every_distinct_subformula_bottom_up(self) -> None:
        formula = parse_ctl('E("p" U "q") & !EG "p"')
        trace = trace_ctl_model_checking(_system(), formula)
        self.assertIsInstance(trace, AlgorithmTrace)
        self.assertTrue(all(isinstance(step, CTLSubformulaStep) for step in trace.steps))
        self.assertEqual(
            [step.formula for step in trace.steps],
            [
                parse_ctl('"p"'), parse_ctl('"q"'), parse_ctl('E("p" U "q")'),
                parse_ctl('EG "p"'), parse_ctl('!EG "p"'), formula,
            ],
        )
        self.assertEqual(
            [step.satisfying_states for step in trace.steps],
            [
                frozenset({"s0", "s1", "s2"}),
                frozenset({"s3", "s4"}),
                frozenset({"s0", "s2", "s3", "s4"}),
                frozenset({"s0", "s1"}),
                frozenset({"s2", "s3", "s4"}),
                frozenset({"s2", "s3", "s4"}),
            ],
        )
        self.assertEqual(trace.result.subformula_sets, trace.steps)
        self.assertEqual(trace.result.satisfying_states, frozenset({"s2", "s3", "s4"}))
        self.assertFalse(trace.result.satisfies)
        self.assertEqual(trace.result.violating_initial_states, frozenset({"s0"}))
        self.assertEqual(trace.result.set_for(parse_ctl('"q"')), frozenset({"s3", "s4"}))
        with self.assertRaises(KeyError):
            trace.result.set_for(parse_ctl('EX "q"'))

    def test_reasoning_shows_successor_checks_and_backward_search(self) -> None:
        formula = parse_ctl('EX "q" & E("p" U "q") & EG "p"')
        trace = trace_ctl_model_checking(_system(), formula, detail="reasoning")
        summaries = tuple(step for step in trace.steps if isinstance(step, CTLSubformulaStep))
        self.assertEqual(summaries, trace.result.subformula_sets)
        self.assertTrue(all(step.explanation for step in summaries))
        self.assertEqual(
            trace.result.set_for(parse_ctl('EX "q"')),
            frozenset({"s2", "s3", "s4"}),
        )

        predecessor = next(step for step in trace.steps if isinstance(step, CTLPredecessorStep))
        self.assertEqual(predecessor.target_states, frozenset({"s3", "s4"}))
        matches = {check.state: check.matching_successors for check in predecessor.checks}
        self.assertEqual(matches["s2"], frozenset({"s3"}))
        self.assertEqual(matches["s0"], frozenset())

        until = parse_ctl('E("p" U "q")')
        until_steps = [step for step in trace.steps
                       if isinstance(step, CTLFixedPointStep) and step.formula == until]
        self.assertEqual(until_steps[0].approximation, {"s3", "s4"})
        self.assertEqual(until_steps[0].pending_states, {"s3", "s4"})
        self.assertIsNone(until_steps[0].processed_state)
        self.assertEqual(until_steps[-1].approximation, trace.result.set_for(until))
        self.assertEqual(until_steps[-1].pending_states, frozenset())
        self.assertEqual(
            {step.processed_state for step in until_steps[1:]},
            trace.result.set_for(until),
        )
        self.assertEqual(len(until_steps), len(trace.result.set_for(until)) + 1)
        for previous, step in zip(until_steps, until_steps[1:]):
            self.assertIn(step.processed_state, previous.pending_states)
            self.assertEqual(step.approximation, previous.approximation | step.added_states)
            self.assertTrue(step.added_states.isdisjoint(previous.approximation))
            self.assertEqual(
                step.pending_states,
                (previous.pending_states - {step.processed_state}) | step.added_states,
            )
            for check in step.checks:
                self.assertIn(check.state, step.added_states)
                self.assertEqual(check.matching_successors, {step.processed_state})

        globally = parse_ctl('EG "p"')
        globally_steps = [step for step in trace.steps
                          if isinstance(step, CTLFixedPointStep) and step.formula == globally]
        self.assertEqual(globally_steps[0].approximation, {"s0", "s1", "s2"})
        self.assertEqual(globally_steps[0].pending_states, {"s3", "s4"})
        self.assertEqual(dict(globally_steps[0].successor_counts), {"s0": 2, "s1": 1, "s2": 1})
        self.assertEqual(globally_steps[-1].approximation, {"s0", "s1"})
        self.assertEqual(globally_steps[-1].pending_states, frozenset())
        self.assertEqual(dict(globally_steps[-1].successor_counts), {"s0": 1, "s1": 1, "s2": 0})
        for previous, step in zip(globally_steps, globally_steps[1:]):
            self.assertIn(step.processed_state, previous.pending_states)
            self.assertEqual(step.approximation, previous.approximation - step.removed_states)
            self.assertEqual(
                step.pending_states,
                (previous.pending_states - {step.processed_state}) | step.removed_states,
            )
        system = _system()
        for step in globally_steps:
            self.assertEqual(
                dict(step.successor_counts),
                {state: len(system.post(state) & (step.approximation | step.pending_states))
                 for state in globally_steps[0].approximation},
            )
        self.assertFalse(
            next(check for step in globally_steps for check in step.checks
                 if check.state == "s2").matching_successors
        )

        callback_steps = []
        direct = model_check_ctl(
            _system(), formula, detail="reasoning", on_step=callback_steps.append,
        )
        self.assertEqual(direct, trace.result)
        self.assertEqual(tuple(callback_steps), trace.steps)

    def test_backward_search_stops_immediately_with_an_empty_worklist(self) -> None:
        system = _system()
        for source, expected in (
            ('E("p" U false)', frozenset()),
            ('EG true', system.states),
        ):
            with self.subTest(source=source):
                formula = to_existential_normal_form(parse_ctl(source))
                trace = trace_ctl_model_checking(system, formula, detail="reasoning")
                steps = [step for step in trace.steps if isinstance(step, CTLFixedPointStep)]
                self.assertEqual(len(steps), 1)
                self.assertEqual(steps[0].iteration, 0)
                self.assertEqual(steps[0].pending_states, frozenset())
                self.assertIsNone(steps[0].processed_state)
                self.assertEqual(trace.result.satisfying_states, expected)

    def test_backward_search_propagates_additions_and_removals_along_a_chain(self) -> None:
        states = frozenset(range(7))
        system = TransitionSystem.from_edges(
            states=states,
            edges={(state, state + 1) for state in range(6)} | {(6, 6)},
            action="go", initial_states={0}, atomic_propositions={"p", "q"},
            labels={state: {"p"} if state < 6 else {"q"} for state in states},
        )
        for source, expected in (
            ('E("p" U "q")', states),
            ('EG "p"', frozenset()),
        ):
            with self.subTest(source=source):
                trace = trace_ctl_model_checking(system, parse_ctl(source), detail="reasoning")
                steps = [step for step in trace.steps if isinstance(step, CTLFixedPointStep)]
                self.assertEqual(trace.result.satisfying_states, expected)
                self.assertEqual(len(steps), len(states) + 1)
                self.assertEqual(steps[-1].pending_states, frozenset())
                self.assertEqual({step.processed_state for step in steps[1:]}, states)

    def test_true_negation_and_reused_subformulae(self) -> None:
        system = _system()
        formula = parse_ctl('true & !"q" & EX "q"')
        result = model_check_ctl(system, formula)
        self.assertEqual(result.set_for(parse_ctl('true')), system.states)
        self.assertEqual(result.set_for(parse_ctl('!"q"')), frozenset({"s0", "s1", "s2"}))
        self.assertEqual(result.satisfying_states, frozenset({"s2"}))
        self.assertEqual(len([row for row in result.subformula_sets if row.formula == parse_ctl('"q"')]), 1)
        self.assertTrue(model_check_ctl(system, parse_ctl('EX "p"')).satisfies)

    def test_rejects_non_enf_unknown_propositions_and_terminal_states(self) -> None:
        system = _system()
        with self.assertRaisesRegex(ValueError, "existential normal form"):
            model_check_ctl(system, parse_ctl('AX "p"'))
        with self.assertRaisesRegex(ValueError, "existential normal form"):
            model_check_ctl(system, parse_ctl('false'))
        with self.assertRaisesRegex(ValueError, "Unknown atomic propositions"):
            model_check_ctl(system, parse_ctl('EX "missing"'))
        with self.assertRaisesRegex(ValueError, "detail"):
            trace_ctl_model_checking(system, parse_ctl('true'), detail="verbose")

        terminal = TransitionSystem.from_edges(
            states={"s"}, edges=set(), action="go",
            atomic_propositions={"p"},
        )
        with self.assertRaisesRegex(ValueError, "terminal states"):
            model_check_ctl(terminal, parse_ctl('"p"'))


if __name__ == "__main__":
    unittest.main()
