from graphviz import Digraph

from mocha.algorithms.invariance import InvariantStep, InvariantResult
from mocha.models.transition_system import TransitionSystem
from mocha.visualisation.transition_system import to_graphviz

def visualise_invariant_step(
        ts: TransitionSystem[str, str, str],
        step: InvariantStep[str],
) -> Digraph:
    return to_graphviz(
        ts,
        highlighted_states=step.visited,
        current_state=step.current_state,
    )


def visualise_invariant_result(
        ts: TransitionSystem[str, str, str],
        result: InvariantResult[str],
) -> Digraph:
    if result.counterexample is None:
        return to_graphviz(ts)

    counterexample_states = set(result.counterexample)

    path_edges = set(
        zip(
            result.counterexample,
            result.counterexample[1:],
        )
    )

    counterexample_transitions = {
        transition
        for transition in ts.transitions()
        if (
               transition.source,
               transition.target,
           ) in path_edges
    }

    return to_graphviz(
        ts,
        highlighted_states=counterexample_states,
        highlighted_transitions=counterexample_transitions,
        current_state=result.counterexample[-1],
    )
