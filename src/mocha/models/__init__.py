"""Domain models used by the Model Checking Assistant."""

from .automaton import (
    Automaton,
    AutomatonState,
    AutomatonTransition,
    FiniteAutomaton,
    GNBA,
    GeneralizedNondeterministicBuchiAutomaton,
    NBA,
    NondeterministicBuchiAutomaton,
    Symbol,
)
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
    "Automaton",
    "AutomatonState",
    "AutomatonTransition",
    "FiniteAutomaton",
    "GNBA",
    "GeneralizedNondeterministicBuchiAutomaton",
    "NBA",
    "NondeterministicBuchiAutomaton",
    "State",
    "Symbol",
    "Transition",
    "TransitionSystem",
]
