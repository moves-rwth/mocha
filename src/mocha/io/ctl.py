"""Parse CTL text into immutable formula syntax trees."""

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

    def formula(self, minimum_precedence: int = 1) -> CTLStateFormula:
        token = self.advance()
        if token.kind == "proposition":
            left: CTLStateFormula = Proposition(token.value)
        elif token.kind == "keyword" and token.value in {"true", "false"}:
            left = BooleanConstant(token.value == "true")
        elif token.kind == "operator" and token.value == "(":
            left = self.formula()
            self.expect(")")
        elif token.kind == "operator" and token.value == "!":
            left = Not(self.formula(3))
        elif token.kind == "operator" and token.value in {"E", "A"}:
            if self.current.kind == "operator" and self.current.value in {"X", "F", "G"}:
                operator = self.advance().value
                path: CTLPathFormula = {"X": Next, "F": Eventually, "G": Always}[operator](self.formula(3))
            else:
                self.expect("(")
                until_left = self.formula()
                if self.current.kind != "operator" or self.current.value not in {"U", "W"}:
                    raise CTLParseError(self.source, self.current.position, "Expected 'U' or 'W'")
                operator = self.advance().value
                until_right = self.formula()
                self.expect(")")
                path = (Until if operator == "U" else WeakUntil)(until_left, until_right)
            left = (Exists if token.value == "E" else ForAll)(path)
        else:
            raise CTLParseError(self.source, token.position, "Expected a CTL formula")

        while (
            self.current.kind == "operator"
            and self.current.value == "&"
            and minimum_precedence <= 1
        ):
            self.advance()
            left = And(left, self.formula(2))
        return left

    def parse(self) -> CTLStateFormula:
        formula = self.formula()
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
