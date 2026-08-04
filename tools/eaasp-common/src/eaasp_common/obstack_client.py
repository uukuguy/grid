"""OBSTACK client — single source of truth for the OBSTACK API.

Phase D.2 (eaasp-obstack-client extraction). This module unifies
the OBSTACK call surface across every EAASP caller:

  - grid-cli / eaasp-cli-v2 (Python) — call from subcommands
  - web (TypeScript) — has a TS mirror at @/api/obstack-client.ts
  - any future automation (Playwright, etcd, observability stack)

The backend is L4 (Rust axum). The wire format is the JSON shape
documented in tools/eaasp-l4-orchestration/src/eaasp_l4_orchestration/
flow_api.py. This client mirrors that surface 1:1 — the
``obstack_models`` dataclasses are the typed view of the JSON.

Both sync and async APIs are provided. Sync is the simpler
shape (e.g. for CLIs and quick scripts); async is the
recommended shape for any service-side code that wants to
concurrent-fetch multiple business flows.

Multi-tenant upgrade (Phase D): add a ``tenant_id`` parameter to
every method; the L4 server reads the ``X-Tenant-Id`` header.
Until that ships, the methods work without it.
"""

from __future__ import annotations

import json
import urllib.parse
from collections.abc import Iterator
from typing import Any

from .obstack_models import (
    BusinessFlowListResponse,
    BusinessFlowSummary,
    EvaluationReport,
    EvaluationResponse,
    FlowListParams,
    SessionRef,
    SessionsResponse,
    SummaryBlock,
    SummaryResponse,
    TimelineEvent,
    TimelineResponse,
)


class ObstackClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Mirrors the ``CliError`` taxonomy used by ``eaasp-cli-v2``:
    exit code 2 = client (4xx), 3 = transport (5xx-ish), 4 = server (5xx).
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


# ─── Sync client ────────────────────────────────────────────────


class ObstackClient:
    """Synchronous OBSTACK client.

    Construct with a base URL (e.g. ``http://127.0.0.1:18084``).
    Methods are 1:1 with the L4 /v1/business-flows/* surface.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        http_getter: "Any | None" = None,
    ) -> None:
        # Strip trailing slash; we'll join paths explicitly.
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        # Inject the HTTP getter for tests (returns parsed JSON);
        # defaults to urllib.request so the common package stays
        # stdlib-only (matching the philosophy of business_flow.py).
        self._http_getter = http_getter or _default_http_getter

    # ─── List ──────────────────────────────────────────────
    def list_business_flows(
        self,
        params: "FlowListParams | None" = None,
    ) -> BusinessFlowListResponse:
        """GET /v1/business-flows/list — all distinct business flows."""
        if params is None:
            params = FlowListParams()
        search: dict[str, str] = {"limit": str(params.limit)}
        if params.business_object_id:
            search["business_object_id"] = params.business_object_id
        if params.status:
            search["status"] = params.status
        body = self._get("/v1/business-flows/list", search=search)
        return BusinessFlowListResponse(
            flows=[
                BusinessFlowSummary(**flow) for flow in body.get("flows", [])
            ],
            total=body.get("total", 0),
        )

    # ─── Single-flow endpoints ───────────────────────────
    def get_timeline(self, business_key: str) -> TimelineResponse:
        """GET /v1/business-flows/{key}/timeline — ordered cross-layer events."""
        encoded = _encode_business_key(business_key)
        body = self._get(f"/v1/business-flows/{encoded}/timeline")
        return TimelineResponse(
            business_key=body["business_key"],
            events=[TimelineEvent(**ev) for ev in body.get("events", [])],
            count=body.get("count", 0),
        )

    def get_summary(self, business_key: str) -> SummaryResponse:
        """GET /v1/business-flows/{key}/summary — flow rollup."""
        encoded = _encode_business_key(business_key)
        body = self._get(f"/v1/business-flows/{encoded}/summary")
        s = body["summary"]
        return SummaryResponse(
            business_key=body["business_key"],
            summary=SummaryBlock(
                status=s["status"],
                started_at=s.get("started_at"),
                completed_at=s.get("completed_at"),
                total_duration_ms=s.get("total_duration_ms"),
                event_count=s["event_count"],
                layer_counts=s["layer_counts"],
                interrupted_layer=s.get("interrupted_layer"),
            ),
        )

    def get_sessions(self, business_key: str) -> SessionsResponse:
        """GET /v1/business-flows/{key}/sessions — matched session list."""
        encoded = _encode_business_key(business_key)
        body = self._get(f"/v1/business-flows/{encoded}/sessions")
        return SessionsResponse(
            business_key=body["business_key"],
            session_ids=[
                SessionRef(**s) for s in body.get("session_ids", [])
            ],
            count=body.get("count", 0),
        )

    def get_evaluation(self, business_key: str) -> EvaluationResponse:
        """GET /v1/business-flows/{key}/evaluation — completion report + hints."""
        encoded = _encode_business_key(business_key)
        body = self._get(f"/v1/business-flows/{encoded}/evaluation")
        r = body["report"]
        return EvaluationResponse(
            business_key=body["business_key"],
            report=EvaluationReport(
                window_seconds=r["window_seconds"],
                total_flows=r["total_flows"],
                status_counts=r["status_counts"],
                completion_rate=r["completion_rate"],
                interruption_heatmap=r.get("interruption_heatmap", {}),
                hints=[_hint_from_dict(h) for h in r.get("hints", [])],
            ),
        )

    # ─── Internals ──────────────────────────────────────
    def _get(self, path: str, search: dict[str, str] | None = None) -> dict[str, Any]:
        url = self.base_url + path
        if search:
            url += "?" + urllib.parse.urlencode(search)
        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        # Phase D.2 — wrap injected getter in the same try/except the
        # default transport uses, so callers don't need to repeat
        # HTTPError handling in their test fakes. Tests use raising
        # getters to assert ObstackClientError propagation.
        try:
            return self._http_getter(url, headers=headers)
        except ObstackClientError:
            raise  # don't double-wrap
        except Exception as e:
            # urllib.error.HTTPError carries an HTTP status; preserve it
            # so callers can branch on the response code. Other
            # exceptions (URLError, socket errors) get status=0.
            status = getattr(e, "code", 0) or 0
            raise ObstackClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e


# ─── Async client (thin wrapper over the sync one) ──────────────
#
# Use when you have many flows to fetch concurrently. For most
# callers the sync client is enough; this exists so server-side code
# (e.g. an aiohttp service) doesn't have to wrap sync calls in
# run_in_executor.

try:
    import asyncio as _asyncio  # type: ignore
    import httpx as _httpx  # type: ignore  # noqa: F401 — third-party
except ImportError:
    _asyncio = None
    _httpx = None
# Module-level aliases so the rest of the file can use them without
# sprinkling `if _asyncio is not None` everywhere.
asyncio = _asyncio
httpx = _httpx


def iter_summary_over_window(
    client: ObstackClient,
    business_keys: list[str],
    *,
    max_concurrency: int = 8,
) -> Iterator[SummaryResponse]:
    """Yield one ``SummaryResponse`` per business_key, fetched
    concurrently up to ``max_concurrency`` at a time.

    Phase D helper: dashboard refetches a batch of flow summaries
    on a periodic poll; this iterator avoids the simpler "one at a
    time" loop that would scale linearly with the number of flows.

    Falls back to a serial loop if ``asyncio`` is not available
    (the client is stdlib-only; this helper is an optional
    convenience for callers that have already pulled asyncio in).
    """
    if asyncio is None:
        for key in business_keys:
            yield client.get_summary(key)
        return

    async def _gather() -> list[SummaryResponse]:
        sem = asyncio.Semaphore(max_concurrency)

        async def _one(key: str) -> SummaryResponse:
            async with sem:
                # Run the sync call in a thread (the sync client
                # uses urllib, which blocks the event loop otherwise).
                return await asyncio.to_thread(client.get_summary, key)

        return await asyncio.gather(*[_one(k) for k in business_keys])

    for summary in asyncio.run(_gather()):
        yield summary


# ─── Helpers ───────────────────────────────────────────────


def _encode_business_key(key: str) -> str:
    """URL-encode a business key for the path segment.

    The pipe character is reserved in URL syntax, so we percent-encode
    it (and any other special chars).
    """
    return urllib.parse.quote(key, safe="")


def _hint_from_dict(d: dict[str, Any]):
    """Build an OptimizationHint from a wire dict (avoids a name
    import in the public model)."""
    from .obstack_models import OptimizationHint  # local to avoid cycle
    return OptimizationHint(**d)


# ─── Default transport (stdlib urllib) ───────────────────────────


def _default_http_getter(url: str, headers: dict[str, str]) -> dict[str, Any]:
    """The default transport — uses urllib.request (stdlib, no deps).

    On any non-2xx response we raise ``ObstackClientError`` so the
    caller can branch on status without parsing strings.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise ObstackClientError(e.code, f"HTTP {e.code} from {url}", body) from e
    except urllib.error.URLError as e:
        raise ObstackClientError(0, f"transport error from {url}: {e.reason}") from e

    try:
        return json.loads(payload)
    except json.JSONDecodeError as e:
        raise ObstackClientError(0, f"non-JSON response from {url}: {e}") from e
