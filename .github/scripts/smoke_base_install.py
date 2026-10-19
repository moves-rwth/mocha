"""Exercise the installed base package without its visualisation dependency."""

from importlib import import_module
from importlib.util import find_spec


def main() -> None:
    assert find_spec("graphviz") is None, "The base installation includes graphviz"

    import mocha
    from mocha.algorithms import (
        check_invariant,
        check_persistence,
        compute_reachable_states,
    )
    from mocha.io import from_dict, to_dict

    # Importing the namespace should leave rendering dependencies optional.
    import_module("mocha.visualisation")

    # Every advertised core export must work without the optional dependency.
    for module_name in (
        "mocha", "mocha.algorithms", "mocha.io", "mocha.models", "mocha.logic",
    ):
        module = import_module(module_name)
        for name in module.__all__:
            getattr(module, name)

    system = mocha.TransitionSystem.from_components(
        states={"start", "stable", "unreachable"},
        actions={"step"},
        transitions={
            ("start", "step", "stable"),
            ("stable", "step", "stable"),
            ("unreachable", "step", "unreachable"),
        },
        initial_states={"start"},
        atomic_propositions={"safe"},
        labels={"start": set(), "stable": {"safe"}, "unreachable": set()},
    )
    system = from_dict(to_dict(system))

    assert compute_reachable_states(system).reachable_states == {"start", "stable"}
    assert check_invariant(system, {"start", "stable"}).satisfies
    invariant = check_invariant(system, {"start"})
    assert not invariant.satisfies
    assert invariant.counterexample == ("start", "stable")
    assert check_persistence(system, "safe").satisfies

    system.remove_label("stable", "safe")
    persistence = check_persistence(system, "safe")
    assert not persistence.satisfies
    assert persistence.counterexample == ("start", "stable", "stable")
    assert persistence.loop_start == 1

    print("Base installation smoke test passed without the graphviz package.")


if __name__ == "__main__":
    main()
