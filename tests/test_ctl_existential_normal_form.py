import unittest
from itertools import product

from mocha.algorithms.ctl_transformations import (
    CTLRewriteStep, to_existential_normal_form,
    trace_existential_normal_form,
)
from mocha.io import parse_ctl
from mocha.algorithms.trace import AlgorithmTrace
from mocha.logic.ctl import (
    Always, And, BooleanConstant, CTLFormula,
    Eventually, Exists, ForAll, Next, Not, Proposition, Until, WeakUntil,
)


def _satisfying_states(
    formula: CTLFormula,
    successors: dict[str, frozenset[str]],
    labels: dict[str, frozenset[str]],
) -> frozenset[str]:
    """Evaluate CTL directly by least/greatest fixed points on a total graph."""
    states = frozenset(successors)

    def exists_next(target: frozenset[str]) -> frozenset[str]:
        return frozenset(state for state in states if successors[state] & target)

    def all_next(target: frozenset[str]) -> frozenset[str]:
        return frozenset(state for state in states if successors[state] <= target)

    def fixed_point(seed: frozenset[str], update) -> frozenset[str]:
        current = seed
        while True:
            following = update(current)
            if following == current:
                return current
            current = following

    if isinstance(formula, BooleanConstant):
        return states if formula.value else frozenset()
    if isinstance(formula, Proposition):
        return frozenset(state for state in states if formula.name in labels[state])
    if isinstance(formula, Not):
        return states - _satisfying_states(formula.operand, successors, labels)
    if isinstance(formula, And):
        return (_satisfying_states(formula.left, successors, labels)
                & _satisfying_states(formula.right, successors, labels))
    if isinstance(formula, (Exists, ForAll)) and isinstance(formula.operand, (Next, Always, Eventually)):
        path = formula.operand
        operand = _satisfying_states(path.operand, successors, labels)
        existential = isinstance(formula, Exists)
        if isinstance(path, Next) and existential:
            return exists_next(operand)
        if isinstance(path, Next):
            return all_next(operand)
        if isinstance(path, Always) and existential:
            return fixed_point(states, lambda found: operand & exists_next(found))
        if isinstance(path, Always):
            return fixed_point(states, lambda found: operand & all_next(found))
        if existential:
            return fixed_point(frozenset(), lambda found: operand | exists_next(found))
        return fixed_point(frozenset(), lambda found: operand | all_next(found))
    if isinstance(formula, (Exists, ForAll)) and isinstance(formula.operand, (Until, WeakUntil)):
        path = formula.operand
        left = _satisfying_states(path.left, successors, labels)
        right = _satisfying_states(path.right, successors, labels)
        if isinstance(formula, Exists):
            seed = states if isinstance(path, WeakUntil) else frozenset()
            return fixed_point(seed, lambda found: right | (left & exists_next(found)))
        if isinstance(path, Until):
            return fixed_point(frozenset(), lambda found: right | (left & all_next(found)))
        return fixed_point(states, lambda found: right | (left & all_next(found)))
    raise TypeError(type(formula))


def _assert_enf(test: unittest.TestCase, formula: CTLFormula) -> None:
    test.assertIsInstance(formula, (BooleanConstant, Proposition, Not, And, Exists))
    if isinstance(formula, BooleanConstant):
        test.assertTrue(formula.value)
    elif isinstance(formula, Not):
        _assert_enf(test, formula.operand)
    elif isinstance(formula, And):
        _assert_enf(test, formula.left)
        _assert_enf(test, formula.right)
    elif isinstance(formula, Exists):
        path = formula.operand
        test.assertIsInstance(path, (Next, Always, Until))
        if isinstance(path, (Next, Always)):
            _assert_enf(test, path.operand)
        elif isinstance(path, Until):
            _assert_enf(test, path.left)
            _assert_enf(test, path.right)


class CTLExistentialNormalFormTests(unittest.TestCase):
    def test_lecture_rewrites(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        self.assertEqual(
            to_existential_normal_form(Exists(Eventually(p))),
            Exists(Until(BooleanConstant(True), p)),
        )
        self.assertEqual(
            to_existential_normal_form(Exists(WeakUntil(p, q))),
            Not(And(Not(Exists(Until(p, q))), Not(Exists(Always(p))))),
        )
        self.assertEqual(
            to_existential_normal_form(ForAll(Next(p))),
            Not(Exists(Next(Not(p)))),
        )
        self.assertEqual(
            to_existential_normal_form(ForAll(Eventually(p))),
            Not(Exists(Always(Not(p)))),
        )
        self.assertEqual(
            to_existential_normal_form(ForAll(Always(p))),
            Not(Exists(Until(BooleanConstant(True), Not(p)))),
        )
        self.assertEqual(
            to_existential_normal_form(ForAll(Until(p, q))),
            And(
                Not(Exists(Until(Not(q), And(Not(p), Not(q))))),
                Not(Exists(Always(Not(q)))),
            ),
        )
        self.assertEqual(
            to_existential_normal_form(ForAll(WeakUntil(p, q))),
            Not(Exists(Until(And(p, Not(q)), And(Not(p), Not(q))))),
        )
        self.assertEqual(to_existential_normal_form(BooleanConstant(False)), Not(BooleanConstant(True)))

    def test_normal_form_is_idempotent_and_semantically_equivalent(self) -> None:
        formulas = tuple(parse_ctl(source) for source in (
            'AX "p"', 'AF "q"', 'AG "p"', 'A("p" U "q")',
            'A("p" W "q")', 'AG ("p" & EX "q")',
            'A(AX "p" U AF "q")', '!(A("p" W "q") & false)',
            'EX (AG "p")', 'E("p" U A("q" W "p"))',
            'EF "p"', 'E("p" W "q")', 'E("p" W false)',
            'E(false W "q")', 'EF false', 'EF true',
            'AG EF "p"', 'E(EF "p" W AF "q")',
            'EF E("p" W "q")',
        ))
        graphs = (
            {"s0": frozenset({"s1", "s2"}), "s1": frozenset({"s1"}), "s2": frozenset({"s2"})},
            {"s0": frozenset({"s1"}), "s1": frozenset({"s2"}), "s2": frozenset({"s2"})},
            {"s0": frozenset({"s1"}), "s1": frozenset({"s0", "s2"}), "s2": frozenset({"s2"})},
        )
        valuations = (frozenset(), frozenset({"p"}), frozenset({"q"}), frozenset({"p", "q"}))
        for formula in formulas:
            normalized = to_existential_normal_form(formula)
            _assert_enf(self, normalized)
            self.assertEqual(to_existential_normal_form(normalized), normalized)
            self.assertEqual(parse_ctl(normalized.to_source()), normalized)
            for graph in graphs:
                for assignment in product(valuations, repeat=3):
                    labels = dict(zip(graph, assignment))
                    self.assertEqual(
                        _satisfying_states(formula, graph, labels),
                        _satisfying_states(normalized, graph, labels),
                        msg=f"{formula} with {graph} and {labels}",
                    )

    def test_trace_records_existential_eventually_and_weak_until_rewrites(self) -> None:
        formula = parse_ctl('EX (EF "p" & E("p" W "q"))')
        trace = trace_existential_normal_form(formula)
        self.assertEqual(
            [step.rule for step in trace.steps],
            ["initial", "eliminate_ef", "eliminate_ew"],
        )
        self.assertEqual(trace.steps[1].path, ("operand", "operand", "left"))
        self.assertEqual(trace.steps[2].path, ("operand", "operand", "right"))
        self.assertEqual(trace.steps[1].before, parse_ctl('EF "p"'))
        self.assertEqual(trace.steps[1].after, parse_ctl('E(true U "p")'))
        self.assertEqual(trace.steps[2].before, parse_ctl('E("p" W "q")'))
        self.assertEqual(trace.steps[2].after, parse_ctl('!( !E("p" U "q") & !EG "p")'))
        _assert_enf(self, trace.result)

    def test_trace_records_local_rewrites_in_full_formulas(self) -> None:
        formula = parse_ctl('EX (AG "p" & AX false)')
        steps: list[CTLRewriteStep] = []
        result = to_existential_normal_form(formula, on_step=steps.append)
        trace = trace_existential_normal_form(formula)
        self.assertIsInstance(trace, AlgorithmTrace)
        self.assertEqual(trace.result, result)
        self.assertEqual(trace.steps, tuple(steps))
        self.assertEqual(trace.steps[0], CTLRewriteStep(0, "initial", formula, (), None, None))
        self.assertEqual(trace.steps[-1].formula, result)
        self.assertEqual(
            [step.rule for step in trace.steps],
            ["initial", "eliminate_ag", "eliminate_ax", "eliminate_false", "double_negation"],
        )
        self.assertEqual(trace.steps[1].path, ("operand", "operand", "left"))
        for previous, current in zip(trace.steps, trace.steps[1:]):
            before: CTLFormula = previous.formula
            after: CTLFormula = current.formula
            for component in current.path:
                before = getattr(before, component)
                after = getattr(after, component)
            self.assertEqual(before, current.before)
            self.assertEqual(after, current.after)

        core = parse_ctl('E("p" U "q")')
        self.assertEqual(
            trace_existential_normal_form(core).steps,
            (CTLRewriteStep(0, "initial", core, (), None, None),),
        )


if __name__ == "__main__":
    unittest.main()
