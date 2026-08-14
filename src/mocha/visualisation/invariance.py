from graphviz import Digraph

from mocha.algorithms.invariance import InvariantStep
from mocha.models.transition_system import TransitionSystem
from mocha.visualisation.transition_system import to_graphviz


def visualise_invariant_step(
        ts: TransitionSystem[str, str, str],
        step: InvariantStep[str],
) -> Digraph:
    return to_graphviz(
        ts,
        highlighted_states=step.visited,
    )
