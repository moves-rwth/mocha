"""Graphviz visualisation helpers for transition systems."""

from typing import Any

from .overlay import TransitionSystemOverlay

__all__ = [
    "TransitionSystemOverlay",
    "to_graphviz",
    "to_lasso_graphviz",
    "visualise_invariant_step",
    "visualise_invariant_result",
    "visualise_persistence_counterexample",
    "visualise_reachability_step",
    "visualise_step",
]


def __getattr__(name: str) -> Any:
    """Load Graphviz-dependent rendering helpers only when they are requested."""
    if name in {"to_graphviz", "to_lasso_graphviz", "visualise_step"}:
        from .transition_system import to_graphviz, to_lasso_graphviz, visualise_step

        return {
            "to_graphviz": to_graphviz,
            "to_lasso_graphviz": to_lasso_graphviz,
            "visualise_step": visualise_step,
        }[name]
    if name == "visualise_persistence_counterexample":
        from .persistence import visualise_persistence_counterexample

        return visualise_persistence_counterexample
    if name == "visualise_reachability_step":
        from .reachability import visualise_reachability_step

        return visualise_reachability_step
    if name == "visualise_invariant_step":
        from .invariance import visualise_invariant_step

        return visualise_invariant_step
    if name == "visualise_invariant_result":
        from .invariance import visualise_invariant_result

        return visualise_invariant_result
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
