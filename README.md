# Model Checking Assistant (MoChA)

[![CI](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml)

MoChA is a small, typed Python library for representing labelled transition
systems and analysing them. 

## Install

MoChA requires Python 3.11 or later. Install the package from a checkout:

```bash
python -m pip install .
```

Install the optional visualisation dependency to use the Graphviz helpers:

```bash
python -m pip install '.[visualization]'
```

Rendering an image also requires the [Graphviz](https://graphviz.org/)
executables to be installed and available on your `PATH`.

## Transition Systems

A labelled transition system is defined as

$$
\mathcal{T} = (S, \mathrm{Act}, \to, I, \mathrm{AP}, L),
$$

where $S$ is the set of states, $\mathrm{Act}$ is the set of actions,
$\to\;\subseteq S \times \mathrm{Act} \times S$ is the transition relation,
$I \subseteq S$ is the set of initial states, $\mathrm{AP}$ is the set of
atomic propositions, and $L : S \to 2^{\mathrm{AP}}$ is the state-labelling
function. `TransitionSystem` is generic, so application code can use any
hashable values for these components. `None` is reserved as the optional action
filter in predecessor and successor queries, and cannot be an action.

Use `from_components` when every component is known up front. This strict
constructor validates that transition endpoints, actions, initial states, and
labels were declared.

```python
from mocha.models import TransitionSystem

system = TransitionSystem.from_components(
    states={"idle", "running", "done"},
    actions={"start", "finish"},
    transitions={
        ("idle", "start", "running"),
        ("running", "finish", "done"),
    },
    initial_states={"idle"},
    atomic_propositions={"ready", "busy", "complete"},
    labels={
        "idle": {"ready"},
        "running": {"busy"},
        "done": {"complete"},
    },
)
```

For a graph whose edges all share one action, use `from_edges`. An empty system
can also be built incrementally with `add_state`, `add_action`,
`add_transition`, and the label methods. The collection properties return
immutable snapshots. Query successors with `post(state, action=None)`,
predecessors with `pre(state, action=None)`, and iterate the relation with
`transitions()`.


## License

MoChA is licensed under the Mozilla Public License 2.0. See
[LICENCE](LICENCE) for the full license text.

## Funding

MoChA is partially funded by RWTH Aachen University as part of the Exploratory Teaching Space project ETS607 "The Model Checking Assistant: A Learning Framework for the Model Checking Course".
