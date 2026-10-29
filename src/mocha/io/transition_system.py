"""Read, write, and validate versioned JSON transition-system documents.

The document format represents string-valued transition systems with
the keys ``states``, ``actions``, ``initial_states``, ``atomic_propositions``,
``labels``, and ``transitions``. Its JSON Schema validates document structure;
the model constructor additionally validates cross-references such as a
transition endpoint being a declared state.
"""

import json
from pathlib import Path
from typing import Any, cast
from importlib.resources import files

from jsonschema import Draft202012Validator

from mocha.models.transition_system import TransitionSystem

_SCHEMA_PATH = (
        files("mocha.io.schemas")
        / "transition-system.schema.json"
)

with _SCHEMA_PATH.open(encoding="utf-8") as file:
    _SCHEMA = json.load(file)

Draft202012Validator.check_schema(_SCHEMA)

_VALIDATOR = Draft202012Validator(_SCHEMA)


__all__ = [
    "from_dict",
    "load_transition_system",
    "save_transition_system",
    "to_dict",
    "validate_dict",
]


def validate_dict(data: object) -> None:
    """Validate a decoded JSON document against the schema.

    Raises :class:`jsonschema.ValidationError` when the document has an
    unsupported version, an invalid shape, or invalid value types. This checks
    structural constraints only; use :func:`from_dict` to also construct and
    validate a transition system's component relationships.
    """
    _VALIDATOR.validate(data)


def to_dict(
        transition_system: TransitionSystem[str, str, str],
) -> dict[str, object]:
    """Convert a string-valued transition system to a JSON-compatible dict.

    Collections are sorted so identical systems produce deterministic output.
    The returned document conforms to the version-1 transition-system schema.
    """
    return {
        "schema_version": 1,
        "kind": "transition_system",
        "states": sorted(transition_system.states),
        "actions": sorted(transition_system.actions),
        "initial_states": sorted(transition_system.initial_states),
        "atomic_propositions": sorted(transition_system.atomic_propositions),
        "labels": {
            state: sorted(transition_system.labels(state))
            for state in sorted(transition_system.states)
        },
        "transitions": [
            [source, action, target]
            for source, action, target in sorted(transition_system.transitions())
        ],
    }


def from_dict(
        data: object,
) -> TransitionSystem[str, str, str]:
    """Construct a transition system from a validated JSON-compatible dict.

    The document is first checked against the JSON Schema, then passed to the
    strict :meth:`TransitionSystem.from_components` constructor. Consequently,
    malformed document structure raises ``ValidationError`` and invalid model
    cross-references raise ``ValueError``.
    """
    validate_dict(data)

    obj = cast(dict[str, Any], data)

    transitions = [
        tuple(transition)
        for transition in obj["transitions"]
    ]

    return TransitionSystem.from_components(
        states=obj["states"],
        actions=obj["actions"],
        transitions=transitions,
        initial_states=obj["initial_states"],
        atomic_propositions=obj["atomic_propositions"],
        labels=obj["labels"],
    )

def save_transition_system(
        transition_system: TransitionSystem[str, str, str],
        path: str | Path,
) -> None:
    """Write ``transition_system`` as UTF-8, indented JSON to ``path``.

    Existing files at ``path`` are replaced. The output ends in a newline and
    uses deterministic ordering supplied by :func:`to_dict`.
    """
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(
            to_dict(transition_system),
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")


def load_transition_system(
        path: str | Path,
) -> TransitionSystem[str, str, str]:
    """Load a UTF-8 JSON transition-system document from ``path``.

    JSON parsing errors propagate as ``JSONDecodeError``; schema and model
    validation errors propagate from :func:`from_dict`.
    """
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)

    return from_dict(data)
