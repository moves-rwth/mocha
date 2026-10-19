import unittest

from mocha.models import Automaton, FiniteAutomaton, GNBA, NBA


class AutomatonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.automaton: Automaton[str, str] = Automaton()
        self.automaton.add_state("q0", initial=True)
        self.automaton.add_state("q1")
        self.automaton.add_state("q2")

    def test_constructor_creates_empty_components(self) -> None:
        automaton: Automaton[str, str] = Automaton()

        self.assertEqual(automaton.states, frozenset())
        self.assertEqual(automaton.alphabet, frozenset())
        self.assertEqual(automaton.initial_states, frozenset())
        self.assertEqual(set(automaton.transitions()), set())
        self.assertTrue(automaton.is_deterministic)

    def test_add_transition_uses_registered_symbols_and_updates_queries(self) -> None:
        self.automaton.add_symbol("a")
        self.automaton.add_symbol("b")
        self.automaton.add_transition("q0", "a", "q1")
        self.automaton.add_transition("q0", "b", "q2")
        self.automaton.add_transition("q2", "a", "q1")

        self.assertEqual(self.automaton.alphabet, frozenset({"a", "b"}))
        self.assertEqual(self.automaton.post("q0"), frozenset({"q1", "q2"}))
        self.assertEqual(self.automaton.post("q0", "a"), frozenset({"q1"}))
        self.assertEqual(self.automaton.pre("q1"), frozenset({"q0", "q2"}))
        self.assertEqual(self.automaton.pre("q1", "a"), frozenset({"q0", "q2"}))
        self.assertTrue(self.automaton.has_transition("q0", "a", "q1"))

    def test_add_transition_rejects_unregistered_symbols_without_mutation(self) -> None:
        for automaton_type in (Automaton, FiniteAutomaton, NBA, GNBA):
            with self.subTest(automaton_type=automaton_type):
                automaton = automaton_type.from_components(
                    states={"q0", "q1"},
                    alphabet={"a"},
                    transitions={("q0", "a", "q1")},
                )
                transitions = set(automaton.transitions())

                with self.assertRaisesRegex(ValueError, "Unknown alphabet symbol 'b'"):
                    automaton.add_transition("q1", "b", "q0")

                self.assertEqual(automaton.alphabet, frozenset({"a"}))
                self.assertEqual(set(automaton.transitions()), transitions)

                automaton.add_symbol("b")
                automaton.add_transition("q1", "b", "q0")
                self.assertTrue(automaton.has_transition("q1", "b", "q0"))

    def test_initial_membership_can_be_changed(self) -> None:
        self.automaton.set_initial("q0", initial=False)
        self.automaton.set_initial("q2")

        self.assertEqual(self.automaton.initial_states, frozenset({"q2"}))

    def test_is_deterministic_identifies_nondeterminism_and_initial_choices(self) -> None:
        self.automaton.add_symbol("a")
        self.automaton.add_transition("q0", "a", "q1")
        self.assertTrue(self.automaton.is_deterministic)

        self.automaton.add_transition("q0", "a", "q2")
        self.assertFalse(self.automaton.is_deterministic)

        self.automaton.remove_transition("q0", "a", "q2")
        self.automaton.set_initial("q2")
        self.assertFalse(self.automaton.is_deterministic)

    def test_is_complete_with_no_state_symbol_pairs(self) -> None:
        for states, alphabet in ((set(), set()), ({"q0"}, set()), (set(), {"a"})):
            with self.subTest(states=states, alphabet=alphabet):
                automaton = Automaton.from_components(
                    states=states, alphabet=alphabet, transitions=set(),
                )
                self.assertTrue(automaton.is_complete)

    def test_is_complete_checks_unreachable_states_and_every_symbol(self) -> None:
        automaton = Automaton.from_components(
            states={"q0", "unreachable"},
            alphabet={"a", "b"},
            transitions={
                ("q0", "a", "q0"),
                ("q0", "b", "q0"),
                ("unreachable", "a", "unreachable"),
            },
            initial_states={"q0"},
        )

        self.assertFalse(automaton.is_complete)
        automaton.add_transition("unreachable", "b", "unreachable")
        self.assertTrue(automaton.is_complete)

    def test_is_complete_allows_nondeterminism_and_multiple_initial_states(self) -> None:
        for automaton_type in (Automaton, FiniteAutomaton, NBA, GNBA):
            with self.subTest(automaton_type=automaton_type):
                automaton = automaton_type.from_components(
                    states={"q0", "q1"},
                    alphabet={"a"},
                    transitions={
                        ("q0", "a", "q0"),
                        ("q0", "a", "q1"),
                        ("q1", "a", "q1"),
                    },
                    initial_states={"q0", "q1"},
                )

                self.assertTrue(automaton.is_complete)
                self.assertFalse(automaton.is_deterministic)

    def test_is_complete_reflects_mutations(self) -> None:
        automaton = Automaton.from_components(
            states={"q0"}, alphabet={"a"}, transitions={("q0", "a", "q0")},
        )
        self.assertTrue(automaton.is_complete)

        automaton.add_symbol("b")
        self.assertFalse(automaton.is_complete)
        automaton.add_transition("q0", "b", "q0")
        self.assertTrue(automaton.is_complete)

        automaton.add_state("q1")
        self.assertFalse(automaton.is_complete)
        automaton.add_transition("q1", "a", "q1")
        automaton.add_transition("q1", "b", "q1")
        self.assertTrue(automaton.is_complete)

        automaton.remove_transition("q1", "a", "q1")
        self.assertFalse(automaton.is_complete)
        automaton.remove_symbol("a")
        self.assertTrue(automaton.is_complete)

    def test_remove_state_and_symbol_remove_incident_transitions(self) -> None:
        self.automaton.add_symbol("a")
        self.automaton.add_symbol("b")
        self.automaton.add_transition("q0", "a", "q1")
        self.automaton.add_transition("q2", "a", "q1")
        self.automaton.add_transition("q0", "b", "q2")

        self.automaton.remove_state("q1")

        self.assertFalse(self.automaton.has_transition("q0", "a", "q1"))
        self.assertEqual(self.automaton.post("q2"), frozenset())
        self.assertIn("a", self.automaton.alphabet)

        self.automaton.remove_symbol("b")
        self.assertNotIn("b", self.automaton.alphabet)
        self.assertEqual(self.automaton.post("q0"), frozenset())

    def test_from_components_validates_cross_references(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown initial states"):
            Automaton.from_components(
                states={"q0"},
                alphabet=set(),
                transitions=set(),
                initial_states={"missing"},
            )

        with self.assertRaisesRegex(ValueError, "Unknown transition symbol"):
            Automaton.from_components(
                states={"q0", "q1"},
                alphabet={"a"},
                transitions={("q0", "b", "q1")},
            )

        with self.assertRaisesRegex(ValueError, "None cannot be used"):
            Automaton.from_components(
                states={"q0"},
                alphabet={None},
                transitions=set(),
            )


class FiniteAutomatonTests(unittest.TestCase):
    def test_empty_acceptance_condition_rejects_every_word(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0"},
            alphabet={"a"},
            transitions={("q0", "a", "q0")},
            initial_states={"q0"},
            accepting_states=set(),
        )

        self.assertEqual(automaton.accepting_states, frozenset())
        for word in ((), ("a",), ("a", "a")):
            with self.subTest(word=word):
                self.assertFalse(automaton.accepts(word))

    def test_accepting_membership_can_be_changed(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0", "q1"},
            alphabet=set(),
            transitions=set(),
            accepting_states={"q0"},
        )

        automaton.set_accepting("q0", accepting=False)
        automaton.set_accepting("q1")

        self.assertEqual(automaton.accepting_states, frozenset({"q1"}))

    def test_accepts_words_nondeterministically(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0", "q1", "q2"},
            alphabet={"a", "b"},
            transitions={
                ("q0", "a", "q0"),
                ("q0", "a", "q1"),
                ("q1", "b", "q2"),
            },
            initial_states={"q0"},
            accepting_states={"q2"},
        )

        self.assertTrue(automaton.accepts(("a", "b")))
        self.assertTrue(automaton.accepts(("a", "a", "b")))
        self.assertFalse(automaton.accepts(()))
        self.assertFalse(automaton.accepts(("a",)))
        self.assertFalse(automaton.accepts(("c",)))

    def test_empty_word_is_accepted_when_an_initial_state_is_accepting(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0"},
            alphabet=set(),
            transitions=set(),
            initial_states={"q0"},
            accepting_states={"q0"},
        )

        self.assertTrue(automaton.accepts(()))


class NbaTests(unittest.TestCase):
    def test_allows_empty_acceptance_condition(self) -> None:
        automaton = NBA.from_components(
            states={"q0"},
            alphabet={"a"},
            transitions={("q0", "a", "q0")},
            initial_states={"q0"},
            accepting_states=set(),
        )

        self.assertEqual(automaton.accepting_states, frozenset())
        self.assertTrue(automaton.has_transition("q0", "a", "q0"))

        automaton.set_accepting("q0")
        automaton.set_accepting("q0", accepting=False)
        self.assertEqual(automaton.accepting_states, frozenset())

    def test_represents_state_based_buchi_acceptance(self) -> None:
        automaton = NBA.from_components(
            states={"q0", "q1"},
            alphabet={"a", "b"},
            transitions={
                ("q0", "a", "q1"),
                ("q1", "b", "q1"),
            },
            initial_states={"q0"},
            accepting_states={"q1"},
        )

        self.assertEqual(automaton.initial_states, frozenset({"q0"}))
        self.assertEqual(automaton.accepting_states, frozenset({"q1"}))
        self.assertTrue(automaton.has_transition("q1", "b", "q1"))


class GnbaTests(unittest.TestCase):
    def test_represents_multiple_acceptance_sets(self) -> None:
        automaton = GNBA.from_components(
            states={"q0", "q1", "q2"},
            alphabet={"a"},
            transitions={
                ("q0", "a", "q1"),
                ("q1", "a", "q2"),
            },
            initial_states={"q0"},
            accepting_sets=({"q1"}, {"q1", "q2"}),
        )

        self.assertEqual(
            automaton.accepting_sets,
            frozenset({frozenset({"q1"}), frozenset({"q1", "q2"})}),
        )

    def test_validates_and_updates_acceptance_sets(self) -> None:
        automaton: GNBA[str, str] = GNBA()
        automaton.add_state("q0")
        automaton.add_state("q1")
        automaton.add_accepting_set({"q0", "q1"})

        with self.assertRaisesRegex(ValueError, "Unknown accepting states"):
            automaton.add_accepting_set({"missing"})

        automaton.remove_state("q1")
        self.assertEqual(automaton.accepting_sets, frozenset({frozenset({"q0"})}))

        automaton.remove_accepting_set({"q0"})
        self.assertEqual(automaton.accepting_sets, frozenset())


if __name__ == "__main__":
    unittest.main()
