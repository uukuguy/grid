"""OBSTACK client models — Pydantic/dataclass shapes that mirror
L4 ``/v1/business-flows/*`` response payloads.

L4 Python is the server owner. ``web/src/api/obstack_types.ts`` is the TypeScript mirror.

Phase D.2 (eaasp-obstack-client extraction). These types describe the
OBSTACK API surface for its consumers:

  - L4 Python — actual server emitting these JSON shapes
  - grid-cli / eaasp-cli-v2 (Python) — consumes via ObstackClient
  - web (TypeScript) — consumes its mirror via @/api/obstack-client.ts

When the L4 server adds or renames a field, update these Python models
and the TypeScript mirror together so consumer type checks surface the
contract change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ─── List endpoint ────────────────────────────────────────────────


@dataclass(frozen=True)
class BusinessFlowSummary:
    """One business flow row in the list endpoint.

    Mirrors the response shape of ``GET /v1/business-flows/list``:
    one row per distinct ``business_key`` with the most recent
    session's stats aggregated.
    """

    business_key: str
    business_object_id: str
    skill_id: str
    session_id: str
    session_count: int
    finished_count: int
    failed_count: int
    last_started_at: int | None
    last_completed_at: int | None
    last_duration_ms: int | None
    # Per-row status aggregated from the most recent session.
    # Possible values: "failed" (any session failed), "active" (any
    # session is still open), "closed" (all sessions finished).
    status: str


@dataclass(frozen=True)
class BusinessFlowListResponse:
    """Response body of GET /v1/business-flows/list."""

    flows: list[BusinessFlowSummary] = field(default_factory=list)
    total: int = 0


# ─── Timeline endpoint ────────────────────────────────────────────


@dataclass(frozen=True)
class TimelineEvent:
    """One cross-layer event in the business-flow timeline.

    Mirrors the L4 flow_timeline.BusinesFlowEvent.to_dict() output.
    """

    ts: int  # epoch milliseconds (per L4 convention)
    layer: str
    component: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class TimelineResponse:
    """Response body of GET /v1/business-flows/{key}/timeline."""

    business_key: str
    events: list[TimelineEvent] = field(default_factory=list)
    count: int = 0


# ─── Summary endpoint ────────────────────────────────────────────


@dataclass(frozen=True)
class SummaryBlock:
    """The inner summary block returned by GET /v1/business-flows/{key}/summary."""

    status: str
    started_at: int | None
    completed_at: int | None
    total_duration_ms: int | None
    event_count: int
    layer_counts: dict[str, int]
    interrupted_layer: str | None = None


@dataclass(frozen=True)
class SummaryResponse:
    """Response body of GET /v1/business-flows/{key}/summary."""

    business_key: str
    summary: SummaryBlock


# ─── Sessions endpoint ────────────────────────────────────────────


@dataclass(frozen=True)
class SessionRef:
    """One row in the per-business-flow sessions list."""

    session_id: str
    status: str
    created_at: int


@dataclass(frozen=True)
class SessionsResponse:
    """Response body of GET /v1/business-flows/{key}/sessions."""

    business_key: str
    session_ids: list[SessionRef] = field(default_factory=list)
    count: int = 0


# ─── Evaluation endpoint ──────────────────────────────────────────


@dataclass(frozen=True)
class OptimizationHint:
    """One optimization hint returned by the flow evaluator."""

    layer: str
    metric: str
    severity: str  # "info" | "warn" | "critical"
    recommendation: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationReport:
    """Inner report block."""

    window_seconds: int
    total_flows: int
    status_counts: dict[str, int]
    completion_rate: float
    interruption_heatmap: dict[str, int]
    hints: list[OptimizationHint] = field(default_factory=list)


@dataclass(frozen=True)
class EvaluationResponse:
    """Response body of GET /v1/business-flows/{key}/evaluation."""

    business_key: str
    report: EvaluationReport


# ─── List endpoint query params (mirrored client-side) ──────────


@dataclass(frozen=True)
class FlowListParams:
    """Query parameters for GET /v1/business-flows/list.

    ``status`` is a single value forwarded to the server; for multi-
    status filtering, callers iterate server-side ORs after a single
    call. ``business_object_id`` does exact match on the third pipe
    segment of the wire-format key.
    """

    limit: int = 20
    business_object_id: str | None = None
    status: str | None = None
