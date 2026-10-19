"""Parse LTL text into immutable formula syntax trees."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import json
import re

from mocha.logic._syntax import LTL_KEYWORDS as _KEYWORDS, LTL_TEMPORAL_CHAIN as _TEMPORAL_CHAIN
from mocha.logic.ltl import (
    Always,
    And,
    BooleanConstant,
    Equiv,
    Eventually,
    Implies,
    LTLFormula,
    Next,
    Not,
    Or,
    Proposition,
    Release,
    Until,
    WeakUntil,
    propositions,
)


class LTLParseError(ValueError):
    """Invalid LTL syntax, with a one-based source location."""

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
    r'|(?P<operator><->|->|&&|\|\||[!&|()¬∧∨→↔○◯□◇])'
    r'|(?P<identifier>[A-Za-z_][A-Za-z_0-9]*)'
)
_UNARY = {"!": Not, "X": Next, "F": Eventually, "G": Always}
_BINARY = {
    "<->": (1, Equiv),
    "->": (2, Implies),
    "|": (3, Or),
    "&": (4, And),
    "U": (5, Until),
    "W": (5, WeakUntil),
    "R": (5, Release),
}
_OPERATOR_ALIASES = {
    "&&": "&", "||": "|", "¬": "!", "∧": "&", "∨": "|",
    "→": "->", "↔": "<->", "○": "X", "◯": "X", "□": "G", "◇": "F",
}


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    position = 0
    while position < len(source):
        if source[position].isspace():
            position += 1
            continue
        match = _TOKEN.match(source, position)
        if match is None:
            raise LTLParseError(source, position, "Unexpected character")
        value = match.group()
        if match.lastgroup == "quoted":
            try:
                value = json.loads(value)
            except json.JSONDecodeError as error:
                raise LTLParseError(
                    source, position, "Invalid quoted proposition"
                ) from error
            kind = "proposition"
        elif match.lastgroup == "identifier":
            if _TEMPORAL_CHAIN.fullmatch(value):
                tokens.extend(_Token("keyword", operator, position + offset)
                              for offset, operator in enumerate(value))
                position = match.end()
                continue
            if value not in _KEYWORDS:
                raise LTLParseError(
                    source, position, "Proposition names must be enclosed in double quotes"
                )
            kind = "keyword"
        else:
            kind = "operator"
            value = _OPERATOR_ALIASES.get(value, value)
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

    def expression(self, minimum_precedence: int = 1) -> LTLFormula:
        token = self.advance()
        if token.kind == "operator" and token.value == "(":
            left = self.expression()
            if self.current.value != ")":
                raise LTLParseError(self.source, self.current.position, "Expected ')'")
            self.advance()
        elif token.kind == "proposition":
            left = Proposition(token.value)
        elif token.kind == "keyword" and token.value in {"true", "false"}:
            left = BooleanConstant(token.value == "true")
        elif token.kind in {"keyword", "operator"} and token.value in _UNARY:
            left = _UNARY[token.value](self.expression(6))
        else:
            raise LTLParseError(self.source, token.position, "Expected a formula")

        while (
            self.current.kind in {"keyword", "operator"}
            and self.current.value in _BINARY
        ):
            precedence, constructor = _BINARY[self.current.value]
            if precedence < minimum_precedence:
                break
            operator = self.advance()
            next_minimum = (
                precedence if operator.value in {"->", "U", "W", "R"}
                else precedence + 1
            )
            left = constructor(left, self.expression(next_minimum))
        return left

    def parse(self) -> LTLFormula:
        formula = self.expression()
        if self.current.kind != "end":
            raise LTLParseError(
                self.source, self.current.position, "Unexpected token"
            )
        return formula


def parse_ltl(
    source: str,
    *,
    atomic_propositions: Iterable[str] | None = None,
) -> LTLFormula:
    """Parse LTL, optionally checking names against a system's propositions.

    Pass ``ts.atomic_propositions`` for a string-valued transition system.
    All proposition names require double quotes, including single letters.
    Runs consisting only of ``X``, ``F``, and ``G`` are unary operator chains
    (``XX"p"``, ``GF("p")``). Boolean constants remain unquoted.
    Use ``formula.to_source()`` for serialization; ``str(formula)`` is display notation.
    Syntax errors raise :class:`LTLParseError` with a line and column;
    undeclared propositions raise ``ValueError``.
    """
    formula = _Parser(source).parse()
    if atomic_propositions is not None:
        unknown = propositions(formula) - frozenset(atomic_propositions)
        if unknown:
            raise ValueError(f"Unknown atomic propositions: {sorted(unknown)!r}")
    return formula


__all__ = ["LTLParseError", "parse_ltl"]
