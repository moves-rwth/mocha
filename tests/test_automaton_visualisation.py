"""Check automaton notation, graph topology, and literal Graphviz labels."""

import shutil
import subprocess
import sys
import unittest

from mocha import Automaton, AutomatonTransition, FiniteAutomaton, GNBA, NBA
from mocha.visualisation import AcceptingStateShape, to_automaton_graphviz
from mocha.visualisation.automaton import AcceptingStateShape as RendererAcceptingStateShape
from mocha.visualisation.automaton import to_graphviz
from test_transition_system_visualisation import SVG, svg_groups, text_labels


class AutomatonGraphvizTests(unittest.TestCase):
    def test_public_alias_and_acceptance_styles(self):
        self.assertIs(to_automaton_graphviz, to_graphviz)
        self.assertIs(AcceptingStateShape, RendererAcceptingStateShape)
        for model in (Automaton, FiniteAutomaton, NBA):
            with self.subTest(model=model.__name__):
                automaton = model.from_components(
                    states={"q0", "q1", "unreachable"}, alphabet={"a", "b"},
                    transitions={
                        ("q0", "a", "q1"), ("q0", "b", "q1"),
                        ("q1", "a", "q1"),
                    },
                    initial_states={"q0", "q1"},
                )
                if isinstance(automaton, (FiniteAutomaton, NBA)):
                    automaton.set_accepting("q1")
                source = to_graphviz(automaton).source
                self.assertIn("rankdir=LR", source)
                self.assertIn("node [shape=circle]", source)
                self.assertIn('state_0 -> state_1 [label="a, b"]', source)
                self.assertIn("state_1 -> state_1 [label=a]", source)
                self.assertIn("state_2 [label=unreachable]", source)
                self.assertIn("__initial_0 -> state_0", source)
                self.assertIn("__initial_1 -> state_1", source)
                self.assertEqual(source.count("shape=square"), int(model != Automaton))
                for shape in AcceptingStateShape:
                    styled = to_graphviz(
                        automaton, accepting_state_shape=shape,
                        highlighted_states={"q1"},
                    ).source
                    expected = (
                        f"state_1 [label=q1 penwidth=3 shape={shape.value}]"
                        if model != Automaton else "state_1 [label=q1 penwidth=3]"
                    )
                    self.assertIn(expected, styled)
                    self.assertIn("state_0 [label=q0]", styled)

    def test_highlighting_preserves_acceptance_and_parallel_symbols(self):
        automaton = NBA.from_components(
            states={"q"}, alphabet={"a", "b", "c"},
            transitions={("q", symbol, "q") for symbol in ("c", "b", "a")},
            initial_states={"q"}, accepting_states={"q"},
        )
        source = to_graphviz(
            automaton, highlighted_states=iter(["q"]),
            highlighted_transitions=iter([AutomatonTransition("q", "b", "q")]),
        ).source
        self.assertIn("state_0 [label=q penwidth=3 shape=square]", source)
        self.assertIn('state_0 -> state_0 [label="a, c"]', source)
        self.assertIn("state_0 -> state_0 [label=b penwidth=3]", source)

    def test_invalid_highlights_are_rejected(self):
        automaton = Automaton.from_components(
            states={"q"}, alphabet={"a"}, transitions=(),
        )
        with self.assertRaisesRegex(ValueError, "unknown states"):
            to_graphviz(automaton, highlighted_states={"missing"})
        # Both endpoints and the symbol exist, but this transition does not.
        with self.assertRaisesRegex(ValueError, "unknown transitions"):
            to_graphviz(
                automaton,
                highlighted_transitions={AutomatonTransition("q", "a", "q")},
            )

    def test_generalized_acceptance_sets_overlap_and_empty_requirements(self):
        automaton = GNBA.from_components(
            states={"q0", "q1", "q2"}, alphabet=(), transitions=(),
            accepting_sets=({"q0", "q1"}, {"q1", "q2"}, set()),
        )
        source = to_graphviz(automaton).source
        self.assertIn("F1 (empty)", source)
        self.assertIn('[F2, F3]', source)
        self.assertNotIn("xlabel", source)
        self.assertNotIn("fillcolor", source)
        self.assertNotIn("labelloc", source)
        self.assertIn("visit every set infinitely often", source)
        self.assertNotIn("F1 =", source)
        self.assertNotIn("{q0, q1}", source)
        self.assertNotIn("{q1, q2}", source)
        self.assertNotIn("shape=square", source)
        automaton.remove_accepting_set(set())
        automaton.remove_accepting_set({"q0", "q1"})
        automaton.remove_accepting_set({"q1", "q2"})
        source = to_graphviz(automaton).source
        self.assertIn("Generalized Büchi: no acceptance requirements", source)
        self.assertNotIn("xlabel", source)
        self.assertNotIn("(empty)", source)

    def test_empty_models_and_no_accepting_states(self):
        for model in (Automaton, FiniteAutomaton, NBA, GNBA):
            with self.subTest(model=model.__name__):
                source = to_graphviz(model()).source
                self.assertNotIn("state_", source)
                self.assertNotIn("__initial_", source)
                self.assertNotIn("shape=square", source)
        for model in (FiniteAutomaton, NBA):
            automaton = model.from_components(states={"q"}, alphabet=(), transitions=())
            self.assertNotIn("shape=square", to_graphviz(automaton).source)

    def test_non_string_values_and_deterministic_ordering(self):
        # These state values cannot be directly sorted against each other.
        states = [0, ("q", 1), frozenset({"q"})]
        symbols = [frozenset(), frozenset({"p"})]
        graphs = []
        for reverse in (False, True):
            automaton = GNBA()
            for state in reversed(states) if reverse else states:
                automaton.add_state(state, initial=True)
            for symbol in reversed(symbols) if reverse else symbols:
                automaton.add_symbol(symbol)
                automaton.add_transition(states[0], symbol, states[1])
            sets = [states[:2], states[1:]]
            for members in reversed(sets) if reverse else sets:
                automaton.add_accepting_set(members)
            graphs.append(to_graphviz(
                automaton,
                format_state=lambda state: f"q{states.index(state)}",
                format_symbol=lambda symbol: "{" + ", ".join(sorted(symbol)) + "}",
            ).source)
        self.assertEqual(graphs[0], graphs[1])
        self.assertIn('label="{p}, {}"', graphs[0])

    def test_graphviz_remains_an_optional_dependency(self):
        code = """
import sys
class BlockGraphviz:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'graphviz' or fullname.startswith('graphviz.'):
            raise ImportError('Graphviz deliberately blocked')
sys.meta_path.insert(0, BlockGraphviz())
import mocha
import mocha.visualisation
from mocha.visualisation import TransitionSystemOverlay
assert 'graphviz' not in sys.modules
try:
    from mocha.visualisation import to_automaton_graphviz
except ImportError as error:
    assert 'Graphviz deliberately blocked' in str(error)
else:
    raise AssertionError('Renderer should require the optional dependency')
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(shutil.which("dot"), "Graphviz executable is required")
class AutomatonRenderingTests(unittest.TestCase):
    def test_standard_shapes_and_arrows_in_rendered_svg(self):
        for model in (FiniteAutomaton, NBA):
            with self.subTest(model=model.__name__):
                automaton = model.from_components(
                    states={"q0", "q1"}, alphabet={"a"},
                    transitions={("q0", "a", "q1"), ("q1", "a", "q1")},
                    initial_states={"q0", "q1"}, accepting_states={"q1"},
                )
                graph = to_graphviz(automaton)
                nodes = {
                    text_labels(node)[0]: node for node in svg_groups(graph, "node")
                    if text_labels(node)
                }
                self.assertEqual(len(nodes["q0"].findall(f"{SVG}ellipse")), 1)
                self.assertEqual(len(nodes["q1"].findall(f"{SVG}ellipse")), 0)
                polygon = nodes["q1"].find(f"{SVG}polygon")
                self.assertIsNotNone(polygon)
                points = [
                    tuple(map(float, point.split(",")))
                    for point in polygon.get("points").split()
                ]
                xs, ys = zip(*points)
                self.assertAlmostEqual(max(xs) - min(xs), max(ys) - min(ys))
                edges = svg_groups(graph, "edge")
                self.assertEqual(len(edges), 4)
                self.assertEqual(sum(not text_labels(edge) for edge in edges), 2)

    def test_labels_are_literal_and_cannot_change_topology(self):
        values = ["a", "a:b", "__initial_0", "state_0", "<a & b>",
                  r"raw\n\N\G", 'a "quoted" value', "∅漢字"]
        automaton = NBA.from_components(
            states=values, alphabet=values,
            transitions={(value, value, value) for value in values},
            initial_states=values, accepting_states=values,
        )
        graph = to_graphviz(automaton)
        nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
        labels_by_id = {
            node.findtext(f"{SVG}title"): text_labels(node)[0] for node in nodes
        }
        self.assertCountEqual(labels_by_id.values(), values)
        initial_targets = []
        actual_transitions = []
        for edge in svg_groups(graph, "edge"):
            source, target = edge.findtext(f"{SVG}title").split("->")
            if text_labels(edge):
                actual_transitions.append((
                    labels_by_id[source], text_labels(edge)[0], labels_by_id[target],
                ))
            else:
                self.assertNotIn(source, labels_by_id)
                initial_targets.append(labels_by_id[target])
        self.assertCountEqual(initial_targets, values)
        self.assertCountEqual(actual_transitions, [(value, value, value) for value in values])

    def test_colliding_formatted_labels_preserve_distinct_states(self):
        automaton = Automaton.from_components(
            states={0, 1}, alphabet={2}, transitions={(0, 2, 1)}, initial_states={0},
        )
        graph = to_graphviz(
            automaton, format_state=lambda _: "same", format_symbol=lambda _: "<x>",
        )
        nodes = [node for node in svg_groups(graph, "node") if text_labels(node)]
        self.assertEqual(len(nodes), 2)
        self.assertEqual([text_labels(node) for node in nodes], [["same"], ["same"]])
        self.assertIn("state_0->state_1", [
            edge.findtext(f"{SVG}title") for edge in svg_groups(graph, "edge")
        ])

    def test_generalized_acceptance_markers_are_inside_states(self):
        value = r"<q>\n\N & q"
        automaton = GNBA.from_components(
            states={0}, alphabet=(), transitions=(), accepting_sets=({0},),
        )
        graph = to_graphviz(automaton, format_state=lambda _: value)
        nodes = svg_groups(graph, "node")
        self.assertCountEqual(text_labels(nodes[0]), [value, "[F1]"])
        # Both lines belong to the same circular node, with no external label.
        ellipse = nodes[0].find(f"{SVG}ellipse")
        centre_y = float(ellipse.get("cy"))
        radius_y = float(ellipse.get("ry"))
        for text in nodes[0].findall(f"{SVG}text"):
            self.assertLess(abs(float(text.get("y")) - centre_y), radius_y)
        legend = svg_groups(graph, "graph")[0]
        legend_labels = [
            "".join(text.itertext()) for text in legend.findall(f"{SVG}text")
        ]
        self.assertEqual(legend_labels, [])

    def test_generalized_acceptance_markers_preserve_all_memberships(self):
        automaton = GNBA.from_components(
            states={"q0", "q1", "q2", "q3"}, alphabet={"a"},
            transitions={("q0", "a", "q1")}, initial_states={"q0"},
            accepting_sets=({"q0", "q1"}, {"q1", "q2"}, {"q1"}),
        )
        graph = to_graphviz(automaton, highlighted_states={"q1"})
        nodes = {
            text_labels(node)[0]: node for node in svg_groups(graph, "node")
            if text_labels(node)
        }

        def fills(node):
            return {
                shape.get("fill").lower() for shape in node.iter()
                if shape.get("fill") not in (None, "none")
            }

        self.assertEqual(text_labels(nodes["q0"]), ["q0", "[F1]"])
        self.assertEqual(text_labels(nodes["q1"]), ["q1", "[F1, F2, F3]"])
        self.assertEqual(text_labels(nodes["q2"]), ["q2", "[F3]"])
        self.assertEqual(text_labels(nodes["q3"]), ["q3"])
        for node in nodes.values():
            self.assertEqual(fills(node), set())
        self.assertTrue(any(
            shape.get("stroke-width") == "3" for shape in nodes["q1"].iter()
        ))


if __name__ == "__main__":
    unittest.main()
