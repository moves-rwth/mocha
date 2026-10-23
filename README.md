# Model Checking Assistant (MoChA)

[![CI](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/moves-rwth/mocha/actions/workflows/ci.yml)

MoChA is a small, typed Python library for representing labelled transition
systems and automata, checking reachability, invariants, persistence, and LTL
properties, and parsing and transforming LTL formulas. Algorithm traces expose
intermediate steps for teaching and worked examples.

The public API is available from `mocha`: models, analysis results and traces,
algorithms, and parsing and JSON helpers. These names are also exported from
`mocha.models`, `mocha.algorithms`, and `mocha.io`. LTL formula constructors
live in `mocha.logic.ltl` (also available as `mocha.ltl`), and rendering helpers
are exported from `mocha.visualisation` with the optional `visualization` extra.

## Install

MoChA requires Python 3.11 or later.

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


## LTL Formulas

LTL formulas are immutable syntax trees defined in `mocha.logic.ltl`.
Parse them with `mocha.io.parse_ltl`; normal forms and rewrite traces live in
`mocha.algorithms`. These helpers are also available directly from `mocha`.

Atomic proposition names require double quotes and use JSON string escaping.
The unquoted constants `true` and `false` are Boolean values; `"true"` and
`"false"` are proposition names. An optional vocabulary checks which names
are allowed:

```python
from mocha import parse_ltl

formula = parse_ltl(
    'G("request" -> F "grant")',
    atomic_propositions={"request", "grant"},
)
print(formula)  # □(request → ◇grant)
source = formula.to_source()
assert parse_ltl(source) == formula
```

Malformed syntax raises `LTLParseError` with a one-based line and column;
names outside the supplied vocabulary raise `ValueError`.
`str(formula)` uses textbook display notation and may omit proposition
quotes. Use `formula.to_source()` for text that can be parsed again.

Supported operators are `!` (not), `&`/`&&` (and), `|`/`||` (or), `->`
(implication), `<->` (equivalence), `X` (next), `F` (eventually), `G`
(always), `U` (until), `W` (weak until), and `R` (release). The parser also
accepts `¬`, `∧`, `∨`, `→`, `↔`, `◯`/`○`, `◇`, and `□`.
From strongest to weakest, precedence is unary operators, `U`/`W`/`R`,
conjunction, disjunction, implication, then equivalence. Implication and the
temporal operators `U`, `W`, and `R` are not associative: chaining them at the
same precedence requires parentheses. Write `"p" -> ("q" -> "r")` or
`("p" -> "q") -> "r"`; `"p" -> "q" -> "r"` is rejected. The same applies to
mixed temporal chains: write `"p" U ("q" R "r")` or `("p" U "q") R "r"`.
Conjunction, disjunction, and equivalence may be chained and are grouped to
the left. Parentheses override precedence. Adjacent unary temporal operators
are accepted: `GF"p"` means `G F "p"`.

### Normal Forms

`normalize_ltl` rewrites a formula using only conjunction, negation, next,
and until, plus propositions and Boolean constants. Negation may still
apply to a temporal formula in this form.

`to_release_pnf` and `to_weak_until_pnf` instead produce positive normal
forms, where negation applies only to propositions. Both allow conjunction,
disjunction, next, and until; the former also allows release, and the latter
weak until. Boolean constants remain allowed in both forms.

```python
from mocha.algorithms import (
    normalize_ltl, to_release_pnf, to_weak_until_pnf,
)

print(normalize_ltl(parse_ltl('G"p"')))  # ¬(true U ¬p)
negated_until = parse_ltl('!("p" U "q")')
print(to_release_pnf(negated_until))     # ¬p R ¬q
print(to_weak_until_pnf(negated_until))  # (p ∧ ¬q) W (¬p ∧ ¬q)
```

### Transformation Traces

`trace_normalize_ltl`, `trace_release_pnf`, and `trace_weak_until_pnf`
return an `AlgorithmTrace` with the transformed formula in `result` and
immutable `LTLRewriteStep` snapshots in `steps`:

```python
from mocha.algorithms import trace_normalize_ltl

trace = trace_normalize_ltl(formula)
for step in trace.steps:
    print(step.iteration, step.rule, step.formula)
assert trace.result == normalize_ltl(formula)
```

The first step records the input formula. Each later step records one named
rewrite, the whole formula after that rewrite, and the changed subformula
in `before` and `after`. Its `path` identifies the location using `operand`,
`left`, and `right`. The direct transformations also accept an `on_step`
callback to stream the same snapshots.

These transformations preserve the formula's meaning on infinite words.
Parsing and transforming a formula do not check whether a transition system
satisfies it.

### Model Checking

`check_ltl(system, property)` checks whether **every infinite run from every
initial state** satisfies an LTL formula. Interpretation starts with the initial
state's label: `"grant"` concerns that state, while `X "grant"` concerns its
successor. Derived operators such as `F` and `G` are normalized automatically.

The system must have no terminal states, including unreachable ones. Its
declared atomic proposition names must be strings, and every name in the formula
must be declared. Extra system propositions are allowed and ignored by the
automaton construction. The input system is not modified. With no initial
states, every property holds vacuously.

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

ltl_property = parse_ltl('G "grant"')
ltl_result = check_ltl(ltl_system, ltl_property)
assert not ltl_result.satisfies  # grant is absent in the initial state
```

When the property fails, `counterexample` contains a finite representation of
an infinite violating path: a prefix followed by a repeating cycle, called a
lasso. Its entries are original system states. The final entry repeats the state
at the zero-based `loop_start` index to close the cycle; omit that last entry
when extracting the repeating portion:

```python
ltl_path = ltl_result.counterexample
ltl_loop_start = ltl_result.loop_start
assert ltl_path is not None and ltl_loop_start is not None
assert ltl_path[-1] == ltl_path[ltl_loop_start]

ltl_prefix = ltl_path[:ltl_loop_start]   # traverse once
ltl_cycle = ltl_path[ltl_loop_start:-1]  # repeat forever
assert ltl_cycle
```

Apply `ltl_system.labels(state)` along that infinite path to obtain the word
that violates the property. A counterexample need not be shortest or unique.
When the property holds, `counterexample`, `product_counterexample`, and
`loop_start` are all `None`.

For construction details, the result also retains the negated formula, its
GNBA translation, the equivalent NBA, and the system–NBA product. The separate
`search_product` marks non-accepting states and completes product dead ends with
a non-accepting sink for persistence search. `product_counterexample` retains
the automaton component of each path position; `counterexample` projects it
onto the original system while preserving the cycle boundary.

`trace_check_ltl` collects the steps for negation, GNBA translation, NBA
conversion, product construction, emptiness search, and the verdict. Detailed
translation and depth-first-search events are available in each step's `detail`:

```python
from mocha import trace_check_ltl

ltl_trace = trace_check_ltl(ltl_system, ltl_property)
assert not ltl_trace.result.satisfies
for step in ltl_trace.steps:
    print(step.iteration, step.stage, step.message)
```

The direct check also accepts `on_step` to stream the same events. Trace helpers
retain all snapshots in memory. To draw the projected counterexample, use the
lasso renderer with the optional `visualization` extra:

```python
from mocha.visualisation import to_lasso_graphviz

ltl_graph = to_lasso_graphviz(ltl_system, ltl_path, ltl_loop_start)
```

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
