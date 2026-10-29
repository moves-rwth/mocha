import unittest

from mocha.algorithms.invariance import check_invariant, trace_invariant
from mocha.models import TransitionSystem


class InvarianceTests(unittest.TestCase):
    def test_trace_invariant_records_a_counterexample_path(self) -> None:
        system = TransitionSystem.from_components(
            states={"s0", "s1", "s2", "unreachable"},
            actions={"a", "b"},
            transitions={
                ("s0", "a", "s1"),
                ("s1", "a", "s2"),
                ("s2", "b", "s2"),
                ("unreachable", "a", "unreachable"),
            },
            initial_states={"s0"},
        )

        trace = trace_invariant(transition_system=system, invariant_states={"s0", "s1"})

        self.assertFalse(trace.result.satisfies)
        self.assertEqual(trace.result.counterexample, ("s0", "s1", "s2"))
        self.assertEqual(
            tuple(step.current_state for step in trace.steps),
            ("s0", "s1", "s2"),
        )
        self.assertFalse(trace.steps[-1].satisfies_invariant)
        self.assertEqual(
            tuple(step.visited for step in trace.steps),
            (
                frozenset({"s0"}),
                frozenset({"s0", "s1"}),
                frozenset({"s0", "s1", "s2"}),
            ),
        )

    def test_accepts_when_only_unreachable_states_violate_the_invariant(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start", "safe", "unreachable"},
            edges={("start", "safe"), ("safe", "safe")},
            initial_states={"start"},
        )

        trace = trace_invariant(system, {"start", "safe"})

        self.assertTrue(trace.result.satisfies)
        self.assertIsNone(trace.result.counterexample)
        self.assertEqual(trace.steps[-1].visited, {"start", "safe"})
        self.assertTrue(all(step.satisfies_invariant for step in trace.steps))

    def test_initial_state_violation_has_a_single_state_counterexample(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start", "later"},
            edges={("start", "later")},
            initial_states={"start"},
        )

        trace = trace_invariant(system, {"later"})

        self.assertFalse(trace.result.satisfies)
        self.assertEqual(trace.result.counterexample, ("start",))
        self.assertEqual(len(trace.steps), 1)
        self.assertEqual(trace.steps[0].visited, {"start"})
        self.assertFalse(trace.steps[0].satisfies_invariant)

    def test_checks_every_initial_component(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"safe_start", "other_start", "bad"},
            edges={("safe_start", "safe_start"), ("other_start", "bad")},
            initial_states={"safe_start", "other_start"},
        )

        result = check_invariant(
            transition_system=system, invariant_states={"safe_start", "other_start"},
        )

        self.assertFalse(result.satisfies)
        self.assertEqual(result.counterexample, ("other_start", "bad"))

    def test_cycles_and_shared_successors_are_examined_only_once(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start", "left", "right", "join"},
            edges={
                ("start", "left"), ("start", "right"),
                ("left", "join"), ("right", "join"),
                ("join", "start"), ("join", "join"),
            },
            initial_states={"start"},
        )

        trace = trace_invariant(system, system.states)

        self.assertTrue(trace.result.satisfies)
        self.assertIsNone(trace.result.counterexample)
        self.assertCountEqual(
            (step.current_state for step in trace.steps), system.states,
        )
        self.assertEqual(trace.steps[-1].visited, system.states)

    def test_branching_counterexample_follows_existing_transitions(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start", "left", "right", "bad"},
            edges={
                ("start", "left"), ("start", "right"),
                ("left", "bad"), ("right", "bad"), ("bad", "start"),
            },
            initial_states={"start"},
        )

        result = check_invariant(system, {"start", "left", "right"})

        self.assertFalse(result.satisfies)
        path = result.counterexample
        self.assertIsNotNone(path)
        self.assertIn(path[0], system.initial_states)
        self.assertEqual(path[-1], "bad")
        self.assertEqual(len(path), len(set(path)))
        for source, target in zip(path, path[1:]):
            self.assertIn(target, system.post(source))

    def test_no_initial_states_satisfies_the_invariant_without_steps(self) -> None:
        for states in (set(), {"unreachable"}):
            with self.subTest(states=states):
                system = TransitionSystem.from_edges(
                    states=states, edges=set(), action="step",
                )

                trace = trace_invariant(system, set())

                self.assertTrue(trace.result.satisfies)
                self.assertIsNone(trace.result.counterexample)
                self.assertEqual(trace.steps, ())

    def test_terminal_states_can_satisfy_or_violate_the_invariant(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"terminal"}, edges=set(), initial_states={"terminal"},
        )

        for invariant in ({"terminal"}, set()):
            with self.subTest(invariant=invariant):
                result = check_invariant(system, invariant)

                self.assertEqual(result.satisfies, bool(invariant))
                self.assertEqual(
                    result.counterexample, None if invariant else ("terminal",),
                )

    def test_rejects_unknown_invariant_states_before_reporting_steps(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start"}, edges=set(), initial_states={"start"},
        )
        steps = []

        with self.assertRaisesRegex(ValueError, "unknown states"):
            check_invariant(system, {"missing"}, on_step=steps.append)
        self.assertEqual(steps, [])
        with self.assertRaisesRegex(ValueError, "unknown states"):
            trace_invariant(system, {"missing"})

    def test_callbacks_and_collected_traces_agree_for_iterable_invariants(self) -> None:
        system = TransitionSystem.from_edges(
            action="step",
            states={"start", "middle", "end"},
            edges={("start", "middle"), ("middle", "end")},
            initial_states={"start"},
        )

        for invariant in ({"start", "middle"}, system.states):
            with self.subTest(invariant=invariant):
                steps = []
                direct = check_invariant(system, iter(invariant), on_step=steps.append)
                trace = trace_invariant(system, iter(invariant))

                self.assertEqual(trace.result, direct)
                self.assertEqual(trace.steps, tuple(steps))

    def test_counterexamples_support_none_and_other_hashable_states(self) -> None:
        for path in (
            (None,), (None, 0, ("bad",)),
            (0, None, ("bad",)), (0, ("bad",), None),
        ):
            with self.subTest(path=path):
                system = TransitionSystem.from_edges(
                    action="step",
                    states=set(path), edges=set(zip(path, path[1:])),
                    initial_states={path[0]},
                )

                result = check_invariant(system, path[:-1])

                self.assertFalse(result.satisfies)
                self.assertEqual(result.counterexample, path)


if __name__ == "__main__":
    unittest.main()
