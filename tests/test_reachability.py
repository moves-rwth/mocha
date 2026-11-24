import unittest

from mocha import (
    ReachabilityStep,
    TransitionSystem,
    compute_reachable_states,
    reduce_to_reachable,
    trace_reachability,
)


class ReachabilityTests(unittest.TestCase):
    def test_returns_immutable_set_from_all_initial_states(self) -> None:
        system = TransitionSystem.from_components(
            states={"start", "cycle", "terminal", "isolated", "unreachable"},
            actions={"a", "b"},
            transitions={
                ("start", "a", "cycle"),
                ("cycle", "a", "start"),
                ("cycle", "b", "terminal"),
                ("unreachable", "a", "start"),
            },
            initial_states={"start", "isolated"},
        )
        states_before = system.states
        transitions_before = set(system.transitions())

        reachable = compute_reachable_states(transition_system=system)

        self.assertIsInstance(reachable, frozenset)
        self.assertEqual(reachable, {"start", "cycle", "terminal", "isolated"})
        self.assertEqual(reachable & system.terminal_states, {"terminal", "isolated"})
        self.assertEqual(system.states, states_before)
        self.assertEqual(set(system.transitions()), transitions_before)
        system.add_state("later", initial=True)
        self.assertNotIn("later", reachable)

    def test_trace_matches_callback_snapshots_and_direct_set(self) -> None:
        system = TransitionSystem.from_edges(
            states={0, 1, 2, 99}, edges={(0, 1), (1, 2), (2, 1)},
            action="step", initial_states={0},
        )
        snapshots: list[ReachabilityStep[int]] = []

        reachable = compute_reachable_states(system, on_step=snapshots.append)
        trace = trace_reachability(transition_system=system)

        self.assertIsInstance(trace.result, frozenset)
        self.assertEqual(trace.result, reachable)
        self.assertEqual(trace.steps, tuple(snapshots))
        self.assertEqual(trace.steps, (
            ReachabilityStep(0, frozenset({0})),
            ReachabilityStep(1, frozenset({0, 1})),
            ReachabilityStep(2, frozenset({0, 1, 2})),
        ))
        self.assertEqual(trace.steps[-1].reachable_states, trace.result)

    def test_no_initial_states_returns_empty_set_and_initial_snapshot(self) -> None:
        for states in (set(), {0, 1}):
            with self.subTest(states=states):
                system = TransitionSystem.from_edges(
                    states=states, edges={(state, state) for state in states},
                    action="step",
                )

                self.assertEqual(compute_reachable_states(system), frozenset())
                trace = trace_reachability(system)
                self.assertIsInstance(trace.result, frozenset)
                self.assertEqual(trace.result, frozenset())
                self.assertEqual(trace.steps, (ReachabilityStep(0, frozenset()),))


class ReachableReductionTests(unittest.TestCase):
    def test_keeps_exactly_the_fragment_reachable_from_all_initial_states(self) -> None:
        system = TransitionSystem.from_components(
            states={"start", "cycle", "deadlock", "isolated", "unreachable"},
            actions={"a", "unused"},
            transitions={
                ("start", "a", "cycle"),
                ("cycle", "a", "start"),
                ("cycle", "a", "deadlock"),
                ("unreachable", "a", "start"),
                ("unreachable", "a", "unreachable"),
            },
            initial_states={"start", "isolated"},
            atomic_propositions={"safe", "error", "unused"},
            labels={"start": {"safe"}, "unreachable": {"error"}},
        )

        reduced = reduce_to_reachable(transition_system=system)

        self.assertEqual(reduced.states, frozenset({"start", "cycle", "deadlock", "isolated"}))
        self.assertEqual(reduced.initial_states, system.initial_states)
        self.assertEqual(set(reduced.transitions()), {
            ("start", "a", "cycle"),
            ("cycle", "a", "start"),
            ("cycle", "a", "deadlock"),
        })
        self.assertEqual(reduced.actions, system.actions)
        self.assertEqual(reduced.atomic_propositions, system.atomic_propositions)
        for state in reduced.states:
            self.assertEqual(reduced.labels(state), system.labels(state))
        self.assertIn("unreachable", system.states)
        self.assertTrue(system.has_transition("unreachable", "a", "start"))

    def test_no_initial_states_yields_an_empty_fragment(self) -> None:
        for states in (set(), {"unreachable"}):
            with self.subTest(states=states):
                system = TransitionSystem.from_components(
                    states=states,
                    actions={"a"},
                    transitions={(state, "a", state) for state in states},
                    atomic_propositions={"p"},
                )

                reduced = reduce_to_reachable(system)

                self.assertEqual(reduced.states, frozenset())
                self.assertEqual(reduced.initial_states, frozenset())
                self.assertEqual(set(reduced.transitions()), set())
                self.assertEqual(reduced.actions, system.actions)
                self.assertEqual(reduced.atomic_propositions, system.atomic_propositions)
                self.assertEqual(system.states, frozenset(states))

    def test_fully_reachable_system_still_returns_an_independent_copy(self) -> None:
        system = TransitionSystem.from_edges(
            states={0, 1}, edges={(0, 1), (1, 1)}, action="a", initial_states={0},
        )

        reduced = reduce_to_reachable(system)

        self.assertIsNot(reduced, system)
        self.assertEqual(reduced.states, system.states)
        self.assertEqual(set(reduced.transitions()), set(system.transitions()))
        reduced.remove_state(1)
        self.assertIn(1, system.states)
        self.assertTrue(system.has_transition(0, "a", 1))


if __name__ == "__main__":
    unittest.main()
