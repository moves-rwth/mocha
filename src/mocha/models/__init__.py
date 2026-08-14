"""Domain models used by the Model Checking Assistant."""

from .transition_system import (
    Action,
    AtomicProposition,
    State,
    Transition,
    TransitionSystem,
)

__all__ = [
    "Action",
    "AtomicProposition",
    "State",
    "Transition",
    "TransitionSystem",
]
