"""RUO-C1 Existing ReasonUnit compatibility foundation."""

from .compatibility import (
    CANONICAL_ARTIFACTS,
    PROFILE,
    generate_compatibility,
    validate_compatibility,
    verify_ruo_c0,
)
from .model import (
    ObjectTransaction,
    compare_semantics,
    derived_state_is_stale,
    invalidate_evidence,
    project_existing_runtime_view,
    query_compatibility,
    unwrap_legacy_units,
    validate_wrapped_object,
    wrap_legacy_units,
)

__all__ = [
    "CANONICAL_ARTIFACTS",
    "PROFILE",
    "ObjectTransaction",
    "compare_semantics",
    "derived_state_is_stale",
    "generate_compatibility",
    "invalidate_evidence",
    "project_existing_runtime_view",
    "query_compatibility",
    "unwrap_legacy_units",
    "validate_compatibility",
    "validate_wrapped_object",
    "verify_ruo_c0",
    "wrap_legacy_units",
]
