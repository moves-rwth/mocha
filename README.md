# Model Checking Assistant (MoChA)

[![CI](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml)

MoChA is a small, typed Python library for representing labelled transition
systems and analysing them. 
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

## Automata

MoChA represents the common automaton structure

$$
\mathcal{A} = (Q, \Sigma, \delta, I, F),
$$

where $Q$ is the finite set of states, $\Sigma$ is the alphabet,
$\delta \subseteq Q \times \Sigma \times Q$ is a nondeterministic transition
relation, $I \subseteq Q$ is the set of initial states, and $F \subseteq Q$ is
the set of accepting states. `Automaton` stores the shared graph components
$(Q, \Sigma, \delta, I)$. `FiniteAutomaton` adds $F$ and accepts a finite word
when at least one run starts in an initial state, consumes the whole word,
and ends in an accepting state. It represents NFAs and their deterministic
instances, which may have missing transitions.

`is_complete` checks that every state has at least one successor for every
alphabet symbol, independently of `is_deterministic`. With no states or no
alphabet symbols, the automaton is complete because there are no pairs to check.

```python
from mocha.models import FiniteAutomaton

automaton = FiniteAutomaton.from_components(
    states={"even", "odd"},
    alphabet={"a"},
    transitions={
        ("even", "a", "odd"),
        ("odd", "a", "even"),
    },
    initial_states={"even"},
    accepting_states={"even"},
)

assert automaton.accepts(())
assert automaton.accepts(("a", "a"))
assert not automaton.accepts(("a",))
```

The generic alphabet can use individual actions, state-label valuations, or
any other hashable symbols except `None`, which is reserved for unfiltered
queries. When building an automaton incrementally, register symbols with
`add_symbol` before calling `add_transition`; both endpoints must also exist.

An `NBA` is a nondeterministic Büchi automaton with the same tuple, but it
accepts an infinite word when one of its infinite runs from an initial state
visits $F$ infinitely often. An empty $F$ is valid for both finite automata
and NBAs and makes their language empty. The class records this state-based
acceptance condition; the corresponding
acceptance and model checking algorithms belong in the algorithms package.

A `GNBA` is a generalized nondeterministic Büchi automaton:

$$
\mathcal{A} = (Q, \Sigma, \delta, I, \mathcal{F}),
$$

where $\mathcal{F} \subseteq 2^Q$ is a finite family of acceptance sets. A run
is accepting when it visits every $F \in \mathcal{F}$ infinitely often. The
model stores this family as `accepting_sets`:

```python
from mocha.models import GNBA

automaton = GNBA.from_components(
    states={"start", "request_seen", "grant_seen"},
    alphabet={"a", "b"},
    transitions={
        ("start", "a", "request_seen"),
        ("start", "b", "start"),
        ("request_seen", "a", "request_seen"),
        ("request_seen", "b", "grant_seen"),
        ("grant_seen", "a", "request_seen"),
        ("grant_seen", "b", "grant_seen"),
    },
    initial_states={"start"},
    accepting_sets=(
        {"request_seen"},
        {"grant_seen"},
    ),
)
```

With an empty acceptance family $\mathcal{F}=\varnothing$, every infinite run
satisfies the acceptance condition. If the family contains the empty set,
no run is accepting. An accepted word must have an infinite run from an
initial state in either case.

`NondeterministicBuchiAutomaton` is provided as a descriptive alias for `NBA`.
`GeneralizedNondeterministicBuchiAutomaton` is the corresponding alias for
`GNBA`. The standard round-robin construction is available as
`mocha.algorithms.gnba_to_nba`; it converts a GNBA into an equivalent NBA while
preserving the represented infinite-word language.

## Transition-System–Automaton Products

`mocha.algorithms.transition_system_automaton_product` constructs the formal
product of a transition system and a `FiniteAutomaton` or `NBA` over
$2^{\mathrm{AP}}$. It returns another `TransitionSystem`, whose states are
pairs $(s,q)$, atomic propositions are the automaton states $Q$, and labels
are $L'(s,q)=\{q\}$. Automaton input is the trace $L(s_0), L(s_1), \ldots$:
the initial label is consumed before the first product state, while each
product transition consumes its target state's label. For an NBA, the accepting
product states are the pairs $(s,q)$ for which $q \in F$. The returned
transition system stores the graph and labels; the caller retains the
automaton's acceptance condition.

The automaton must declare its complete alphabet $2^{\mathrm{AP}}$, including
valuations that no system state currently uses. This follows the formal product
definition and makes a mismatched proposition vocabulary explicit.

## Visualisation

With the `visualization` extra installed, `to_graphviz` returns a
`graphviz.Digraph`. Nodes display their state identifier and atomic-proposition
label; arrows from invisible markers identify initial states. Highlighted
states and transitions have thicker outlines, and a current state has a double
outline.

```python
from mocha.visualisation import to_graphviz

graph = to_graphviz(system, highlighted_states={"running"})
graph.render("system", format="svg", cleanup=True)
```

`visualise_step`, `visualise_reachability_step`, `visualise_invariant_step`,
and `visualise_invariant_result` turn analysis snapshots and results into the
same kind of graph.

`visualise_persistence_counterexample` draws a failing persistence check as an ordered
lasso: each path position is a separate node, blue nodes belong to the
repeating cycle, and the final arrow returns to its first position. A
successful result has no counterexample and raises `ValueError` if passed
to this function. Since the witness records states rather than actions, an
arrow lists every action connecting its two states.

```python
from mocha import TransitionSystem
from mocha.algorithms.persistence import check_persistence
from mocha.visualisation import visualise_persistence_counterexample

system = TransitionSystem.from_components(
    states={"idle", "busy"}, actions={"tick"},
    transitions={("idle", "tick", "busy"), ("busy", "tick", "busy")},
    initial_states={"idle"}, atomic_propositions={"stable"},
    labels={"idle": {"stable"}, "busy": set()},
)
result = check_persistence(system, "stable")
graph = visualise_persistence_counterexample(system, result)
graph.render("persistence_result", format="svg", cleanup=True)
```

`to_lasso_graphviz(system, states, loop_start)` also accepts a lasso directly.
Both functions accept formatting callbacks for complex states, actions, and
propositions. 

## License

MoChA is licensed under the Mozilla Public License 2.0. See
[LICENSE](LICENSE) for the full license text.

## Funding

MoChA is partially funded by RWTH Aachen University as part of the Exploratory Teaching Space project ETS607 "The Model Checking Assistant: A Learning Framework for the Model Checking Course".
