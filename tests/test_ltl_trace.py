import unittest

from mocha.algorithms.ltl_transformations import (
    LTLRewriteStep,
    normalize_ltl,
    to_release_pnf,
    to_weak_until_pnf,
    trace_normalize_ltl,
    trace_release_pnf,
    trace_weak_until_pnf,
)
from mocha.io import parse_ltl
from mocha.algorithms.trace import AlgorithmTrace


def _at_path(formula, path):
    for component in path:
        formula = getattr(formula, component)
    return formula


class LTLTraceTests(unittest.TestCase):
    def test_traces_show_full_formulas_and_local_rewrites(self) -> None:
        formula = parse_ltl('!G(("a" U "b") | X "c")')
        for transform, trace_transform in (
            (normalize_ltl, trace_normalize_ltl),
            (to_weak_until_pnf, trace_weak_until_pnf),
            (to_release_pnf, trace_release_pnf),
        ):
            with self.subTest(transform=transform.__name__):
                trace = trace_transform(formula)
                self.assertIsInstance(trace, AlgorithmTrace)
                self.assertEqual(trace.result, transform(formula))
                self.assertEqual(
                    trace.steps[0],
                    LTLRewriteStep(0, "initial", formula, (), None, None),
                )
                self.assertEqual(trace.steps[-1].formula, trace.result)
                self.assertGreater(len(trace.steps), 1)

                for previous, step in zip(trace.steps, trace.steps[1:]):
                    self.assertEqual(step.iteration, previous.iteration + 1)
                    self.assertNotEqual(step.formula, previous.formula)
                    self.assertEqual(
                        _at_path(previous.formula, step.path), step.before
                    )
                    self.assertEqual(_at_path(step.formula, step.path), step.after)
                    self.assertNotEqual(step.before, step.after)
                    self.assertEqual(parse_ltl(step.formula.to_source()), step.formula)

                reported = []
                self.assertEqual(
                    transform(formula, on_step=reported.append), trace.result
                )
                self.assertEqual(tuple(reported), trace.steps)

    def test_pnf_trace_names_the_book_rewrite_rules(self) -> None:
        formula = parse_ltl('!G(("a" U "b") | X "c")')
        expected = ["initial", "negate_always", "de_morgan_or",
                    "negate_until", "negate_next"]
        self.assertEqual(
            [step.rule for step in trace_weak_until_pnf(formula).steps], expected
        )
        self.assertEqual(
            [step.rule for step in trace_release_pnf(formula).steps], expected
        )

    def test_already_normalized_formula_has_only_initial_snapshot(self) -> None:
        formula = parse_ltl('"p" U "q"')
        for trace_transform in (
            trace_normalize_ltl, trace_weak_until_pnf, trace_release_pnf,
        ):
            trace = trace_transform(formula)
            self.assertEqual(trace.result, formula)
            self.assertEqual(
                trace.steps,
                (LTLRewriteStep(0, "initial", formula, (), None, None),),
            )


if __name__ == "__main__":
    unittest.main()
