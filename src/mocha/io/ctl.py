"""Parse CTL text into immutable formula syntax trees.

The ``state`` and ``path`` productions implement ``Φ`` and ``φ`` from
:mod:`mocha.logic.ctl`. The extra ``unary`` production expresses precedence
in concrete source notation. The recursive-descent parser follows::

    state ::= unary ("&" unary)*
    unary ::= quoted_proposition | "true" | "false" | "(" state ")"
            | "!" unary | ("E" | "A") path
    path  ::= ("X" | "F" | "G") unary | "(" state ("U" | "W") state ")"

Negation and quantified temporal operators bind more tightly than conjunction.
Tokenization separates adjacent operators, so ``EX "p"`` and ``E X "p"``
follow the same productions. Unicode spellings are translated to ASCII tokens.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import json
import re

from mocha.logic._syntax import CTL_KEYWORDS as _KEYWORDS
from mocha.logic.ctl import (
    Always,
    And,
    BooleanConstant,
    CTLPathFormula,
    CTLStateFormula,
    Eventually,
    Exists,
    ForAll,
    Next,
    Not,
    Proposition,
    Until,
    WeakUntil,
    propositions,
)


class CTLParseError(ValueError):
    """Invalid CTL syntax, with a one-based source location."""

    def __init__(self, source: str, position: int, message: str) -> None:
        line = source.count("\n", 0, position) + 1
        column = position - source.rfind("\n", 0, position)
        self.position = position
        self.line = line
        self.column = column
        super().__init__(f"{message} at line {line}, column {column}")


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    position: int


_TOKEN = re.compile(
    r'(?P<quoted>"(?:\\.|[^"\\])*")'
    r'|(?P<operator>&&|[EAXFGUW!&()¬∧∃∀◯○□◇])'
    r'|(?P<identifier>[A-Za-z_][A-Za-z_0-9]*)'
)
_ALIASES = {"&&": "&", "¬": "!", "∧": "&", "○": "X", "◯": "X", "□": "G", "◇": "F", "∃": "E", "∀": "A"}


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        match = _TOKEN.match(source, position)
        if match is None:
            raise CTLParseError(source, position, "Unexpected character")
        value = match.group()
        if match.lastgroup == "quoted":
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise CTLParseError(source, position, "Invalid quoted proposition") from error
            kind = "proposition"
        elif match.lastgroup == "identifier":
            if value not in _KEYWORDS:
                raise CTLParseError(
                    source, position, "Proposition names must be enclosed in double quotes"
                )
            kind = "keyword"
        else:
            kind = "operator"
            value = _ALIASES.get(value, value)
        tokens.append(_Token(kind, value, position))
        position = match.end()
    tokens.append(_Token("end", "", len(source)))
    return tokens


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _tokenize(source)
        self.index = 0

    @property
    def current(self) -> _Token:
        return self.tokens[self.index]

    def advance(self) -> _Token:
        token = self.current
        self.index += 1
        return token

    def expect(self, value: str) -> None:
        if self.current.value != value or self.current.kind == "proposition":
            raise CTLParseError(self.source, self.current.position, f"Expected {value!r}")
        self.advance()

    def state_formula(self) -> CTLStateFormula:
        """Parse a conjunction of unary state formulae, grouped to the left."""
        formula = self.unary_state_formula()
        while self.current.kind == "operator" and self.current.value == "&":
            self.advance()
            formula = And(formula, self.unary_state_formula())
        return formula

    def unary_state_formula(self) -> CTLStateFormula:
        """Parse an atom, grouped state formula, negation, or quantifier."""
        token = self.advance()
        if token.kind == "proposition":
            return Proposition(token.value)
        if token.kind == "keyword" and token.value in {"true", "false"}:
            return BooleanConstant(token.value == "true")
        if token.kind == "operator" and token.value == "(":
            formula = self.state_formula()
            self.expect(")")
            return formula
        if token.kind == "operator" and token.value == "!":
            return Not(self.unary_state_formula())
        if token.kind == "operator" and token.value in {"E", "A"}:
            path = self.path_formula()
            if token.value == "E":
                return Exists(path)
            return ForAll(path)
        raise CTLParseError(self.source, token.position, "Expected a CTL state formula")

    def path_formula(self) -> CTLPathFormula:
        """Parse one temporal operator with state-formula operands."""
        if self.current.kind == "operator" and self.current.value in {"X", "F", "G"}:
            operator = self.advance().value
            operand = self.unary_state_formula()
            if operator == "X":
                return Next(operand)
            if operator == "F":
                return Eventually(operand)
            return Always(operand)

        self.expect("(")
        left = self.state_formula()
        if self.current.kind != "operator" or self.current.value not in {"U", "W"}:
            raise CTLParseError(self.source, self.current.position, "Expected 'U' or 'W'")
        operator = self.advance().value
        right = self.state_formula()
        self.expect(")")
        if operator == "U":
            return Until(left, right)
        return WeakUntil(left, right)

    def parse(self) -> CTLStateFormula:
        formula = self.state_formula()
        if self.current.kind != "end":
            raise CTLParseError(self.source, self.current.position, "Unexpected token")
        return formula


def parse_ctl(
    source: str, *, atomic_propositions: Iterable[str] | None = None,
) -> CTLStateFormula:
    """Parse the supported CTL fragment, optionally checking proposition names.

    All proposition names must be double-quoted. Syntax errors raise
    :class:`CTLParseError` with a line and column; undeclared propositions
    raise ``ValueError``.
    """
    formula = _Parser(source).parse()
    if atomic_propositions is not None:
        unknown = propositions(formula) - frozenset(atomic_propositions)
        if unknown:
            raise ValueError(f"Unknown atomic propositions: {sorted(unknown)!r}")
    return formula


__all__ = ["CTLParseError", "parse_ctl"]
