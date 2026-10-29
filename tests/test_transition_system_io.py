import unittest

from jsonschema import ValidationError

from mocha.io import to_dict
from mocha.io.transition_system import from_dict, validate_dict
from mocha.models import TransitionSystem


class TransitionSystemIoTests(unittest.TestCase):
    def test_dict_round_trip(self) -> None:
        original = TransitionSystem.from_components(
            states={"s0", "s1"},
            actions={"a"},
            transitions={
                ("s0", "a", "s1"),
                ("s1", "a", "s1"),
            },
            initial_states={"s0"},
            atomic_propositions={"p", "q"},
            labels={
                "s0": {"p"},
                "s1": {"q"},
            },
        )

        restored = from_dict(to_dict(transition_system=original))

        self.assertEqual(restored.states, original.states)
        self.assertEqual(restored.actions, original.actions)
        self.assertEqual(restored.initial_states, original.initial_states)
        self.assertEqual(
            restored.atomic_propositions,
            original.atomic_propositions,
        )
        self.assertEqual(set(restored.transitions()), set(original.transitions()))
        for state in original.states:
            self.assertEqual(restored.labels(state), original.labels(state))

    def test_to_dict_matches_schema(self) -> None:
        system = TransitionSystem.from_edges(
            states=("idle", "running"),
            edges=(("idle", "running"),),
            action="start",
            initial_states=("idle",),
        )

        self.assertIsNone(validate_dict(to_dict(system)))

    def test_to_dict_serializes_every_component_in_a_stable_order(self) -> None:
        system = TransitionSystem.from_components(
            states=("running", "idle", "done"),
            actions=("finish", "start", "reset"),
            transitions=(
                ("running", "finish", "done"),
                ("idle", "start", "running"),
            ),
            initial_states=("idle",),
            atomic_propositions=("finished", "busy", "ready", "error"),
            labels={
                "running": ("busy",),
                "idle": ("ready",),
                "done": ("finished",),
            },
        )

        data = to_dict(system)

        self.assertEqual(
            data,
            {
                "schema_version": 1,
                "kind": "transition_system",
                "states": ["done", "idle", "running"],
                "actions": ["finish", "reset", "start"],
                "initial_states": ["idle"],
                "atomic_propositions": ["busy", "error", "finished", "ready"],
                "labels": {
                    "done": ["finished"],
                    "idle": ["ready"],
                    "running": ["busy"],
                },
                "transitions": [
                    ["idle", "start", "running"],
                    ["running", "finish", "done"],
                ],
            },
        )
        validate_dict(data)

    def test_to_dict_includes_empty_labels_and_collections(self) -> None:
        system = TransitionSystem.from_components(
            states=("idle",),
            actions=(),
            transitions=(),
        )

        self.assertEqual(
            to_dict(system),
            {
                "schema_version": 1,
                "kind": "transition_system",
                "states": ["idle"],
                "actions": [],
                "initial_states": [],
                "atomic_propositions": [],
                "labels": {"idle": []},
                "transitions": [],
            },
        )

    def test_validate_dict_rejects_invalid_schema_data(self) -> None:
        valid_data = {
            "schema_version": 1,
            "kind": "transition_system",
            "states": ["idle"],
            "actions": [],
            "initial_states": [],
            "atomic_propositions": [],
            "labels": {"idle": []},
            "transitions": [],
        }

        invalid_payloads = (
            {key: value for key, value in valid_data.items() if key != "labels"},
            {**valid_data, "schema_version": 2},
            {**valid_data, "states": ["idle", "idle"]},
            {**valid_data, "transitions": [["idle", "start"]]},
            {**valid_data, "extra": True},
        )

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                validate_dict(payload)


if __name__ == "__main__":
    unittest.main()
