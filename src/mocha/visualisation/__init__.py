"""Graphviz visualisation helpers for transition systems."""

from typing import Any

from .overlay import TransitionSystemOverlay

__all__ = [
    "TransitionSystemOverlay",
    "to_graphviz",
    "visualise_reachability_step",
    "visualise_step",
]


def __getattr__(name: str) -> Any:
    """Load Graphviz-dependent rendering helpers only when they are requested."""
    if name in {"to_graphviz", "visualise_step"}:
        from .transition_system import to_graphviz, visualise_step

        return {"to_graphviz": to_graphviz, "visualise_step": visualise_step}[name]
    if name == "visualise_reachability_step":
        from .reachability import visualise_reachability_step

        return visualise_reachability_step
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
