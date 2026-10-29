# Model Checking Assistant (MoChA)

[![CI](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml)

MoChA is a small, typed Python library for representing labelled transition
systems and automata, checking reachability, invariants, persistence, and CTL
and LTL properties, and parsing and transforming temporal-logic formulas. Algorithm traces expose
intermediate steps for teaching and worked examples.

The public API is available from `mocha`: models, analysis results and traces,
algorithms, and parsing and JSON helpers. These names are also exported from
`mocha.models`, `mocha.algorithms`, and `mocha.io`. CTL and LTL formula constructors
live in `mocha.logic.ctl` and `mocha.logic.ltl` (also available as `mocha.ctl`
and `mocha.ltl`), and rendering helpers
are exported from `mocha.visualisation` with the optional `visualization` extra.

## Install

MoChA requires Python 3.11 or later. Install the package from PyPI:

```bash
python -m pip install mocha-model-checking
```

For the optional visualisation helpers:

```bash
python -m pip install 'mocha-model-checking[visualization]'
```

Rendering images also requires the [Graphviz](https://graphviz.org/)
executables, including `dot`, to be installed and available on your `PATH`.
Core models, algorithms, and JSON helpers work without Graphviz.

To install from a source checkout, run one of these commands from its root:

```bash
python -m pip install .
python -m pip install '.[visualization]'
```

### Docker

Use Docker to run MoChA in JupyterLab without installing Python or Graphviz
separately. The image includes Python 3.15, a Python notebook kernel, and
Graphviz for drawing diagrams. It works on Intel/AMD computers and Apple
Silicon.

With Docker installed, start JupyterLab using the latest nightly version.
Run this command from the directory where you want to keep your notebooks:

```bash
docker run --pull always --rm -it \
  -p 127.0.0.1:8888:8888 \
  --mount "type=bind,src=$PWD,dst=/work" \
  ghcr.io/moves-rwth/mocha:nightly
```

The first run downloads the image. `--pull always` checks for an updated image
each time you run it. When **Starting MoChA with JupyterLab** appears, allow a
few seconds for startup, then open the browser link printed below it. The link
includes your login token and opens JupyterLab directly.

Keep the terminal open while you work. To stop JupyterLab, save your notebook,
return to the terminal, and press **Ctrl+C**.

The mounted directory appears as `/work` in the container. Notebooks and
diagrams saved there remain on your computer after the container stops.
On Linux, the mounted directory must be writable by UID 1000, the container's
user.

For an interactive Python prompt, run:

```bash
docker run --pull always --rm -it ghcr.io/moves-rwth/mocha:nightly python
```

To run a script from your current directory:

```bash
docker run --pull always --rm \
  --mount "type=bind,src=$PWD,dst=/work" \
  ghcr.io/moves-rwth/mocha:nightly python my_script.py
```

Choose the version that suits your work:

- `nightly`: the current development version, updated each night.
- `latest`: the most recent stable release, available after the first stable
  release is published.
- A specific [release tag](https://github.com/moves-rwth/mocha/releases)

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
from mocha import TransitionSystem

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

## Reachability and Invariants

`compute_reachable_states` finds all states reachable from any initial state,
including the initial states themselves. `check_invariant` checks whether
every reachable state belongs to a supplied set of allowed states. A failing
result contains a path from an initial state to a violating state:

```python
from mocha import check_invariant, compute_reachable_states, trace_reachability

reachable = compute_reachable_states(system)
assert reachable.reachable_states == {"idle", "running", "done"}

result = check_invariant(system, {"idle", "running"})
assert not result.satisfies
assert result.counterexample == ("idle", "running", "done")

trace = trace_reachability(system)
assert trace.result == reachable
for step in trace.steps:
    print(step.iteration, step.reachable_states)
```

Use `reduce_to_reachable(system)` to create a new transition system containing
only reachable states and transitions between them. It preserves their labels,
all initial states, and the declared action and proposition sets. The original
system remains unchanged; with no initial states, the result has no states.

```python
from mocha import reduce_to_reachable

reduced = reduce_to_reachable(system)
assert reduced.states == reachable.reachable_states
```

`trace_reachability`, `trace_invariant`, and `trace_persistence` return an
`AlgorithmTrace` with the final `result` and an immutable tuple of `steps`.
The direct algorithms also accept an `on_step` callback to stream snapshots.
Their result and step types are exported from `mocha` and `mocha.algorithms`.

For a complete invariant walkthrough, see
[examples/invariant_checking.py](https://github.com/moves-rwth/mocha/blob/main/examples/invariant_checking.py).
It builds a faulty mutual-exclusion model, derives the allowed states from
their labels, explains the counterexample, and prints each invariant-checking
step. It then removes the faulty transition and checks the invariant again.
With MoChA installed, run it from the repository root:

```bash
python -I examples/invariant_checking.py
```

## JSON Import and Export

String-valued transition systems can be saved as versioned JSON documents:

```python
from mocha import (
    from_dict, load_transition_system, save_transition_system, to_dict,
)

document = to_dict(system)
restored = from_dict(document)
assert to_dict(restored) == document

save_transition_system(system, "system.json")
restored = load_transition_system("system.json")
```

`to_dict` produces deterministic ordering. `from_dict` and
`load_transition_system` validate both the JSON Schema and the model's
cross-references. Invalid document structure raises
`jsonschema.ValidationError`; invalid component references raise `ValueError`.
`validate_dict` checks only the schema. Saving replaces an existing file at
the supplied path.

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
from mocha import FiniteAutomaton

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
from mocha import GNBA

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

## State and Path Formulas

`mocha.logic.StateFormula` and `mocha.logic.PathFormula` distinguish formulas
evaluated at a state from formulas evaluated along a path. Both inherit from
`Formula`. LTL syntax trees inherit from `PathFormula`.

CTL has separate `CTLStateFormula` and `CTLPathFormula` types in
`mocha.logic.ctl`, with `CTLFormula` as their common base. Propositions,
Boolean operations, and path quantifiers are state formulas. Temporal
operators are path formulas, and their operands must be CTL state formulas:

```python
from mocha import parse_ctl
from mocha.logic.ctl import Exists, Next, Proposition, is_ctl_formula

formula = Exists(Next(Proposition("ready")))
assert formula == parse_ctl('EX "ready"')
assert is_ctl_formula(formula)
assert not is_ctl_formula(formula.operand)  # A bare path is not a CTL state formula.
```

`Exists` and `ForAll` quantify path formulas built with `Next`, `Always`,
`Eventually`, `Until`, and `WeakUntil`. Both existential and universal
quantification support all five. Construct formulas with explicit quantifier
and temporal nodes, such as `Exists(Next(p))` or `ForAll(Always(p))`.
Compact source notation such as `EX "p"` and `AG "p"` is also accepted.

`parse_ctl` still accepts only the supported CTL fragment. Constructors reject
unquantified temporal operands, such as `Always(Next(p))`. `is_ctl_formula`
checks the fragment recursively, independently of normal form.
`Exists(Eventually(p))` and `Exists(WeakUntil(p, q))` have source spellings
`EF "p"` and `E("p" W "q")`. Normalization rewrites them using existential
until and always.
CTL normal forms and their rewrite traces live in
`mocha.algorithms.ctl_transformations`, following the LTL organization.
`CTLRewriteStep`, `to_existential_normal_form`, and
`trace_existential_normal_form` are also exported from `mocha.algorithms`
and `mocha`.
`model_check_ctl` evaluates formulas in existential normal form and reports
satisfaction sets only for state subformulas of that normalized formula.
Rewrite trace paths include the extra quantifier/temporal level;
the proposition in `Exists(Next(p))` is at `("operand", "operand")`.
The `EU` and `EG` searches follow Algorithms 15 and 16 in *Principles of
Model Checking*. With `detail="reasoning"`, their trace records the candidate
set `T`, pending set `E`, and processed state after each worklist iteration;
the `EG` trace also includes successor counters.

CTL model checking requires a transition system without terminal states:
every state, including unreachable ones, must have at least one outgoing
transition. A terminal state causes `ValueError`. The self-loop at `done`
in the following example ensures that paths continue infinitely.

The CTL workflow keeps each stage explicit: construct or parse a formula,
rewrite it into existential normal form, then compute the state-subformula
sets. For example, every path in this system eventually reaches `done`:

```python
from mocha import (
    TransitionSystem, model_check_ctl, parse_ctl,
    to_existential_normal_form, trace_ctl_model_checking,
)

ctl_system = TransitionSystem.from_edges(
    states={"waiting", "done"},
    edges={("waiting", "done"), ("done", "done")},
    action="step", initial_states={"waiting"},
    atomic_propositions={"done"}, labels={"done": {"done"}},
)
ctl_formula = parse_ctl('AF "done"')
ctl_enf = to_existential_normal_form(ctl_formula)  # AF done ≡ ¬EG ¬done
ctl_result = model_check_ctl(ctl_system, ctl_enf)
assert ctl_result.satisfies
assert ctl_result.satisfying_states == {"waiting", "done"}

ctl_trace = trace_ctl_model_checking(ctl_system, ctl_enf, detail="reasoning")
assert ctl_trace.result == ctl_result
```


## LTL Model Checking

`check_ltl` checks whether every infinite run from an initial state satisfies
an LTL formula. For example, this system eventually reaches a state labelled
`grant` and stays there:

```python
from mocha import TransitionSystem, check_ltl, parse_ltl

ltl_system = TransitionSystem.from_components(
    states={"waiting", "granted"},
    actions={"step"},
    transitions={
        ("waiting", "step", "granted"),
        ("granted", "step", "granted"),
    },
    initial_states={"waiting"},
    atomic_propositions={"grant"},
    labels={"waiting": set(), "granted": {"grant"}},
)

assert check_ltl(ltl_system, parse_ltl('F "grant"')).satisfies
assert not check_ltl(ltl_system, parse_ltl('G "grant"')).satisfies
```

`F` means “eventually” and `G` means “always”. The second property fails
because `grant` is absent in the initial state. LTL checking requires every
state to have an outgoing transition and every formula proposition to be
declared in the system.

The [LTL guide](https://github.com/moves-rwth/mocha/blob/main/docs/ltl.md)
explains formula syntax, normal forms, rewrite traces, checking preconditions,
and how to interpret and visualise a counterexample's repeating cycle.

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

`to_graphviz` and the analysis-step renderers currently accept string-valued
states, actions, and propositions. State labels are displayed as literal
text. Actions connecting the same pair of states share an edge label, with
highlighted actions drawn on a separate edge.

The returned graph supports several output workflows:

```python
graph.save("system.dot")                          # Graphviz DOT source
graph.render("system", format="png", cleanup=True)  # PNG image
svg_bytes = graph.pipe(format="svg")              # SVG bytes in memory
```

In a Jupyter notebook, use `display(graph)` to show the graph inline.
Building the graph or saving DOT source requires the Python `graphviz`
package; rendering an image also needs the Graphviz executables.

`visualise_step`, `visualise_reachability_step`, `visualise_invariant_step`,
and `visualise_invariant_result` turn analysis snapshots and results into the
same kind of graph.

```python
from mocha.visualisation import visualise_reachability_step

graph = visualise_reachability_step(system, trace_reachability(system).steps[0])
```

### Automata

`to_automaton_graphviz` renders `Automaton`, `FiniteAutomaton`, `NBA`, and `GNBA`
models as state diagrams. States are circles by default, incoming
arrows identify initial states, and accepting states of finite and Büchi automata
use squares. Pass `accepting_state_shape=AcceptingStateShape.DOUBLE_CIRCLE` to
use double circles instead. Symbols connecting the same pair of states share
an edge label.

```python
from mocha import FiniteAutomaton
from mocha.visualisation import AcceptingStateShape, to_automaton_graphviz

automaton = FiniteAutomaton.from_components(
    states={"q0", "q1"}, alphabet={"a", "b"},
    transitions={
        ("q0", "a", "q0"), ("q0", "b", "q1"), ("q1", "b", "q1"),
    },
    initial_states={"q0"}, accepting_states={"q1"},
)
graph = to_automaton_graphviz(
    automaton, accepting_state_shape=AcceptingStateShape.SQUARE,
)
graph.render("automaton", format="svg", cleanup=True)
```

For generalized Büchi automata, bracketed labels such as `[F1, F2]` mark
acceptance-set memberships directly below the state name inside the circle.
The diagram uses no colours, legend, or set definitions. An accepting run must
visit every set infinitely often. An SVG graph tooltip identifies empty sets
that cannot be marked on any state, or an empty family with no acceptance
requirements. Set indices are assigned for display; the model stores an
unordered family.

Use `format_state` and `format_symbol` to display non-string values, including
product states and sets of propositions. For example, an automaton over
proposition sets can use:

```python
from mocha import NBA

nba = NBA.from_components(
    states={0}, alphabet={frozenset(), frozenset({"p"})},
    transitions={(0, frozenset(), 0), (0, frozenset({"p"}), 0)},
    initial_states={0}, accepting_states={0},
)
graph = to_automaton_graphviz(
    nba,
    format_state=lambda state: str(state),
    format_symbol=lambda symbol: "{" + ", ".join(sorted(symbol)) + "}",
)
```

Labels are literal text. `highlighted_states` and `highlighted_transitions`
(iterables of `AutomatonTransition` values) draw thicker outlines and edges;
unknown selections raise `ValueError`. All the DOT, image, and notebook output
workflows above apply. The renderer is also available as
`mocha.visualisation.automaton.to_graphviz`.

### Persistence Counterexamples

`check_persistence(system, proposition)` checks whether every infinite run
eventually stays in states labelled with the proposition (`◇□proposition`).
The proposition must be declared, and every state must have an outgoing
transition, including unreachable states. Violations of these preconditions
raise `ValueError`.

`visualise_persistence_counterexample` draws a failing persistence check as an ordered
lasso: each path position is a separate node, shaded nodes belong to the
repeating cycle, blue arrows mark the cycle, and the final arrow returns to
its first position. A
successful result has no counterexample and raises `ValueError` if passed
to this function. Since the witness records states rather than actions, an
arrow lists every action connecting its two states.

```python
from mocha import TransitionSystem, check_persistence
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

```python
from mocha.visualisation import to_lasso_graphviz

graph = to_lasso_graphviz(system, ("idle", "busy", "busy"), loop_start=1)
```

The final state must repeat the state at `loop_start`; the sequence must
start in an initial state and follow existing transitions. Unlike
`to_graphviz`, the lasso renderer also supports non-string model values
through `format_state`, `format_action`, and `format_proposition` callbacks.

## Development

See the [contributor guide](https://github.com/moves-rwth/mocha/blob/main/CONTRIBUTING.md)
for environment setup, tests, the typing example, and release-artifact checks.
After setting up the development environment, run the test suite from the
repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

### Type Checking

Install the type checker, JSON Schema stubs, and visualisation dependency:

```bash
python -m pip install -e '.[visualization,typecheck]'
```

Run strict type checking across the library:

```bash
python -m mypy
```

The configuration in `pyproject.toml` checks `src/mocha` in strict mode,
targeting Python 3.11. Graphviz 0.21 lacks a `py.typed` marker, so a scoped
override lets mypy read its existing source annotations. Checking calls to
Graphviz is limited by the annotations it provides.

## Project Status and Scope

MoChA is intended for teaching and small worked examples. During the `0.x`
release series, public APIs may change between releases. Breaking changes will
be documented in the
[changelog](https://github.com/moves-rwth/mocha/blob/main/CHANGELOG.md).

LTL automata construction explicitly enumerates combinations of formula
choices and atomic-proposition valuations. Its time and memory requirements
can grow exponentially as formulas grow. Trace helpers retain intermediate
snapshots in memory, which can further increase memory use.

## License

MoChA is licensed under the Mozilla Public License 2.0. See
[LICENCE](LICENCE) for the full license text.

## Funding

MoChA is partially funded by RWTH Aachen University as part of the Exploratory Teaching Space project ETS607 "The Model Checking Assistant: A Learning Framework for the Model Checking Course".
