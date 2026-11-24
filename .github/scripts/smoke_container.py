"""Exercise the installed container package, JSON schema, and Graphviz runtime."""

from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree

from mocha import TransitionSystem, check_invariant, compute_reachable_states
from mocha.io import from_dict, to_dict
from mocha.visualisation import to_graphviz


def main() -> None:
    system = TransitionSystem.from_components(
        states={"start", "done", "unreachable"},
        actions={"step"},
        transitions={("start", "step", "done"), ("done", "step", "done")},
        initial_states={"start"},
        atomic_propositions={"complete"},
        labels={"done": {"complete"}},
    )
    # Loading validates the schema bundled in the installed wheel.
    system = from_dict(to_dict(system))
    assert compute_reachable_states(system) == {"start", "done"}
    assert check_invariant(system, {"start", "done"}).satisfies
    violation = check_invariant(system, {"start"})
    assert not violation.satisfies
    assert violation.counterexample == ("start", "done")

    # Use the default working directory to check it is writable by the image user.
    with TemporaryDirectory(dir=Path.cwd()) as directory:
        output = to_graphviz(system).render(
            filename="system", directory=directory, format="svg", cleanup=True,
        )
        root = ElementTree.parse(output).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        labels = {element.text for element in root.iter(
            "{http://www.w3.org/2000/svg}text",
        )}
        assert {"start", "done", "{complete}"} <= labels

    print("Container smoke test passed: algorithms, JSON, and SVG rendering.")


if __name__ == "__main__":
    main()
