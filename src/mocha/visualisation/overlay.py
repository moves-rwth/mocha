"""Data used to annotate a transition-system visualization."""

from dataclasses import dataclass
from typing import Generic

from mocha.models.transition_system import Action, State, Transition


@dataclass(frozen=True)
class TransitionSystemOverlay(Generic[State, Action]):
    """Selections and optional text used to annotate a rendered system.

    Attributes:
        highlighted_states: States rendered with a thicker outline.
        highlighted_transitions: Transitions rendered with a thicker edge.
        description: Optional caller-provided explanation of the overlay.
    """

    highlighted_states: frozenset[State] = frozenset()
    highlighted_transitions: frozenset[Transition[State, Action]] = frozenset()
    description: str | None = None


__all__ = ["TransitionSystemOverlay"]
