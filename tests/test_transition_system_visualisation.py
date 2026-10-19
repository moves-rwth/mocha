import shutil
import unittest
from xml.etree import ElementTree

from mocha import Transition, TransitionSystem
from mocha.visualisation import to_graphviz, to_lasso_graphviz


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
                    format_state=lambda _: value,
                    format_action=lambda _: value,
                    format_proposition=lambda _: value,
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
