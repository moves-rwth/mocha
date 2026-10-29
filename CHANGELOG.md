# Changelog

## Unreleased

### Added

- Transition-system rendering supports arbitrary hashable states, actions,
  and propositions, including product-state tuples. `to_graphviz`,
  `visualise_step`, `visualise_reachability_step`, `visualise_invariant_step`,
  and `visualise_invariant_result` accept `format_state`, `format_action`, and
  `format_proposition` callbacks. Defaults use `str` and preserve existing
  string-valued calls. Formatting preserves state identities and highlighting.

### Changed

- `compute_reachable_states` now returns `frozenset[State]` directly, and
  `trace_reachability(...).result` contains that same reachable set.
- Removed `ReachabilityResult` from the public API. Replace
  `compute_reachable_states(system).reachable_states` with
  `compute_reachable_states(system)`. `ReachabilityStep` still exposes
  `iteration` and `reachable_states` for progress snapshots.

## 0.1.0

First stable release of MoChA, a teaching library for model checking.

- Labelled transition systems and finite, Büchi, and generalized Büchi automata.
- Reachability, invariant, persistence, and LTL model checking.
- LTL parsing, normal-form transformations, and automata construction.
- Algorithm traces exposing intermediate steps for teaching.
- Validated JSON import and export for string-valued transition systems.
- Optional Graphviz visualisation for transition systems, automata, and counterexamples.
- Docker images with JupyterLab, a Python notebook kernel, and Graphviz for
  `linux/amd64` and `linux/arm64`.

Requires Python 3.11 or later. Image rendering additionally requires the Graphviz
executables, which are included in the Docker images.

## 0.1.0rc1

First release candidate of MoChA, a teaching library for model checking.

- Labelled transition systems and finite, Büchi, and generalized Büchi automata.
- Reachability, invariant, persistence, and LTL model checking.
- LTL parsing, normal-form transformations, and automata construction.
- Algorithm traces exposing intermediate steps for teaching.
- Validated JSON import and export for string-valued transition systems.
- Optional Graphviz visualisation.

Requires Python 3.11 or later. Image rendering additionally requires the Graphviz executables.
