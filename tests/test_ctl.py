import unittest

from mocha.io import CTLParseError, parse_ctl
from mocha.algorithms import to_existential_normal_form
from mocha.logic import Formula, PathFormula, StateFormula, ltl
from mocha.logic.ctl import (
    Always, And, BooleanConstant, CTLFormula, CTLPathFormula, CTLStateFormula,
    Eventually, Exists, ForAll, Next, Not, Proposition, Until, WeakUntil,
    is_ctl_formula, propositions,
)


class CTLFormulaTypeTests(unittest.TestCase):
    def test_state_and_path_categories_are_distinct(self) -> None:
        state = parse_ctl('EX "p"')
        self.assertIsInstance(state, Formula)
        self.assertIsInstance(state, CTLFormula)
        self.assertIsInstance(state, StateFormula)
        self.assertIsInstance(state, CTLStateFormula)
        self.assertNotIsInstance(state, PathFormula)
        self.assertIsInstance(state.operand, PathFormula)
        self.assertIsInstance(state.operand, CTLPathFormula)
        self.assertNotIsInstance(state.operand, StateFormula)
        self.assertIsInstance(state.operand.operand, StateFormula)

        ltl_formula = ltl.Always(ltl.Proposition("p"))
        self.assertIsInstance(ltl_formula, PathFormula)
        self.assertNotIsInstance(ltl_formula, StateFormula)

    def test_parser_separates_quantifiers_from_temporal_operators(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        for source, expected in (
            ('EX "p"', Exists(Next(p))),
            ('EG "p"', Exists(Always(p))),
            ('EF "p"', Exists(Eventually(p))),
            ('E("p" U "q")', Exists(Until(p, q))),
            ('E("p" W "q")', Exists(WeakUntil(p, q))),
            ('AX "p"', ForAll(Next(p))),
            ('AF "p"', ForAll(Eventually(p))),
            ('AG "p"', ForAll(Always(p))),
            ('A("p" U "q")', ForAll(Until(p, q))),
            ('A("p" W "q")', ForAll(WeakUntil(p, q))),
            ('AG EX "p"', ForAll(Always(Exists(Next(p))))),
        ):
            with self.subTest(source=source):
                self.assertEqual(parse_ctl(source), expected)
                self.assertEqual(parse_ctl(expected.to_source()), expected)
                self.assertTrue(is_ctl_formula(expected))
                self.assertEqual(hash(parse_ctl(source)), hash(expected))

    def test_constructors_enforce_the_ctl_grammar(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        path = Next(p)
        for construct in (
            lambda: Not(path),
            lambda: And(p, path),
            lambda: And(path, p),
            lambda: Next(path),
            lambda: Always(path),
            lambda: Eventually(path),
            lambda: Until(p, path),
            lambda: Until(path, q),
            lambda: WeakUntil(p, path),
            lambda: WeakUntil(path, q),
            lambda: Exists(p),
            lambda: ForAll(p),
            lambda: Exists(ltl.Next(ltl.Proposition("p"))),
            lambda: ForAll(ltl.Always(ltl.Proposition("p"))),
        ):
            with self.subTest(construct=construct), self.assertRaises(TypeError):
                construct()

    def test_fragment_check_rejects_path_and_unknown_formulae(self) -> None:
        p = Proposition("p")
        for formula in (
            Next(p), Always(p), Eventually(p), Until(p, p), WeakUntil(p, p),
            ltl.Proposition("p"), ltl.Always(ltl.Proposition("p")),
            CTLStateFormula(), Exists(CTLPathFormula()), ForAll(CTLPathFormula()),
        ):
            with self.subTest(node=type(formula).__name__):
                self.assertFalse(is_ctl_formula(formula))
        self.assertFalse(is_ctl_formula(And(p, CTLStateFormula())))
        self.assertFalse(is_ctl_formula(Exists(Next(CTLStateFormula()))))
        with self.assertRaisesRegex(TypeError, "state formula"):
            to_existential_normal_form(Next(p))
        with self.assertRaisesRegex(ValueError, "CTL fragment"):
            to_existential_normal_form(ForAll(CTLPathFormula()))

    def test_propositions_and_formatting_traverse_path_nodes(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        formula = ForAll(Always(And(p, Exists(Until(p, q)))))
        self.assertEqual(propositions(formula), frozenset({"p", "q"}))
        self.assertEqual(propositions(formula.operand), frozenset({"p", "q"}))
        self.assertEqual(str(formula), "∀□(p ∧ ∃(p U q))")
        self.assertEqual(str(Until(p, q)), "(p U q)")
        self.assertEqual(str(Next(And(p, q))), "◯(p ∧ q)")


class CTLParserTests(unittest.TestCase):
    def test_compact_and_spaced_operators_share_the_same_syntax(self) -> None:
        for quantifier in ("E", "A"):
            for operator in ("X", "F", "G"):
                compact = f'{quantifier}{operator}AGEX"p"'
                spaced = f'{quantifier} {operator} A G E X "p"'
                with self.subTest(source=compact):
                    self.assertEqual(parse_ctl(compact), parse_ctl(spaced))
                    self.assertEqual(parse_ctl(f'"{quantifier}{operator}"'),
                                     Proposition(quantifier + operator))
                    self.assertEqual(str(Proposition(quantifier + operator)),
                                     f'"{quantifier}{operator}"')
        with self.assertRaises(CTLParseError) as error:
            parse_ctl('EXX "p"')
        self.assertEqual((error.exception.line, error.exception.column), (1, 3))

    def test_parses_existential_eventually_and_weak_until(self) -> None:
        p, q = Proposition("p"), Proposition("q")
        for source, expected in (
            ('EF "p"', Exists(Eventually(p))),
            ('E F "p"', Exists(Eventually(p))),
            ('∃◇"p"', Exists(Eventually(p))),
            ('E("p" W "q")', Exists(WeakUntil(p, q))),
            ('∃("p" W "q")', Exists(WeakUntil(p, q))),
            ('EF "p" & EX "q"', And(Exists(Eventually(p)), Exists(Next(q)))),
            ('E(EF "p" W AG "q")', Exists(WeakUntil(Exists(Eventually(p)), ForAll(Always(q))))),
        ):
            with self.subTest(source=source):
                self.assertEqual(parse_ctl(source), expected)
                self.assertEqual(parse_ctl(expected.to_source()), expected)

    def test_rejects_path_formulae_outside_the_ctl_fragment(self) -> None:
        for source in (
            'X "p"', 'G "p"', '"p" U "q"',
            'E X X "p"', 'A G F "p"',
            'E(G "p" & F "q")', 'A("p" U G "q")',
        ):
            with self.subTest(source=source), self.assertRaises(CTLParseError):
                parse_ctl(source)

    def test_parses_existential_normal_form(self) -> None:
        self.assertEqual(
            parse_ctl('EX "ready" & EG !"failed"'),
            And(Exists(Next(Proposition("ready"))), Exists(Always(Not(Proposition("failed"))))),
        )
        self.assertEqual(
            parse_ctl('E("ready" U ("done" & true))'),
            Exists(Until(Proposition("ready"), And(Proposition("done"), BooleanConstant(True)))),
        )
        self.assertEqual(
            parse_ctl('∃◯"ready" ∧ ∃□¬"failed"'),
            parse_ctl('EX "ready" & EG !"failed"'),
        )
        self.assertEqual(parse_ctl('E X "ready"'), Exists(Next(Proposition("ready"))))
        self.assertEqual(parse_ctl('E G "ready"'), Exists(Always(Proposition("ready"))))
        self.assertEqual(
            parse_ctl('∃("ready" U ∃◯"done")'),
            Exists(Until(Proposition("ready"), Exists(Next(Proposition("done"))))),
        )

    def test_preserves_precedence_and_nested_until(self) -> None:
        self.assertEqual(
            parse_ctl('EX ("p" & "q")'),
            Exists(Next(And(Proposition("p"), Proposition("q")))),
        )
        self.assertEqual(
            parse_ctl('E("p" & "q" U E("r" U "s"))'),
            Exists(Until(
                And(Proposition("p"), Proposition("q")),
                Exists(Until(Proposition("r"), Proposition("s"))),
            )),
        )

    def test_parses_universal_formulas(self) -> None:
        for source, expected in (
            ('AX "ready"', ForAll(Next(Proposition("ready")))),
            ('A X "ready"', ForAll(Next(Proposition("ready")))),
            ('∀◯"ready"', ForAll(Next(Proposition("ready")))),
            ('AF "done"', ForAll(Eventually(Proposition("done")))),
            ('A F "done"', ForAll(Eventually(Proposition("done")))),
            ('∀◇"done"', ForAll(Eventually(Proposition("done")))),
            ('AG !"failed"', ForAll(Always(Not(Proposition("failed"))))),
            ('A G !"failed"', ForAll(Always(Not(Proposition("failed"))))),
            ('∀□¬"failed"', ForAll(Always(Not(Proposition("failed"))))),
            ('A("ready" U "done")', ForAll(Until(Proposition("ready"), Proposition("done")))),
            ('∀("ready" U "done")', ForAll(Until(Proposition("ready"), Proposition("done")))),
            ('A("ready" W "done")', ForAll(WeakUntil(Proposition("ready"), Proposition("done")))),
            ('∀("ready" W "done")', ForAll(WeakUntil(Proposition("ready"), Proposition("done")))),
        ):
            with self.subTest(source=source):
                self.assertEqual(parse_ctl(source), expected)
        self.assertEqual(
            parse_ctl('AG ("ready" & EX "done")'),
            ForAll(Always(And(Proposition("ready"), Exists(Next(Proposition("done")))))),
        )
        self.assertEqual(
            parse_ctl('A(AX "ready" U AG "done")'),
            ForAll(Until(ForAll(Next(Proposition("ready"))), ForAll(Always(Proposition("done"))))),
        )
        self.assertEqual(str(ForAll(Always(Not(Proposition("failed"))))), '∀□¬failed')

    def test_source_round_trips_every_node_and_reserved_proposition(self) -> None:
        formulas = (
            BooleanConstant(False),
            Proposition("EX"),
            Proposition("U"),
            Proposition('a"b'),
            Not(And(Proposition("p"), Proposition("q"))),
            Exists(Next(Exists(Always(Proposition("p"))))),
            Exists(Eventually(Proposition("EF"))),
            Exists(WeakUntil(Not(Proposition("p")), Exists(Eventually(Proposition("q"))))),
            ForAll(Always(And(Proposition("p"), Proposition("q")))),
            ForAll(Always(Exists(Until(Proposition("p"), Proposition("q"))))),
            ForAll(Next(ForAll(Eventually(Proposition("p"))))),
            ForAll(Until(
                And(Proposition("p"), Proposition("q")),
                ForAll(WeakUntil(Proposition("r"), Proposition("s"))),
            )),
            Proposition("AG"),
            Proposition("W"),
            And(Proposition("p"), And(Proposition("q"), Proposition("r"))),
            Exists(Until(
                And(Proposition("p"), Proposition("q")),
                Exists(Until(Proposition("r"), Proposition("s"))),
            )),
        )
        for formula in formulas:
            with self.subTest(formula=formula):
                self.assertEqual(parse_ctl(formula.to_source()), formula)
        self.assertEqual(str(parse_ctl('EX ("p" & "q")')), '∃◯(p ∧ q)')

    def test_validates_propositions(self) -> None:
        formula = parse_ctl('E("p" U "q")', atomic_propositions={"p", "q"})
        self.assertEqual(propositions(formula), frozenset({"p", "q"}))
        with self.assertRaisesRegex(ValueError, "Unknown atomic propositions.*q"):
            parse_ctl('EX "q"', atomic_propositions={"p"})

    def test_rejects_malformed_formula_with_location(self) -> None:
        for source in ('', 'p', 'EX', 'AG', 'A', 'AF', 'AX', 'EF', 'E F', 'E("p" "q")', 'E("p" U)', 'E("p" W)', 'E("p" "W" "q")', 'A("p" & "q")', 'A("p" W)'):
            with self.subTest(source=source), self.assertRaises(CTLParseError):
                parse_ctl(source)
        with self.assertRaises(CTLParseError) as error:
            parse_ctl('EX "p"\n& )')
        self.assertEqual((error.exception.line, error.exception.column), (2, 3))
        self.assertEqual(parse_ctl('"E"'), Proposition("E"))
        self.assertEqual(parse_ctl('"U"'), Proposition("U"))


if __name__ == "__main__":
    unittest.main()
