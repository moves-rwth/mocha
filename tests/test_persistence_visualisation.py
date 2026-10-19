import unittest

from mocha import TransitionSystem
from mocha.algorithms.persistence import PersistenceResult, check_persistence
from mocha.visualisation import to_lasso_graphviz, visualise_persistence_counterexample


def system():
    return TransitionSystem.from_components(
        states={"s0", "s1"}, actions={"go", "back", "again"},
        transitions={
            ("s0", "go", "s1"),
            ("s1", "back", "s0"),
            ("s1", "again", "s0"),
            ("s1", "back", "s1"),
        },
        initial_states={"s0"}, atomic_propositions={"p"},
        labels={"s0": {"p"}, "s1": set()},
    )


class PersistenceVisualisationTests(unittest.TestCase):
    def test_repeated_state_positions_and_return_edge(self):
        graph = to_lasso_graphviz(system(), ("s0", "s1", "s0", "s1", "s0"), 2)
        source = graph.source
        self.assertIn('step_0 [label="0: s0"', source)
        loop_entry = next(line for line in source.splitlines() if 'step_2 [label=' in line)
        self.assertIn('label="2: s0"', loop_entry)
        self.assertIn('xlabel="{p}"', loop_entry)
        self.assertIn('peripheries=2', loop_entry)
        self.assertIn('step_3 -> step_2 [label="again, back (repeat)"', source)
        self.assertNotIn('step_4 [', source)

    def test_persistence_counterexample_renders_lasso(self):
        ts = system()
        failing = check_persistence(ts, "p")
        self.assertFalse(failing.satisfies)
        self.assertEqual(failing.counterexample[failing.loop_start], failing.counterexample[-1])
        graph = visualise_persistence_counterexample(ts, failing)
        self.assertIn('Persistence counterexample', graph.source)
        self.assertIn(
            f"step_{len(failing.counterexample) - 2} -> step_{failing.loop_start}",
            graph.source,
        )

    def test_rejects_successful_persistence_result(self):
        ts = system()
        ts.add_label("s1", "p")
        successful = check_persistence(ts, "p")
        self.assertTrue(successful.satisfies)
        self.assertIsNone(successful.loop_start)
        with self.assertRaisesRegex(ValueError, "no counterexample"):
            visualise_persistence_counterexample(ts, successful)

    def test_rejects_invalid_lasso(self):
        ts = system()
        cases = (
            (("s0",), 0),
            (("s0", "s1"), 0),
            (("s0", "s0"), 0),
            (("s1", "s1"), 0),
            (("s0", "missing", "s0"), 0),
            (("s0", "s1", "s0"), 2),
        )
        for path, loop_start in cases:
            with self.subTest(path=path, loop_start=loop_start):
                with self.assertRaises(ValueError):
                    to_lasso_graphviz(ts, path, loop_start)

        with self.assertRaises(ValueError):
            visualise_persistence_counterexample(ts, PersistenceResult(False))


if __name__ == "__main__":
    unittest.main()
