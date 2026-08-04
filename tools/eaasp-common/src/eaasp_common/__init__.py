"""Shared utilities for EAASP Python tools."""

from .business_flow import (
    BusinessKey,
    business_key_scope,
    get_current_business_key,
    iter_business_key_contexts,
    parse_business_key_header,
    require_current_business_key,
    reset_current_business_key,
    serialize_business_key,
    set_current_business_key,
)
from .errors import sanitize_errors
from .obstack_client import (
    ObstackClient,
    ObstackClientError,
    iter_summary_over_window,
)
from .obstack_models import (
    BusinessFlowListResponse,
    BusinessFlowSummary,
    EvaluationReport,
    EvaluationResponse,
    FlowListParams,
    OptimizationHint,
    SessionRef,
    SessionsResponse,
    SummaryBlock,
    SummaryResponse,
    TimelineEvent,
    TimelineResponse,
)

__all__ = [
    "BusinessFlowListResponse",
    "BusinessFlowSummary",
    "BusinessKey",
    "EvaluationReport",
    "EvaluationResponse",
    "FlowListParams",
    "OptimizationHint",
    "ObstackClient",
    "ObstackClientError",
    "SessionRef",
    "SessionsResponse",
    "SummaryBlock",
    "SummaryResponse",
    "TimelineEvent",
    "TimelineResponse",
    "business_key_scope",
    "get_current_business_key",
    "iter_business_key_contexts",
    "iter_summary_over_window",
    "parse_business_key_header",
    "require_current_business_key",
    "reset_current_business_key",
    "sanitize_errors",
    "serialize_business_key",
    "set_current_business_key",
]
