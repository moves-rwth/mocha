import unittest
from itertools import product

from mocha import (
    normalize_ltl, to_release_pnf,
    to_weak_until_pnf,
)
from mocha.io import LTLParseError, parse_ltl
from mocha.logic.ltl import (
    Always, And, BooleanConstant, Equiv, Eventually, Implies, Next, Not,
    Or, Proposition, Release, Until, WeakUntil, propositions,
)
from mocha.models import TransitionSystem


class LTLParserTests(unittest.TestCase):
    def test_adjacent_unary_temporal_operators(self) -> None:
        for compact, spaced in (
            ('XX"p"', 'X X "p"'),
            ('XXX("p")', 'X X X "p"'),
            ('GF("p")', 'G F "p"'),
            ('FF !"p"', 'F F !"p"'),
            ('GG "p"', 'G G "p"'),
            ('XFG("p" & "q") U XX!"r"', 'X F G ("p" & "q") U X X !"r"'),
            ('XX◯"p"', 'X X X "p"'),
        ):
            with self.subTest(compact=compact):
                self.assertEqual(parse_ltl(compact), parse_ltl(spaced))
        self.assertEqual(propositions(parse_ltl('XX "p"', atomic_propositions={"p"})), {"p"})

    def test_propositions_require_quotes(self) -> None:
        for name in ("p", "ready", "Xray", "XXp", "GF_ready", "XX1", "prefixXX"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(LTLParseError, "double quotes"):
                    parse_ltl(name)
                self.assertEqual(parse_ltl(f'"{name}"'), Proposition(name))
        with self.assertRaisesRegex(LTLParseError, "double quotes"):
            parse_ltl("p", atomic_propositions={"p"})
        with self.assertRaises(LTLParseError) as error:
            parse_ltl('X"p"\n & ready')
        self.assertEqual((error.exception.line, error.exception.column), (2, 4))
        self.assertEqual(parse_ltl('"XX"', atomic_propositions={"XX"}), Proposition("XX"))

    def test_quoted_constants_are_propositions(self) -> None:
        for name, value in (("true", True), ("false", False)):
            self.assertEqual(parse_ltl(name), BooleanConstant(value))
            self.assertEqual(parse_ltl(f'"{name}"'), Proposition(name))

    def test_operator_chain_requires_an_operand_with_correct_location(self) -> None:
        for source, location in (("XX", (1, 3)), ("GF()", (1, 4)), ('XX\n& "p"', (2, 1))):
            with self.subTest(source=source):
                with self.assertRaises(LTLParseError) as error:
                    parse_ltl(source)
                self.assertEqual((error.exception.line, error.exception.column), location)

    def test_parses_temporal_and_boolean_operators(self) -> None:
        self.assertEqual(
            parse_ltl('G("request" -> F "grant received")'),
            Always(Implies(
                Proposition("request"),
                Eventually(Proposition("grant received")),
            )),
        )
        self.assertEqual(
            parse_ltl('X !"p" U ("q" R false)'),
            Until(
                Next(Not(Proposition("p"))),
                Release(Proposition("q"), BooleanConstant(False)),
            ),
        )
        self.assertEqual(
            parse_ltl('true && "p" || "q" <-> !false'),
            Equiv(
                Or(And(BooleanConstant(True), Proposition("p")), Proposition("q")),
                Not(BooleanConstant(False)),
            ),
        )

    def test_associativity_and_quoted_reserved_names(self) -> None:
        self.assertEqual(
            parse_ltl('"p" -> "q" -> "G"'),
            Implies(Proposition("p"), Implies(Proposition("q"), Proposition("G"))),
        )
        self.assertEqual(
            parse_ltl('"p" U "q" R "r"'),
            Until(Proposition("p"), Release(Proposition("q"), Proposition("r"))),
        )
        self.assertEqual(
            parse_ltl('"p" W "q" U "r"'),
            WeakUntil(Proposition("p"), Until(Proposition("q"), Proposition("r"))),
        )
        self.assertEqual(parse_ltl('"a\\\"b"'), Proposition('a"b'))

    def test_validates_against_transition_system_vocabulary(self) -> None:
        system = TransitionSystem.from_components(
            states={"s"}, actions=set(), transitions=set(),
            atomic_propositions={"request", "grant received"},
        )
        formula = parse_ltl(
            'G("request" -> F "grant received")',
            atomic_propositions=system.atomic_propositions,
        )
        self.assertEqual(propositions(formula), system.atomic_propositions)
        with self.assertRaisesRegex(ValueError, "Unknown atomic propositions.*missing"):
            parse_ltl('F "missing"', atomic_propositions=system.atomic_propositions)
        with self.assertRaisesRegex(ValueError, "Unknown atomic propositions"):
            parse_ltl('"p"', atomic_propositions=())

    def test_rejects_malformed_formulas_with_location(self) -> None:
        for source in ("", '"p" &', '("p" | "q"', '"p" "q"', '"p" @ "q"', "X", "()", '"bad\\q"'):
            with self.subTest(source=source), self.assertRaises(LTLParseError):
                parse_ltl(source)
        with self.assertRaises(LTLParseError) as error:
            parse_ltl('G "p"\n& )')
        self.assertEqual((error.exception.line, error.exception.column), (2, 3))


class LTLFormattingTests(unittest.TestCase):
    def test_uses_textbook_symbols(self) -> None:
        self.assertEqual(
            str(parse_ltl('G("request" -> F "grant received")')),
            '□(request → ◇"grant received")',
        )
        self.assertEqual(str(parse_ltl('X ("p" U "q")')), "◯(p U q)")
        self.assertEqual(str(parse_ltl('("p" W "q") U "r"')), "(p W q) U r")
        self.assertEqual(str(parse_ltl('"p" R "q" <-> !false')), "p R q ↔ ¬false")
        self.assertEqual(
            str(normalize_ltl(parse_ltl('G "p"'))), "¬(true U ¬p)"
        )

    def test_serialization_quotes_all_propositions(self) -> None:
        for name in ("p", "request", "true", "G", "W", "XX", "GF", "XFG",
                     "grant received", 'a"b', "a\\b", "a\nb", "Δ", ""):
            with self.subTest(name=name):
                self.assertTrue(Proposition(name).to_source().startswith('"'))
                self.assertEqual(parse_ltl(Proposition(name).to_source()), Proposition(name))

    def test_display_and_serialization_are_distinct(self) -> None:
        formula = parse_ltl('XX"p" & GF"ready"')
        self.assertEqual(str(formula), "◯◯p ∧ □◇ready")
        self.assertEqual(formula.to_source(), '◯◯"p" ∧ □◇"ready"')
        self.assertEqual(parse_ltl(formula.to_source()), formula)
        with self.assertRaises(LTLParseError):
            parse_ltl(str(formula))

    def test_serialized_form_round_trips_with_required_parentheses(self) -> None:
        sources = (
            '"p" & ("q" & "r")', '("p" -> "q") -> "r"', '"p" U ("q" R "r")',
            '("p" U "q") R "r"', '("p" W "q") U "r"', '"p" W ("q" R "r")',
            '"p" <-> ("q" <-> "r")',
            'G("p" -> F "grant received")', '!("p" | "q")', "X !false",
            '"p" | "q"', '"p" && "q"', "true", "false",
        )
        for source in sources:
            with self.subTest(source=source):
                formula = parse_ltl(source)
                self.assertEqual(parse_ltl(formula.to_source()), formula)

    def test_accepts_textbook_unicode_input(self) -> None:
        self.assertEqual(
            parse_ltl('□("p" → ◇"grant received") ∧ ◯"q"'),
            parse_ltl('G("p" -> F "grant received") & X "q"'),
        )
        self.assertEqual(parse_ltl('○"p" ↔ ¬"q" ∨ "r"'),
                         parse_ltl('X "p" <-> !"q" | "r"'))


def _evaluate(formula, word, loop_start, position):
    """Evaluate directly on an infinite prefix followed by a repeated suffix."""
    def future():
        current = position
        for _ in word:
            yield current
            current = current + 1 if current + 1 < len(word) else loop_start

    if isinstance(formula, BooleanConstant):
        return formula.value
    if isinstance(formula, Proposition):
        return formula.name in word[position]
    if isinstance(formula, Not):
        return not _evaluate(formula.operand, word, loop_start, position)
    if isinstance(formula, Next):
        next_position = position + 1 if position + 1 < len(word) else loop_start
        return _evaluate(formula.operand, word, loop_start, next_position)
    if isinstance(formula, And):
        return all(_evaluate(side, word, loop_start, position)
                   for side in (formula.left, formula.right))
    if isinstance(formula, Or):
        return any(_evaluate(side, word, loop_start, position)
                   for side in (formula.left, formula.right))
    if isinstance(formula, Implies):
        return (not _evaluate(formula.left, word, loop_start, position)
                or _evaluate(formula.right, word, loop_start, position))
    if isinstance(formula, Equiv):
        return (_evaluate(formula.left, word, loop_start, position)
                == _evaluate(formula.right, word, loop_start, position))
    if isinstance(formula, Eventually):
        return any(_evaluate(formula.operand, word, loop_start, step)
                   for step in future())
    if isinstance(formula, Always):
        return all(_evaluate(formula.operand, word, loop_start, step)
                   for step in future())
    if isinstance(formula, Until):
        for step in future():
            if _evaluate(formula.right, word, loop_start, step):
                return True
            if not _evaluate(formula.left, word, loop_start, step):
                return False
        return False
    if isinstance(formula, WeakUntil):
        for step in future():
            if _evaluate(formula.right, word, loop_start, step):
                return True
            if not _evaluate(formula.left, word, loop_start, step):
                return False
        return True
    if isinstance(formula, Release):
        for step in future():
            if not _evaluate(formula.right, word, loop_start, step):
                return False
            if _evaluate(formula.left, word, loop_start, step):
                return True
        return True
    raise TypeError(type(formula))


class LTLNormalizationTests(unittest.TestCase):
    def test_rewrites_derived_operators_into_requested_basis(self) -> None:
        self.assertEqual(
            normalize_ltl(parse_ltl('G("p" -> F "q")')),
            Not(Until(
                BooleanConstant(True),
                And(Proposition("p"), Not(Until(
                    BooleanConstant(True), Proposition("q")
                ))),
            )),
        )
        self.assertEqual(
            normalize_ltl(parse_ltl('"p" | "q"')),
            Not(And(Not(Proposition("p")), Not(Proposition("q")))),
        )
        self.assertEqual(
            normalize_ltl(parse_ltl('"p" <-> "q"')),
            And(
                Not(And(Proposition("p"), Not(Proposition("q")))),
                Not(And(Proposition("q"), Not(Proposition("p")))),
            ),
        )
        self.assertEqual(
            normalize_ltl(parse_ltl('"p" R "q"')),
            Not(Until(Not(Proposition("p")), Not(Proposition("q")))),
        )
        self.assertEqual(
            normalize_ltl(parse_ltl('"p" W "q"')),
            Not(Until(
                And(Proposition("p"), Not(Proposition("q"))),
                And(Not(Proposition("p")), Not(Proposition("q"))),
            )),
        )
        self.assertEqual(
            normalize_ltl(parse_ltl('!G "p"')),
            Until(BooleanConstant(True), Not(Proposition("p"))),
        )

    def test_normalization_preserves_lasso_semantics_and_is_idempotent(self) -> None:
        formulas = [parse_ltl(source) for source in (
            'G("p" -> F "q")', '"p" R "q"', '!("p" U "q")',
            'X F "p" <-> G "q"', 'F G "p"', '!("p" R ("q" | X "p"))',
            '"p" W "q"', '!("p" W "q")', 'G("p" W X "q")',
            '!false & ("p" <-> !"q")',
        )]
        valuations = (frozenset(), frozenset({"p"}), frozenset({"q"}),
                      frozenset({"p", "q"}))
        for formula in formulas:
            normalized = normalize_ltl(formula)
            self.assertEqual(normalize_ltl(normalized), normalized)
            self._assert_basic_nodes(normalized)
            self.assertEqual(propositions(normalized), propositions(formula))
            for word in product(valuations, repeat=3):
                for loop_start in (0, 1, 2):
                    for position in range(len(word)):
                        with self.subTest(formula=formula, word=word,
                                          loop_start=loop_start, position=position):
                            self.assertEqual(
                                _evaluate(formula, word, loop_start, position),
                                _evaluate(normalized, word, loop_start, position),
                            )

    def _assert_basic_nodes(self, formula) -> None:
        self.assertIsInstance(
            formula,
            (BooleanConstant, Proposition, Not, Next, And, Until),
        )
        if isinstance(formula, (Not, Next)):
            self._assert_basic_nodes(formula.operand)
        elif isinstance(formula, (And, Until)):
            self._assert_basic_nodes(formula.left)
            self._assert_basic_nodes(formula.right)

    def test_weak_until_allows_right_side_never_to_hold(self) -> None:
        weak = parse_ltl('"p" W "q"')
        strong = parse_ltl('"p" U "q"')
        always_p = (frozenset({"p"}),)
        self.assertTrue(_evaluate(weak, always_p, 0, 0))
        self.assertFalse(_evaluate(strong, always_p, 0, 0))
        self.assertTrue(_evaluate(weak, (frozenset({"q"}),), 0, 0))
        self.assertFalse(_evaluate(weak, (frozenset(),), 0, 0))


class LTLPositiveNormalFormTests(unittest.TestCase):
    def test_matches_the_book_example_in_both_variants(self) -> None:
        formula = parse_ltl('!G(("a" U "b") | X "c")')
        self.assertEqual(
            to_weak_until_pnf(formula),
            Until(BooleanConstant(True), And(
                WeakUntil(
                    And(Proposition("a"), Not(Proposition("b"))),
                    And(Not(Proposition("a")), Not(Proposition("b"))),
                ),
                Next(Not(Proposition("c"))),
            )),
        )
        self.assertEqual(
            to_release_pnf(formula),
            Until(BooleanConstant(True), And(
                Release(Not(Proposition("a")), Not(Proposition("b"))),
                Next(Not(Proposition("c"))),
            )),
        )

    def test_converts_between_weak_until_and_release(self) -> None:
        p = Proposition("p")
        q = Proposition("q")
        self.assertEqual(
            to_weak_until_pnf(parse_ltl('"p" R "q"')),
            WeakUntil(And(Not(p), q), And(p, q)),
        )
        self.assertEqual(
            to_release_pnf(parse_ltl('"p" W "q"')),
            Release(q, Or(p, q)),
        )
        self.assertEqual(
            to_weak_until_pnf(parse_ltl('!F "p"')),
            WeakUntil(Not(p), BooleanConstant(False)),
        )
        self.assertEqual(
            to_release_pnf(parse_ltl('!F "p"')),
            Release(BooleanConstant(False), Not(p)),
        )

    def test_both_forms_preserve_lasso_semantics_and_are_stable(self) -> None:
        sources = (
            '!G(("p" U "q") | X "p")', '!("p" W "q")', '!("p" R "q")',
            '"p" W ("q" R "p")', '"p" R ("q" W "p")', 'G("p" -> F "q")',
            'F G "p"', '"p" <-> X "q"', '!("p" <-> X "q")',
            '!("p" -> F "q")', '!X("p" R "q")', '!(F "p" & G "q")',
            '"p" U ("q" W "p")', "!false", "true",
        )
        valuations = (frozenset(), frozenset({"p"}), frozenset({"q"}),
                      frozenset({"p", "q"}))
        for source in sources:
            formula = parse_ltl(source)
            for transform, dual in (
                (to_weak_until_pnf, WeakUntil),
                (to_release_pnf, Release),
            ):
                with self.subTest(source=source, dual=dual.__name__):
                    result = transform(formula)
                    self._assert_pnf(result, dual)
                    self.assertEqual(transform(result), result)
                    self.assertEqual(propositions(result), propositions(formula))
                    self.assertEqual(parse_ltl(result.to_source()), result)
                    for word in product(valuations, repeat=3):
                        for loop_start in (0, 1, 2):
                            for position in range(len(word)):
                                self.assertEqual(
                                    _evaluate(formula, word, loop_start, position),
                                    _evaluate(result, word, loop_start, position),
                                    (source, dual.__name__, word, loop_start,
                                     position),
                                )

    def _assert_pnf(self, formula, dual) -> None:
        self.assertIsInstance(
            formula,
            (BooleanConstant, Proposition, Not, Next, And, Or, Until, dual),
        )
        if isinstance(formula, Not):
            self.assertIsInstance(formula.operand, Proposition)
        elif isinstance(formula, Next):
            self._assert_pnf(formula.operand, dual)
        elif isinstance(formula, (And, Or, Until, dual)):
            self._assert_pnf(formula.left, dual)
            self._assert_pnf(formula.right, dual)


if __name__ == "__main__":
    unittest.main()
