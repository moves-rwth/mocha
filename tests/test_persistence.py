import unittest

from mocha.algorithms.persistence import (
    check_persistence,
    cycle_check,
    trace_persistence,
)
from mocha.models import TransitionSystem


class PersistenceTests(unittest.TestCase):
    def test_cycle_check_returns_a_cycle_and_updates_the_shared_visited_set(self) -> None:
        system = TransitionSystem.from_components(
            states={"start", "middle"},
            actions={"step"},
            transitions={
                ("start", "step", "middle"),
                ("middle", "step", "start"),
            },
        )
        visited: set[str] = set()

        cycle = cycle_check(system, "start", visited)

        self.assertEqual(cycle, ("start", "middle", "start"))
        self.assertEqual(visited, {"start", "middle"})

    def test_accepts_when_every_run_eventually_remains_in_proposition_states(self) -> None:
        system = TransitionSystem.from_components(
            states={"initial", "stable"},
            actions={"step"},
            transitions={
                ("initial", "step", "stable"),
                ("stable", "step", "stable"),
            },
            initial_states={"initial"},
            atomic_propositions={"p"},
            labels={
                "initial": set(),
                "stable": {"p"},
            },
        )

        result = check_persistence(system, "p")

        self.assertTrue(result.satisfies)
        self.assertIsNone(result.counterexample)

    def test_returns_a_lasso_for_a_reachable_cycle_with_a_violating_state(self) -> None:
        system = TransitionSystem.from_components(
            states={"initial", "bad", "good"},
            actions={"step"},
            transitions={
                ("initial", "step", "bad"),
                ("bad", "step", "good"),
                ("good", "step", "bad"),
            },
            initial_states={"initial"},
            atomic_propositions={"p"},
            labels={
                "initial": {"p"},
                "bad": set(),
                "good": {"p"},
            },
        )

        result = check_persistence(system, "p")

        self.assertFalse(result.satisfies)
        self.assertEqual(result.counterexample, ("initial", "bad", "good", "bad"))

    def test_trace_records_the_outer_and_inner_dfs_configurations(self) -> None:
        system = TransitionSystem.from_components(
            states={"initial", "bad"},
            actions={"step"},
            transitions={
                ("initial", "step", "bad"),
                ("bad", "step", "bad"),
            },
            initial_states={"initial"},
            atomic_propositions={"p"},
            labels={
                "initial": {"p"},
                "bad": set(),
            },
        )

        trace = trace_persistence(system, "p")

        self.assertFalse(trace.result.satisfies)
        self.assertEqual(
            tuple(step.operation for step in trace.steps),
            (
                "initialize",
                "outer_push",
                "outer_push",
                "outer_pop",
                "inner_push",
                "cycle_found",
            ),
        )
        self.assertEqual(trace.steps[0].outer_visited, frozenset())
        self.assertEqual(trace.steps[0].outer_stack, ())
        self.assertEqual(trace.steps[4].inner_visited, frozenset({"bad"}))
        self.assertEqual(trace.steps[4].inner_stack, ("bad",))

    def test_rejects_terminal_transition_systems_and_unknown_propositions(self) -> None:
        terminal_system = TransitionSystem.from_components(
            states={"terminal"},
            actions=set(),
            transitions=set(),
            initial_states={"terminal"},
            atomic_propositions={"p"},
            labels={"terminal": {"p"}},
        )
        non_blocking_system = TransitionSystem.from_components(
            states={"loop"},
            actions={"step"},
            transitions={("loop", "step", "loop")},
            initial_states={"loop"},
            atomic_propositions={"p"},
            labels={"loop": {"p"}},
        )

        with self.assertRaisesRegex(ValueError, "without terminal states"):
            check_persistence(terminal_system, "p")
        with self.assertRaisesRegex(ValueError, "Unknown atomic proposition"):
            check_persistence(non_blocking_system, "missing")


if __name__ == "__main__":
    unittest.main()
