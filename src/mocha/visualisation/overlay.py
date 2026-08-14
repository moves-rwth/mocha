"""Data used to annotate a transition-system visualization."""

from dataclasses import dataclass
from typing import Generic

from mocha.models.transition_system import Action, State, Transition


@dataclass(frozen=True)
class TransitionSystemOverlay(Generic[State, Action]):
    """States and transitions to emphasize in a rendered transition system."""

    highlighted_states: frozenset[State] = frozenset()
    highlighted_transitions: frozenset[Transition[State, Action]] = frozenset()
    description: str | None = None

__all__ = ["TransitionSystemOverlay"]
