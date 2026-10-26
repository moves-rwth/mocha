import unittest

from mocha import TransitionSystem, reduce_to_reachable


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

        reduced = reduce_to_reachable(system)

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
