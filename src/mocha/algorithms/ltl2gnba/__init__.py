"""Educational stages of LTL-to-GNBA translation and their traceable results.

Use ``ltl_to_gnba`` for automatic normalization and the complete construction,
or call the elementary-set, initial-state, transition, and acceptance stages
individually. Elementary-set checking and enumeration require an already
normalized formula. Initial-state, transition, and acceptance construction each
take that formula and an explicit collection of elementary sets in the caller's
chosen order, without requiring an enumeration or another stage's result.
``trace_*`` helpers collect the corresponding callback events in an
``AlgorithmTrace`` with a final result and an ordered tuple of steps.

``check_elementary_set_collection`` separately checks a computed solution for
invalid states, duplicates, and omissions. It recomputes the full enumeration;
component construction only validates individual states and duplicates.
"""

from .acceptance import (
    AcceptanceCondition, AcceptanceDecision, AcceptanceResult, AcceptanceStep,
    compute_acceptance_sets, trace_acceptance_sets,
)
from .initial_states import (
    InitialStateStep, InitialStatesResult, compute_initial_states, trace_initial_states,
)
from .pipeline import LTLToGNBAResult, LTLToGNBAStep, ltl_to_gnba, trace_ltl_to_gnba
from .elementary_set_validation import (
    ElementarySetResult,
    ElementarySetViolation,
    check_elementary_set,
    ElementarySetCollectionResult,
    check_elementary_set_collection,
    validate_elementary_set_collection,
)
from .elementary_set_enumeration import (
    ElementarySetEnumeration,
    ElementaryTable,
    ElementaryTableChange,
    ElementaryTableRow,
    ElementaryTableStep,
    enumerate_elementary_sets,
    trace_elementary_sets,
)
from .transitions import (
    TransitionRestriction,
    TransitionRelationResult,
    TransitionRelationStep,
    TransitionRelationTable,
    compute_transition_relation,
    trace_transition_relation,
)

__all__ = [
    "AcceptanceCondition", "AcceptanceDecision", "AcceptanceResult", "AcceptanceStep",
    "compute_acceptance_sets", "trace_acceptance_sets",
    "InitialStateStep", "InitialStatesResult", "compute_initial_states", "trace_initial_states",
    "LTLToGNBAResult", "LTLToGNBAStep", "ltl_to_gnba", "trace_ltl_to_gnba",
    "TransitionRestriction",
    "TransitionRelationResult",
    "TransitionRelationStep",
    "TransitionRelationTable",
    "compute_transition_relation",
    "trace_transition_relation",
    "ElementarySetEnumeration",
    "ElementarySetResult",
    "ElementarySetViolation",
    "ElementaryTable",
    "ElementaryTableChange",
    "ElementaryTableRow",
    "ElementaryTableStep",
    "check_elementary_set",
    "ElementarySetCollectionResult",
    "check_elementary_set_collection",
    "validate_elementary_set_collection",
    "enumerate_elementary_sets",
    "trace_elementary_sets",
]
