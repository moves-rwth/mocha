"""Common semantic categories for temporal-logic syntax trees."""


class Formula:
    """Base type for a temporal-logic formula."""


class StateFormula(Formula):
    """A formula evaluated at a state of a transition system."""


class PathFormula(Formula):
    """A formula evaluated along a path of a transition system."""


__all__ = ["Formula", "StateFormula", "PathFormula"]
