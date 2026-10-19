import unittest

from mocha.algorithms import gnba_to_nba, transition_system_automaton_product
from mocha.models import FiniteAutomaton, GNBA, NBA, TransitionSystem


class GnbaToNbaTests(unittest.TestCase):
    def test_uses_a_round_robin_counter_for_every_acceptance_set(self) -> None:
        gnba = GNBA.from_components(
            states={"q0", "q1"},
            alphabet={"a", "b"},
            transitions={
                ("q0", "a", "q1"),
                ("q1", "b", "q0"),
            },
            initial_states={"q0"},
            accepting_sets=({"q0"}, {"q1"}),
        )

        nba = gnba_to_nba(gnba)

        self.assertEqual(nba.initial_states, frozenset({("q0", 1)}))
        self.assertIn(
            nba.accepting_states,
            {
                frozenset({("q0", 1)}),
                frozenset({("q1", 1)}),
            },
        )
        self.assertEqual(
            set(nba.transitions()),
            {
                (("q0", 1), "a", ("q1", 1)),
                (("q0", 2), "a", ("q1", 1)),
                (("q1", 1), "b", ("q0", 2)),
                (("q1", 2), "b", ("q0", 2)),
            }
            if nba.accepting_states == frozenset({("q1", 1)})
            else {
                (("q0", 1), "a", ("q1", 2)),
                (("q0", 2), "a", ("q1", 2)),
                (("q1", 1), "b", ("q0", 1)),
                (("q1", 2), "b", ("q0", 1)),
            },
        )

    def test_empty_acceptance_family_becomes_an_all_accepting_nba(self) -> None:
        gnba = GNBA.from_components(
            states={"q0", "q1"},
            alphabet={"a"},
            transitions={("q0", "a", "q1")},
            initial_states={"q0"},
        )

        nba = gnba_to_nba(gnba)

        self.assertEqual(nba.accepting_states, frozenset({("q0", 1), ("q1", 1)}))
        self.assertTrue(nba.has_transition(("q0", 1), "a", ("q1", 1)))


class TransitionSystemAutomatonProductTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system = TransitionSystem.from_components(
            states={"s0", "s1"},
            actions={"a"},
            transitions={("s0", "a", "s1")},
            initial_states={"s0"},
            atomic_propositions={"p", "q"},
            labels={
                "s0": {"p"},
                "s1": {"q"},
            },
        )
        self.alphabet = {
            frozenset(),
            frozenset({"p"}),
            frozenset({"q"}),
            frozenset({"p", "q"}),
        }

    def test_constructs_a_finite_automaton_product(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0", "q1"},
            alphabet=self.alphabet,
            transitions={
                ("q0", frozenset({"p"}), "q1"),
                ("q1", frozenset({"q"}), "q0"),
            },
            initial_states={"q0"},
            accepting_states={"q1"},
        )

        product = transition_system_automaton_product(self.system, automaton)

        self.assertEqual(
            product.states,
            frozenset({
                ("s0", "q0"),
                ("s0", "q1"),
                ("s1", "q0"),
                ("s1", "q1"),
            }),
        )
        self.assertEqual(
            product.initial_states,
            frozenset({("s0", "q1")}),
        )
        self.assertTrue(
            product.has_transition(
                ("s0", "q1"),
                "a",
                ("s1", "q0"),
            )
        )
        self.assertEqual(
            product.labels(("s1", "q0")),
            frozenset({"q0"}),
        )
        self.assertEqual(product.atomic_propositions, frozenset({"q0", "q1"}))
        self.assertEqual(
            frozenset(
                state
                for state in product.states
                if state[1] in automaton.accepting_states
            ),
            frozenset({("s0", "q1"), ("s1", "q1")}),
        )

    def test_constructs_an_nba_product(self) -> None:
        automaton = NBA.from_components(
            states={"q0", "q1"},
            alphabet=self.alphabet,
            transitions={("q0", frozenset({"p"}), "q1")},
            initial_states={"q0"},
            accepting_states={"q1"},
        )

        product = transition_system_automaton_product(self.system, automaton)

        self.assertEqual(
            product.initial_states,
            frozenset({("s0", "q1")}),
        )
        self.assertEqual(
            frozenset(
                state
                for state in product.states
                if state[1] in automaton.accepting_states
            ),
            frozenset({("s0", "q1"), ("s1", "q1")}),
        )

    def test_rejects_an_automaton_with_a_non_valuation_alphabet(self) -> None:
        automaton = FiniteAutomaton.from_components(
            states={"q0"},
            alphabet={frozenset(), frozenset({"p"})},
            transitions=set(),
        )

        with self.assertRaisesRegex(ValueError, "alphabet must equal"):
            transition_system_automaton_product(self.system, automaton)


if __name__ == "__main__":
    unittest.main()
