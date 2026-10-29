# CTL Guide

[Back to the README](../README.md)

This guide covers parsing and transforming CTL formulas, checking a transition
system, and interpreting satisfaction sets and algorithm traces. Install MoChA
using the [README installation instructions](../README.md#install).
Run the Python snippets in order in the same session; later snippets reuse
earlier variables.

- [Formulas](#formulas)
- [Existential normal form](#existential-normal-form)
- [Transformation traces](#transformation-traces)
- [Model checking](#model-checking)
- [Satisfaction sets](#satisfaction-sets)
- [Model-checking traces](#model-checking-traces)

## Formulas

CTL formulas are immutable syntax trees defined in `mocha.logic.ctl`.
Parse them with `mocha.io.parse_ctl`; normal forms, model checking, and trace
helpers live in `mocha.algorithms`. These helpers are also available directly
from `mocha`.

Atomic proposition names require double quotes and use JSON string escaping.
The unquoted constants `true` and `false` are Boolean values; `"true"` and
`"false"` are proposition names. An optional vocabulary checks which names
are allowed:

```python
from mocha import parse_ctl
from mocha.logic.ctl import Exists, Next, Proposition, is_ctl_formula

formula = parse_ctl('EX "ready"', atomic_propositions={"ready"})
assert formula == Exists(Next(Proposition("ready")))
assert is_ctl_formula(formula)
assert not is_ctl_formula(formula.operand)  # A bare path is not a state formula.
assert parse_ctl(formula.to_source()) == formula
```

Malformed syntax raises `CTLParseError` with a one-based line and column;
names outside the supplied vocabulary raise `ValueError`.
`str(formula)` uses textbook display notation and may omit proposition
quotes. Use `formula.to_source()` for text that can be parsed again.

`CTLStateFormula` represents propositions, Boolean operations, and path
quantifiers. `CTLPathFormula` represents one temporal operator with state
formulas as operands. Both inherit from `CTLFormula` and the corresponding
`mocha.logic.StateFormula` or `mocha.logic.PathFormula` base.
`Exists` (`E`) and `ForAll` (`A`) quantify each of these path operators:

| Path constructor | Meaning | Example source |
| --- | --- | --- |
| `Next(p)` | The next state satisfies `p`. | `EX "p"` |
| `Eventually(p)` | Some state, possibly the current one, satisfies `p`. | `AF "p"` |
| `Always(p)` | Every state, including the current one, satisfies `p`. | `EG "p"` |
| `Until(p, q)` | `q` eventually holds, and `p` holds at every earlier state. | `A("p" U "q")` |
| `WeakUntil(p, q)` | Until, also allowing `p` to hold forever without `q`. | `E("p" W "q")` |

Boolean syntax supports `!` (not) and `&`/`&&` (and). Negation and quantified
temporal operators bind more tightly than conjunction; parentheses group
state formulas. The parser also accepts `¬`, `∧`, `∃`, `∀`, `◯`/`○`, `◇`,
and `□`. Adjacent quantifier and temporal symbols are accepted: `EX "p"`
and `E X "p"` mean the same thing.

Temporal nesting passes through another path quantifier: `AG AF "p"` is
valid CTL. Constructors require state-formula operands, so an unquantified
nesting such as `Always(Next(p))` is rejected. `is_ctl_formula` checks the
supported fragment recursively, independently of normal form.

## Existential Normal Form

`to_existential_normal_form` rewrites a CTL state formula using only `true`,
propositions, `Not`, `And`, and `Exists` wrapping `Next`, `Until`, or `Always`.
Negation may apply to any state formula. The transformation eliminates
`false`, universal quantifiers, existential eventually, and existential weak
until. For example, `AF p` becomes `!EG !p`, and `EF p` becomes `E(true U p)`.

```python
from mocha import to_existential_normal_form

ctl_formula = parse_ctl('AF "done"')
ctl_enf = to_existential_normal_form(ctl_formula)
assert ctl_enf == parse_ctl('!EG !"done"')
```

These rewrites preserve meaning under infinite-path semantics. Parsing and
transforming a formula do not check a transition system. `model_check_ctl`
requires the ENF input explicitly; passing a non-ENF formula raises `ValueError`.

## Transformation Traces

`trace_existential_normal_form` returns an `AlgorithmTrace` with the
transformed formula in `result` and immutable `CTLRewriteStep` snapshots in
`steps`:

```python
from mocha import trace_existential_normal_form

rewrite_trace = trace_existential_normal_form(ctl_formula)
assert rewrite_trace.result == ctl_enf
for step in rewrite_trace.steps:
    print(step.iteration, step.rule, step.formula)
```

The first step records the input formula. Each later step records one named
rewrite, the whole formula after that rewrite, and the changed subformula
in `before` and `after`. Its `path` identifies the location using `operand`,
`left`, and `right`. Paths include both the quantifier and temporal levels:
the proposition in `Exists(Next(p))` is at `("operand", "operand")`.
`to_existential_normal_form` also accepts an `on_step` callback to stream the
same snapshots.

## Model Checking

`model_check_ctl` computes satisfaction sets bottom-up for the ENF formula.
The transition system must have no terminal states, including unreachable
ones, and every proposition in the formula must be declared in the system's
`atomic_propositions`. Either violation raises `ValueError`.

```python
from mocha import TransitionSystem, model_check_ctl

ctl_system = TransitionSystem.from_edges(
    states={"waiting", "done"},
    edges={("waiting", "done"), ("done", "done")},
    action="step", initial_states={"waiting"},
    atomic_propositions={"done"}, labels={"done": {"done"}},
)
ctl_result = model_check_ctl(ctl_system, ctl_enf)
assert ctl_result.satisfies
assert ctl_result.satisfying_states == {"waiting", "done"}
assert not ctl_result.violating_initial_states
```

The self-loop at `done` ensures that paths continue infinitely.
`CTLModelCheckingResult.satisfies` is true when **every initial state** belongs
to `satisfying_states`; with no initial states, it is true vacuously.
`violating_initial_states` contains the initial states where the property
fails. Satisfaction sets cover all states, including unreachable ones.
The result's `formula` is the ENF formula passed to the checker.

## Satisfaction Sets

`subformula_sets` contains one `CTLSubformulaStep` per structurally distinct
state subformula of the ENF input, ordered with operands before their parents.
Each row includes its evaluation `rule`, operand sets in `premises`, and a
set-theoretic `explanation`:

```python
assert ctl_result.set_for(parse_ctl('"done"')) == {"done"}
for row in ctl_result.subformula_sets:
    print(row.formula, row.satisfying_states, row.explanation)
```

`set_for(formula)` looks up one of these sets and raises `KeyError` if the
formula has no row. Rewritten-away source formulas and bare path formulas
have no separate rows: the quantifier and its temporal operand form one
evaluation rule.

## Model-Checking Traces

`trace_ctl_model_checking` returns an `AlgorithmTrace` with the final `result`
and an immutable tuple of `steps`. Both it and `model_check_ctl` accept
`detail="sets"` (the default) or `detail="reasoning"`:

| Detail | Trace steps |
| --- | --- |
| `"sets"` | One `CTLSubformulaStep` for each distinct state subformula; these are also the result's `subformula_sets`. |
| `"reasoning"` | The same summary rows, plus `CTLPredecessorStep` successor checks for `EX` and `CTLFixedPointStep` search snapshots for `EU` and `EG`. |

```python
from mocha import CTLFixedPointStep, trace_ctl_model_checking

ctl_trace = trace_ctl_model_checking(ctl_system, ctl_enf, detail="reasoning")
assert ctl_trace.result == ctl_result
for step in ctl_trace.steps:
    if isinstance(step, CTLFixedPointStep):
        print(step.iteration, step.approximation, step.pending_states)
```

For `EX`, each `CTLSuccessorCheck.matching_successors` contains the successors
satisfying the operand; an empty set explains why that state fails the check.
The `EU` and `EG` searches follow Algorithms 15 and 16 in *Principles of
Model Checking*. Their snapshots record `approximation` (`T`),
`pending_states` (`E`), `processed_state`, and added or removed states.
Iteration zero records initialization with `processed_state=None`; each later
snapshot follows processing one pending state. Pending states are selected
in arbitrary order, so intermediate snapshots can vary between runs.

For `EG`, `successor_counts` stores `(state, count)` pairs with
`count[s] = |Post(s) ∩ (T ∪ E)|` for every operand state. Its `checks` instead
show matching successors in the current `T`, so their sizes can differ from
the counters. For `EU`, `checks` records the processed successor witnessing
each newly added state.

To stream the same events without collecting a trace, pass an `on_step`
callback to `model_check_ctl`. Trace helpers retain all snapshots in memory.
Result and step types are exported from both `mocha` and `mocha.algorithms`.
