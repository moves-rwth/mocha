"""Generic support for recording algorithm executions."""

from dataclasses import dataclass
from typing import Generic, TypeVar

Result = TypeVar("Result")
Step = TypeVar("Step")

@dataclass(frozen=True)
class AlgorithmTrace(Generic[Result, Step]):
    result: Result
    steps: tuple[Step, ...]