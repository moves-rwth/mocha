# LTL Guide

[Back to the README](../README.md)

This guide covers parsing and transforming LTL formulas, checking a transition
system, and interpreting counterexamples and algorithm traces. Install MoChA
using the [README installation instructions](../README.md#install).
Run the Python snippets in order in the same session; later snippets reuse
earlier variables. The final visualisation snippet requires the optional
`visualization` extra.

- [Formulas](#formulas)
- [Normal forms](#normal-forms)
- [Transformation traces](#transformation-traces)
- [Model checking and counterexamples](#model-checking)

## Formulas

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

## Normal Forms

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

## Transformation Traces

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

## Model Checking

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
