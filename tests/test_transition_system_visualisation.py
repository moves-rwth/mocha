import shutil
import unittest
from xml.etree import ElementTree

from mocha import (
    NBA,
    InvariantResult,
    InvariantStep,
    ReachabilityStep,
    Transition,
    TransitionSystem,
    transition_system_automaton_product,
)
from mocha.visualisation import (
    TransitionSystemOverlay,
    to_graphviz,
    to_lasso_graphviz,
    visualise_invariant_result,
    visualise_invariant_step,
    visualise_reachability_step,
    visualise_step,
)

SVG = "{http://www.w3.org/2000/svg}"


def svg_groups(graph, kind):
    root = ElementTree.fromstring(graph.pipe(format="svg"))
    return [
        group for group in root.iter(f"{SVG}g")
        if group.get("class") == kind
    ]


def text_labels(group):
    return ["".join(text.itertext()) for text in group.iter(f"{SVG}text")]


@unittest.skipUnless(shutil.which("dot"), "Graphviz executable is required")
class TransitionSystemRenderingTests(unittest.TestCase):
    def test_default_formatting_supports_mixed_hashable_values(self):
        states = [0, ("q", 1), frozenset({2}), None]
        actions = [3, ("step", 4), frozenset({5})]
        transitions = {
            (source, action, target)
            for source, action, target in zip(states[:-1], actions, states[1:], strict=True)
        }
        ts = TransitionSystem.from_components(
            states=states, actions=actions, transitions=transitions,
            initial_states=states, atomic_propositions={6, ("p", 7)},
            labels={state: {6, ("p", 7)} for state in states},
        )
        graph = to_graphviz(ts)
        nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
        labels_by_id = {
            node.findtext(f"{SVG}title"): text_labels(node)[0] for node in nodes
        }
        self.assertCountEqual(labels_by_id.values(), [str(state) for state in states])
        for node in nodes:
            self.assertIn("{('p', 7), 6}", text_labels(node))
            self.assertEqual(len(node.findall(f"{SVG}ellipse")), 1)
        actual_transitions = set()
        initial_targets = []
        for edge in svg_groups(graph, "edge"):
            source, target = edge.findtext(f"{SVG}title", default="").split("->")
            if text_labels(edge):
                actual_transitions.add((
                    labels_by_id[source], text_labels(edge)[0], labels_by_id[target],
                ))
            else:
                initial_targets.append(labels_by_id[target])
        self.assertEqual(actual_transitions, {
            (str(source), str(action), str(target))
            for source, action, target in transitions
        })
        self.assertCountEqual(initial_targets, [str(state) for state in states])
        self.assertEqual(set(ts.transitions()), transitions)

    def test_formatted_labels_do_not_merge_states_or_change_highlights(self):
        highlighted = Transition(0, 2, 1)
        ts = TransitionSystem.from_components(
            states={0, 1}, actions={2, 3},
            transitions={highlighted, (0, 3, 0)}, initial_states={0},
        )
        graph = to_graphviz(
            ts, highlighted_states={1}, highlighted_transitions={highlighted},
            current_state=1, format_state=lambda _: "same", format_action=lambda _: "go",
        )
        nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
        self.assertEqual(len(nodes), 2)
        self.assertEqual([text_labels(node)[0] for node in nodes], ["same", "same"])
        current = next(node for node in nodes if len(node.findall(f"{SVG}ellipse")) == 2)
        current_id = current.findtext(f"{SVG}title")
        edges = svg_groups(graph, "edge")
        initial = next(edge for edge in edges if not text_labels(edge))
        source_id = initial.findtext(f"{SVG}title", default="").split("->")[1]
        self.assertNotEqual(source_id, current_id)
        ordinary_edges = [edge for edge in edges if text_labels(edge)]
        self.assertEqual({edge.findtext(f"{SVG}title") for edge in ordinary_edges}, {
            f"{source_id}->{source_id}", f"{source_id}->{current_id}",
        })
        highlighted_edge = next(edge for edge in ordinary_edges
                                if edge.findtext(f"{SVG}title", default="").endswith(f"->{current_id}"))
        highlighted_path = highlighted_edge.find(f"{SVG}path")
        current_outline = current.find(f"{SVG}ellipse")
        assert highlighted_path is not None
        assert current_outline is not None
        self.assertEqual(highlighted_path.get("stroke-width"), "3")
        self.assertEqual(current_outline.get("stroke-width"), "3")

    def test_formatter_output_is_literal_text(self):
        ts = TransitionSystem.from_components(
            states={0}, actions={2}, transitions={(0, 2, 0)},
            initial_states={0}, atomic_propositions={1}, labels={0: {1}},
        )
        for value in ("<a & b>", r"raw\n\N\G", 'a "quoted" value', "∅漢字"):
            with self.subTest(value=value):
                graph = to_graphviz(
                    ts, format_state=lambda _, label=value: label,
                    format_action=lambda _, label=value: label,
                    format_proposition=lambda _, label=value: label,
                )
                node = next(node for node in svg_groups(graph, "node") if text_labels(node))
                self.assertCountEqual(text_labels(node), [value, f"{{{value}}}"])
                self.assertEqual(
                    [label for edge in svg_groups(graph, "edge") for label in text_labels(edge)],
                    [value],
                )

    def test_helpers_forward_all_formatters_for_generic_states(self):
        ts = TransitionSystem.from_components(
            states={0, 1}, actions={2}, transitions={(0, 2, 1)},
            initial_states={0}, atomic_propositions={3}, labels={0: {3}, 1: {3}},
        )
        cases = (
            (visualise_reachability_step, ReachabilityStep(1, frozenset({0, 1}))),
            (visualise_invariant_step, InvariantStep(1, frozenset({0, 1}), False)),
            (visualise_invariant_result, InvariantResult(False, (0, 1))),
            (visualise_invariant_result, InvariantResult(True)),
            (visualise_step, TransitionSystemOverlay(
                highlighted_states=frozenset({1}),
                highlighted_transitions=frozenset({Transition(0, 2, 1)}),
            )),
        )
        for renderer, record in cases:
            with self.subTest(renderer=renderer.__name__, record=record):
                graph = renderer(
                    ts, record, format_state=lambda value: f"s{value}",
                    format_action=lambda value: f"a{value}",
                    format_proposition=lambda value: f"p{value}",
                )
                nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
                self.assertCountEqual([text_labels(node) for node in nodes], [
                    ["s0", "{p3}"], ["s1", "{p3}"],
                ])
                self.assertEqual(
                    [label for edge in svg_groups(graph, "edge") for label in text_labels(edge)],
                    ["a2"],
                )

    def test_transition_system_automaton_product_renders_directly(self):
        ts = TransitionSystem.from_edges(
            states={0, 1}, edges={(0, 1), (1, 1)}, action=2,
            initial_states={0}, atomic_propositions={"p"}, labels={1: {"p"}},
        )
        alphabet = {frozenset(), frozenset({"p"})}
        automaton = NBA.from_components(
            states={"q"}, alphabet=alphabet,
            transitions={("q", symbol, "q") for symbol in alphabet},
            initial_states={"q"}, accepting_states={"q"},
        )
        product = transition_system_automaton_product(ts, automaton)
        for formatter in (str, lambda state: f"{state[0]} / {state[1]}"):
            with self.subTest(formatter=formatter):
                graph = to_graphviz(product, format_state=formatter)
                nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
                self.assertCountEqual(
                    [text_labels(node)[0] for node in nodes],
                    [formatter(state) for state in product.states],
                )
                self.assertEqual(len(svg_groups(graph, "edge")), 3)

    def test_state_names_do_not_change_graph_topology(self):
        states = {"a", "a:b", "__initial_0", "state_0"}
        transitions = {
            ("a", "go", "a:b"),
            ("a:b", "go", "__initial_0"),
            ("__initial_0", "go", "state_0"),
            ("state_0", "go", "a"),
        }
        ts = TransitionSystem.from_components(
            states=states,
            actions={"go"},
            transitions=transitions,
            initial_states=states,
        )
        graph = to_graphviz(ts)
        # Initial markers have no text; only state nodes contribute labels.
        nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
        labels_by_id = {
            node.findtext(f"{SVG}title", default=""): text_labels(node)[0]
            for node in nodes
        }
        self.assertEqual(set(labels_by_id.values()), states)
        self.assertEqual(len(nodes), len(states))

        actual_transitions = set()
        initial_targets = []
        for edge in svg_groups(graph, "edge"):
            source, target = edge.findtext(f"{SVG}title", default="").split("->")
            if text_labels(edge):
                actual_transitions.add((
                    labels_by_id[source], text_labels(edge)[0], labels_by_id[target],
                ))
            else:
                self.assertNotIn(source, labels_by_id)
                initial_targets.append(labels_by_id[target])
        self.assertEqual(actual_transitions, transitions)
        self.assertCountEqual(initial_targets, states)

    def test_transition_system_labels_are_literal_text(self):
        for value in ("<a & b>", r"raw\n\N\G", 'a "quoted" value', "∅漢字"):
            with self.subTest(value=value):
                ts = TransitionSystem()
                ts.add_state(value, initial=True, labels={value})
                ts.add_transition(value, value, value)
                for highlighted in ((), (Transition(value, value, value),)):
                    with self.subTest(highlighted=bool(highlighted)):
                        graph = to_graphviz(ts, highlighted_transitions=highlighted)
                        node = svg_groups(graph, "node")[0]
                        self.assertCountEqual(text_labels(node), [value, f"{{{value}}}"])
                        edges = svg_groups(graph, "edge")
                        self.assertEqual(
                            [label for edge in edges for label in text_labels(edge)],
                            [value],
                        )

    def test_lasso_formatter_output_is_literal_text(self):
        ts = TransitionSystem()
        ts.add_state(0, initial=True, labels={1})
        ts.add_transition(0, 2, 0)
        for value in ("<a & b>", r"raw\n\N\G", 'a "quoted" value', "∅漢字"):
            with self.subTest(value=value):
                graph = to_lasso_graphviz(
                    ts,
                    (0, 0, 0),
                    0,
                    format_state=lambda _, label=value: label,
                    format_action=lambda _, label=value: label,
                    format_proposition=lambda _, label=value: label,
                )
                nodes = [
                    node for node in svg_groups(graph, "node") if text_labels(node)
                ]
                self.assertEqual(len(nodes), 2)
                for index, node in enumerate(nodes):
                    self.assertCountEqual(
                        text_labels(node), [f"{index}: {value}", f"{{{value}}}"],
                    )
                self.assertCountEqual(
                    [label for edge in svg_groups(graph, "edge")
                     for label in text_labels(edge)],
                    [value, f"{value} (repeat)"],
                )


class TransitionSystemGraphvizTests(unittest.TestCase):
    def test_mixed_values_and_equal_labels_have_stable_ordering(self):
        states = [0, ("q", 1), frozenset({2}), None]
        actions = [3, ("step", 4), frozenset({5})]
        propositions = [6, ("p", 7)]
        transitions = [(states[0], action, states[1]) for action in actions]
        graphs = []
        for reverse in (False, True):
            ts = TransitionSystem()
            for state in reversed(states) if reverse else states:
                ts.add_state(state, initial=True,
                             labels=reversed(propositions) if reverse else propositions)
            for transition in reversed(transitions) if reverse else transitions:
                ts.add_transition(*transition)
            graphs.append(to_graphviz(
                ts, format_state=lambda _: "same", format_action=str,
                highlighted_transitions={transitions[0]},
            ).source)
        self.assertEqual(graphs[0], graphs[1])

    def test_highlights_use_model_values_and_validate_membership(self):
        ts = TransitionSystem.from_edges(
            states={0, 1}, edges={(0, 1)}, action=2, initial_states={0},
        )
        for selection in (
            {"highlighted_states": {"displayed label"}},
            {"highlighted_transitions": {Transition(0, 3, 1)}},
            {"current_state": 99},
        ):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                to_graphviz(ts, format_state=lambda _: "displayed label", **selection)

    def test_highlighted_actions_remain_separate_and_deterministic(self):
        ts = TransitionSystem()
        ts.add_state("s", initial=True)
        ts.add_transition("s", "normal", "s")
        ts.add_transition("s", "highlighted", "s")
        highlighted = Transition("s", "highlighted", "s")
        graph = to_graphviz(
            ts,
            highlighted_states={"s"},
            highlighted_transitions={highlighted},
            current_state="s",
        )
        self.assertIn("label=normal]", graph.source)
        self.assertIn("label=highlighted penwidth=3]", graph.source)
        self.assertIn("penwidth=3 peripheries=2", graph.source)
        ts.remove_transition("s", "normal", "s")
        ts.add_transition("s", "normal", "s")
        self.assertEqual(
            graph.source,
            to_graphviz(
                ts,
                highlighted_states={"s"},
                highlighted_transitions={highlighted},
                current_state="s",
            ).source,
        )


if __name__ == "__main__":
    unittest.main()
