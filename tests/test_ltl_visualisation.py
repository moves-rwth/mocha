"""Check that persistence visualisation preserves an LTL counterexample's loop.

The product lasso is displayed with original-state labels while retaining the
search result's positions and closing edge.
"""

import unittest

from mocha import TransitionSystem, check_ltl
from mocha.io import parse_ltl
from mocha.visualisation import visualise_persistence_counterexample


def system():
    """Build a two-state system with parallel actions and a p-free self-loop."""
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


class LTLVisualisationTests(unittest.TestCase):
    def test_ltl_pipeline_projects_persistence_lasso(self):
        ts = system()
        result = check_ltl(ts, parse_ltl('G"p"'))
        self.assertFalse(result.satisfies)
        self.assertEqual(
            result.counterexample,
            tuple(state for state, _ in result.emptiness.counterexample),
        )
        self.assertEqual(result.loop_start, result.emptiness.loop_start)

        graph = visualise_persistence_counterexample(
            result.search_product,
            result.emptiness,
            format_state=lambda product_state: product_state[0],
            format_proposition=lambda _: "label",
        )
        self.assertIn('Persistence counterexample', graph.source)
        self.assertIn(
            f"step_{len(result.emptiness.counterexample) - 2} -> step_{result.loop_start}",
            graph.source,
        )


if __name__ == "__main__":
    unittest.main()
