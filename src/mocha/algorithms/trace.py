"""Generic support for recording algorithm executions."""

from dataclasses import dataclass
from typing import Generic, TypeVar

Result = TypeVar("Result")
Step = TypeVar("Step")


@dataclass(frozen=True)
class AlgorithmTrace(Generic[Result, Step]):
    """An algorithm result together with its immutable progress snapshots.

    Attributes:
        result: The final result returned by the analysis.
        steps: Snapshots emitted during that analysis, in execution order.
    """

    result: Result
    steps: tuple[Step, ...]
