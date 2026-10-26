import unittest

from mocha.models import TransitionSystem


class TransitionSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.system: TransitionSystem[str, str, str] = TransitionSystem()
        self.system.add_state("idle", initial=True, labels=("ready",))
        self.system.add_state("running", labels=("busy",))
        self.system.add_state("done")

    def test_constructor_creates_an_empty_transition_system(self) -> None:
        system: TransitionSystem[str, str, str] = TransitionSystem()

        self.assertEqual(system.states, frozenset())
        self.assertEqual(system.actions, frozenset())
        self.assertEqual(system.initial_states, frozenset())
        self.assertEqual(system.atomic_propositions, frozenset())
        self.assertEqual(set(system.transitions()), set())
        self.assertTrue(system.is_non_blocking())

    def test_from_components_constructs_every_component(self) -> None:
        system = TransitionSystem.from_components(
            states=("idle", "running", "done"),
            actions=("start", "finish", "reset"),
            transitions=(
                ("idle", "start", "running"),
                ("running", "finish", "done"),
            ),
            initial_states=("idle",),
            atomic_propositions=("ready", "busy", "finished", "error"),
            labels={
                "idle": ("ready",),
                "running": ("busy",),
                "done": ("finished",),
            },
        )

        self.assertEqual(system.states, frozenset({"idle", "running", "done"}))
        self.assertEqual(system.actions, frozenset({"start", "finish", "reset"}))
        self.assertEqual(system.initial_states, frozenset({"idle"}))
        self.assertEqual(
            system.atomic_propositions,
            frozenset({"ready", "busy", "finished", "error"}),
        )
        self.assertEqual(system.labels("running"), frozenset({"busy"}))
        self.assertTrue(system.has_transition("idle", "start", "running"))
        self.assertTrue(system.has_transition("running", "finish", "done"))

    def test_induced_subsystem_restricts_states_transitions_labels_and_initial_states(self) -> None:
        self.system.set_initial("done")
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("running", "wait", "running")
        self.system.add_transition("running", "finish", "done")
        self.system.add_transition("done", "reset", "idle")
        self.system.add_action("unused")
        self.system.add_atomic_proposition("unlabelled")

        subsystem = self.system.induced_subsystem(iter(("idle", "running", "idle")))

        self.assertEqual(subsystem.states, frozenset({"idle", "running"}))
        self.assertEqual(subsystem.initial_states, frozenset({"idle"}))
        self.assertEqual(subsystem.labels("idle"), frozenset({"ready"}))
        self.assertEqual(subsystem.labels("running"), frozenset({"busy"}))
        self.assertEqual(set(subsystem.transitions()), {
            ("idle", "start", "running"),
            ("running", "wait", "running"),
        })
        self.assertEqual(subsystem.actions, self.system.actions)
        self.assertEqual(subsystem.atomic_propositions, self.system.atomic_propositions)

    def test_induced_subsystem_accepts_an_empty_selection(self) -> None:
        self.system.add_transition("idle", "start", "running")

        subsystem = self.system.induced_subsystem(())

        self.assertEqual(subsystem.states, frozenset())
        self.assertEqual(subsystem.initial_states, frozenset())
        self.assertEqual(set(subsystem.transitions()), set())
        self.assertEqual(subsystem.actions, self.system.actions)
        self.assertEqual(subsystem.atomic_propositions, self.system.atomic_propositions)

    def test_induced_subsystem_rejects_unknown_states(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown states.*missing"):
            self.system.induced_subsystem(("idle", "missing"))

    def test_induced_subsystem_is_independent_of_the_original(self) -> None:
        self.system.add_transition("idle", "start", "running")

        subsystem = self.system.induced_subsystem(self.system.states)

        self.assertIsNot(subsystem, self.system)
        self.assertEqual(subsystem.states, self.system.states)
        self.assertEqual(set(subsystem.transitions()), set(self.system.transitions()))
        subsystem.remove_transition("idle", "start", "running")
        subsystem.add_label("idle", "changed")
        subsystem.set_initial("idle", False)
        subsystem.add_action("new")
        subsystem.remove_state("done")

        self.assertTrue(self.system.has_transition("idle", "start", "running"))
        self.assertEqual(self.system.labels("idle"), frozenset({"ready"}))
        self.assertNotIn("changed", self.system.atomic_propositions)
        self.assertEqual(self.system.initial_states, frozenset({"idle"}))
        self.assertNotIn("new", self.system.actions)
        self.assertIn("done", self.system.states)

        self.system.remove_label("running", "busy")
        self.assertEqual(subsystem.labels("running"), frozenset({"busy"}))

    def test_from_components_rejects_unknown_initial_states_actions_and_labels(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown initial states"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=(),
                transitions=(),
                initial_states=("missing",),
            )

        with self.assertRaisesRegex(ValueError, "Labels specified for unknown states"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=(),
                transitions=(),
                labels={"missing": ("ready",)},
            )

        with self.assertRaisesRegex(ValueError, "unknown atomic propositions"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=(),
                transitions=(),
                labels={"idle": ("ready",)},
            )

        with self.assertRaisesRegex(ValueError, "Unknown transition action"):
            TransitionSystem.from_components(
                states=("idle", "done"),
                actions=("start",),
                transitions=(("idle", "finish", "done"),),
            )

        with self.assertRaisesRegex(ValueError, "Unknown transition source"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=("start",),
                transitions=(("missing", "start", "idle"),),
            )

        with self.assertRaisesRegex(ValueError, "Unknown transition target"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=("start",),
                transitions=(("idle", "start", "missing"),),
            )

    def test_from_edges_uses_one_action_for_every_edge(self) -> None:
        system = TransitionSystem.from_edges(
            states=("idle", "running", "done"),
            edges=(("idle", "running"), ("running", "done")),
            action="step",
            initial_states=("idle",),
            atomic_propositions=("finished",),
            labels={"done": ("finished",)},
        )

        self.assertEqual(system.actions, frozenset({"step"}))
        self.assertEqual(system.initial_states, frozenset({"idle"}))
        self.assertTrue(system.has_transition("idle", "step", "running"))
        self.assertTrue(system.has_transition("running", "step", "done"))
        self.assertEqual(system.labels("done"), frozenset({"finished"}))

    def test_add_state_initial_state_and_labels(self) -> None:
        self.assertEqual(self.system.states, frozenset({"idle", "running", "done"}))
        self.assertEqual(self.system.initial_states, frozenset({"idle"}))
        self.assertEqual(self.system.labels("idle"), frozenset({"ready"}))
        self.assertEqual(
            self.system.atomic_propositions,
            frozenset({"ready", "busy"}),
        )

    def test_add_transition_and_post(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")

        self.assertEqual(self.system.actions, frozenset({"start", "skip"}))
        self.assertEqual(self.system.post("idle"), frozenset({"running", "done"}))
        self.assertEqual(self.system.post("idle", "start"), frozenset({"running"}))
        self.assertEqual(self.system.post("idle", "unknown"), frozenset())

    def test_pre_returns_predecessors_with_an_optional_action_filter(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")
        self.system.add_transition("done", "retry", "running")

        self.assertEqual(self.system.pre("running"), frozenset({"idle", "done"}))
        self.assertEqual(self.system.pre("running", "start"), frozenset({"idle"}))
        self.assertEqual(self.system.pre("running", "retry"), frozenset({"done"}))
        self.assertEqual(self.system.pre("running", "unknown"), frozenset())
        self.assertEqual(self.system.pre("idle"), frozenset())

    def test_post_returns_successors_with_an_optional_action_filter(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")
        self.system.add_transition("idle", "restart", "running")

        self.assertEqual(self.system.post("idle"), frozenset({"running", "done"}))
        self.assertEqual(self.system.post("idle", "start"), frozenset({"running"}))
        self.assertEqual(self.system.post("idle", "skip"), frozenset({"done"}))
        self.assertEqual(self.system.post("idle", "unknown"), frozenset())
        self.assertEqual(self.system.post("done"), frozenset())

    def test_transitions_yields_each_distinct_transition(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")
        self.system.add_transition("done", "retry", "running")
        self.system.add_transition("idle", "start", "running")

        self.assertEqual(
            set(self.system.transitions()),
            {
                ("idle", "start", "running"),
                ("idle", "skip", "done"),
                ("done", "retry", "running"),
            },
        )

    def test_has_transition_reports_membership_of_the_relation(self) -> None:
        self.system.add_transition("idle", "start", "running")

        self.assertTrue(self.system.has_transition("idle", "start", "running"))
        self.assertFalse(self.system.has_transition("idle", "start", "done"))
        self.assertFalse(self.system.has_transition("idle", "unknown", "running"))
        self.assertFalse(self.system.has_transition("missing", "start", "running"))

    def test_enabled_actions_returns_only_actions_with_successors(self) -> None:
        self.system.add_action("reset")
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")

        self.assertEqual(self.system.enabled_actions("idle"), frozenset({"start", "skip"}))
        self.assertEqual(self.system.enabled_actions("done"), frozenset())

    def test_remove_transition_updates_relation_and_enabled_actions(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("idle", "skip", "done")

        self.system.remove_transition("idle", "start", "running")

        self.assertFalse(self.system.has_transition("idle", "start", "running"))
        self.assertEqual(self.system.post("idle"), frozenset({"done"}))
        self.assertEqual(self.system.pre("running"), frozenset())
        self.assertEqual(self.system.enabled_actions("idle"), frozenset({"skip"}))
        self.assertIn("start", self.system.actions)

    def test_remove_transition_rejects_unknown_or_missing_transitions(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown source state"):
            self.system.remove_transition("missing", "start", "running")

        with self.assertRaises(ValueError):
            self.system.remove_transition("idle", "start", "missing")

        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.system.remove_transition("idle", "start", "running")

    def test_remove_state_removes_its_labels_and_incident_transitions(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("running", "finish", "done")
        self.system.add_transition("done", "restart", "idle")

        self.system.remove_state("running")

        self.assertEqual(self.system.states, frozenset({"idle", "done"}))
        self.assertEqual(self.system.post("idle"), frozenset())
        self.assertEqual(self.system.pre("done"), frozenset())
        self.assertFalse(self.system.has_transition("idle", "start", "running"))
        self.assertFalse(self.system.has_transition("running", "finish", "done"))
        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.labels("running")

    def test_remove_state_removes_an_initial_state_and_rejects_unknown_states(self) -> None:
        self.system.remove_state("idle")

        self.assertEqual(self.system.initial_states, frozenset())
        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.remove_state("idle")

    def test_remove_action_removes_all_transitions_with_that_action(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("done", "start", "idle")
        self.system.add_transition("idle", "skip", "done")

        self.system.remove_action("start")

        self.assertNotIn("start", self.system.actions)
        self.assertFalse(self.system.has_transition("idle", "start", "running"))
        self.assertFalse(self.system.has_transition("done", "start", "idle"))
        self.assertEqual(self.system.post("idle"), frozenset({"done"}))
        self.assertEqual(self.system.enabled_actions("done"), frozenset())
        self.assertTrue(self.system.has_transition("idle", "skip", "done"))

    def test_remove_action_rejects_an_unknown_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown action"):
            self.system.remove_action("missing")

    def test_add_action_without_a_transition(self) -> None:
        self.system.add_action("reset")
        self.assertEqual(self.system.actions, frozenset({"reset"}))

    def test_none_is_reserved_for_unfiltered_transition_queries(self) -> None:
        with self.assertRaisesRegex(ValueError, "None cannot be used as an action"):
            self.system.add_action(None)

        with self.assertRaisesRegex(ValueError, "None cannot be used as an action"):
            self.system.add_transition("idle", None, "running")

        with self.assertRaisesRegex(ValueError, "None cannot be used as an action"):
            TransitionSystem.from_components(
                states=("idle",),
                actions=(None,),
                transitions=(),
            )

        with self.assertRaisesRegex(ValueError, "None cannot be used as an action"):
            TransitionSystem.from_edges(
                states=("idle",),
                edges=(),
                action=None,
            )

    def test_add_label_and_change_initial_status(self) -> None:
        self.system.add_label("done", "finished")
        self.system.set_initial("idle", initial=False)
        self.system.set_initial("done")

        self.assertEqual(self.system.labels("done"), frozenset({"finished"}))
        self.assertIn("finished", self.system.atomic_propositions)
        self.assertEqual(self.system.initial_states, frozenset({"done"}))

    def test_add_atomic_proposition_without_labelling_a_state(self) -> None:
        self.system.add_atomic_proposition("error")

        self.assertIn("error", self.system.atomic_propositions)
        self.assertEqual(self.system.labels("idle"), frozenset({"ready"}))

    def test_remove_label_does_not_remove_the_atomic_proposition(self) -> None:
        self.system.remove_label("idle", "ready")
        self.system.remove_label("idle", "unknown")

        self.assertEqual(self.system.labels("idle"), frozenset())
        self.assertIn("ready", self.system.atomic_propositions)

    def test_set_labels_replaces_a_state_label_and_adds_propositions(self) -> None:
        self.system.set_labels("running", ("busy", "error"))

        self.assertEqual(self.system.labels("running"), frozenset({"busy", "error"}))
        self.assertIn("error", self.system.atomic_propositions)

    def test_remove_atomic_proposition_removes_it_from_all_labels(self) -> None:
        self.system.add_label("idle", "shared")
        self.system.add_label("running", "shared")
        self.system.add_atomic_proposition("unlabelled")

        self.system.remove_atomic_proposition("shared")

        self.assertNotIn("shared", self.system.atomic_propositions)
        self.assertEqual(self.system.labels("idle"), frozenset({"ready"}))
        self.assertEqual(self.system.labels("running"), frozenset({"busy"}))
        self.assertIn("unlabelled", self.system.atomic_propositions)

    def test_remove_atomic_proposition_rejects_an_unknown_proposition(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown atomic proposition"):
            self.system.remove_atomic_proposition("missing")

    def test_rejects_duplicate_or_unknown_states(self) -> None:
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.system.add_state("idle")

        with self.assertRaisesRegex(ValueError, "Unknown source state"):
            self.system.add_transition("missing", "start", "running")

        with self.assertRaisesRegex(ValueError, "Unknown target state"):
            self.system.add_transition("idle", "start", "missing")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.post("missing")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.pre("missing")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.enabled_actions("missing")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.labels("missing")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.add_label("missing", "ready")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.remove_label("missing", "ready")

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.set_labels("missing", ("ready",))

        with self.assertRaisesRegex(ValueError, "Unknown state"):
            self.system.set_initial("missing")

    def test_terminal_states_exclude_states_with_successors(self) -> None:
        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("running", "finish", "done")

        self.assertEqual(self.system.terminal_states, frozenset({"done"}))

    def test_is_non_blocking_requires_each_state_to_have_a_successor(self) -> None:
        self.assertFalse(self.system.is_non_blocking())

        self.system.add_transition("idle", "start", "running")
        self.system.add_transition("running", "finish", "done")
        self.system.add_transition("done", "restart", "idle")

        self.assertTrue(self.system.is_non_blocking())


if __name__ == "__main__":
    unittest.main()
