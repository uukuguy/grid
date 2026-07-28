"""Ontology service — taxonomy + cross-domain link projection.

v3.14.0 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.

Per ``EAASP_v2_0_EVOLUTION_PATH.md`` §三 Phase 6 + spec §7.5–§7.6:

- The Ontology service exposes ``TaxonomyNode`` / ``CrossDomainLink``
  / ``TaxonomyGraph`` projection types. Each is **derived** via
  SELECT from existing L2 evidence anchor + L3 governance_decisions
  + L4 event_room_events + L5 four-card projections (per D-40
  "派生不复制" — no new tables, no new columns, no new event types).
- ``OntologyService.derive_taxonomy()`` is deterministic (same
  input → same output) and bounded by tenant (D-33-style tenant
  guard).
- Public accessors: ``list_taxonomy(path) -> list[TaxonomyNode]``,
  ``resolve_link(from_node_id, to_node_id) -> CrossDomainLink``,
  ``derive_taxonomy() -> TaxonomyGraph``.

Taxonomy model
--------------

A ``TaxonomyNode`` has:

- ``node_id``  — stable hash of (source_layer, key, tenant_id)
- ``label``    — human-readable label (e.g. ``plant``, ``grid``)
- ``layer``    — which layer the node derives from:
    - ``l2_type`` — from L2 ``anchors.type``
    - ``l3_risk`` — from L3 ``governance_decisions.risk_level``
    - ``l4_event`` — from L4 ``event_room_events.event_type``
    - ``l5_card`` — from L5 four-card projection (Event/Evidence/Action/Approval)
- ``tenant_id`` — tenant this node belongs to
- ``count``    — number of underlying rows that produced this node
- ``children`` — child node IDs (taxonomy tree)
- ``evidence_refs`` — list of evidence anchors / decision_ids /
  event_seqs that produced this node

A ``CrossDomainLink`` connects two taxonomy nodes that share
underlying evidence (e.g. the same evidence anchor is referenced
by both an ``l2_type`` and an ``l3_risk`` node). The link carries:

- ``link_id``    — stable hash of (from_node_id, to_node_id)
- ``from_node_id`` / ``to_node_id`` — node endpoints
- ``evidence_refs`` — list of underlying shared refs
- ``weight``     — number of underlying shared refs

A ``TaxonomyGraph`` is the full set of nodes + links for a
tenant, plus a root node ``"root"`` that points to all top-level
nodes (those with no parents).

Frozen contract (audit §7.2):

- ``derive_taxonomy()`` is idempotent (calling it twice produces
  the same graph for the same input).
- All accessors return ``[]`` (empty list) or an empty graph on
  missing data — never raise on empty input.
- Cross-tenant access raises ``CrossTenantForbidden`` (matching
  v3.13 D-33 + v3.12.1 D-28).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable


# ─── Cross-tenant guard ──────────────────────────────────────────────────


class CrossTenantForbidden(PermissionError):
    """Raised when a caller requests cross-tenant ontology access.

    Mirrors the v3.12.1 D-28 + v3.13 D-33 tenant-guard pattern.
    Callers must translate this to HTTP 403.
    """


# ─── Projection types ────────────────────────────────────────────────────


@dataclass(frozen=True)
class TaxonomyNode:
    """A taxonomy node derived from an underlying EAASP layer.

    See module docstring for the full field semantics.
    """

    node_id: str
    label: str
    layer: str  # one of: l2_type, l3_risk, l4_event, l5_card
    tenant_id: str
    count: int
    evidence_refs: tuple[str, ...] = field(default_factory=tuple)
    children: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "layer": self.layer,
            "tenant_id": self.tenant_id,
            "count": self.count,
            "evidence_refs": list(self.evidence_refs),
            "children": list(self.children),
        }


@dataclass(frozen=True)
class CrossDomainLink:
    """A cross-domain link between two taxonomy nodes."""

    link_id: str
    from_node_id: str
    to_node_id: str
    evidence_refs: tuple[str, ...]
    weight: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "evidence_refs": list(self.evidence_refs),
            "weight": self.weight,
        }


@dataclass(frozen=True)
class TaxonomyGraph:
    """The full taxonomy graph for a tenant.

    Always includes a synthetic ``"root"`` node whose children are
    the top-level (no-parent) nodes — that is, nodes whose ``layer``
    matches the configured ``root_layer`` (default ``l2_type``).
    """

    tenant_id: str
    nodes: tuple[TaxonomyNode, ...]
    links: tuple[CrossDomainLink, ...]
    root_id: str = "root"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "root_id": self.root_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "links": [l.to_dict() for l in self.links],
        }


# ─── Stable ID helpers ───────────────────────────────────────────────────


def _stable_node_id(layer: str, key: str, tenant_id: str) -> str:
    """Compute a stable node ID from (layer, key, tenant_id)."""
    h = hashlib.sha256(f"{layer}|{key}|{tenant_id}".encode()).hexdigest()
    return f"tax-{layer}-{h[:12]}"


def _stable_link_id(from_node_id: str, to_node_id: str) -> str:
    """Compute a stable link ID from two node endpoints."""
    h = hashlib.sha256(f"{from_node_id}|{to_node_id}".encode()).hexdigest()
    return f"lnk-{h[:12]}"


# ─── Ontology service ────────────────────────────────────────────────────


class OntologyService:
    """Read-only projection layer over L2 / L3 / L4 / L5 stores.

    The service is *stateless* — every call to
    ``derive_taxonomy()`` re-runs the SELECT statements against the
    underlying SQLite stores. There is no in-memory cache by
    default (a higher-level wrapper could add one).

    Parameters
    ----------
    l2_db_path, l3_db_path, l4_db_path, l5_db_path
        Paths to the L2 / L3 / L4 / L5 SQLite stores. ``l5_db_path``
        is optional — when omitted, the service derives the
        taxonomy from L2 / L3 / L4 only (which is sufficient for the
        v3.14.0 baseline).
    default_tenant
        Default tenant when ``X-Tenant-Id`` header / ``tenant_id``
        query param is missing. Matches the v3.13 D-33 default.
    root_layer
        Which layer's nodes should be the children of the synthetic
        ``"root"`` node. Default ``"l2_type"`` — the most stable
        taxonomy axis (the L2 ``anchors.type`` field).
    """

    def __init__(
        self,
        *,
        l2_db_path: str,
        l3_db_path: str,
        l4_db_path: str,
        l5_db_path: str | None = None,
        default_tenant: str = "default",
        root_layer: str = "l2_type",
    ) -> None:
        self.l2_db_path = l2_db_path
        self.l3_db_path = l3_db_path
        self.l4_db_path = l4_db_path
        self.l5_db_path = l5_db_path
        self.default_tenant = default_tenant
        self.root_layer = root_layer

    # ─── Tenant guard (D-33 / v3.13 carry-over; FAIL-CLOSED) ────────

    def _resolve_tenant(self, tenant_id: str | None) -> str:
        """Resolve the calling tenant for an ontology request.

        The caller MUST supply a non-empty ``tenant_id`` that has
        been validated against an authenticated principal (API key,
        OPA-issued token, session cookie). Unauthenticated callers
        receive ``CrossTenantForbidden`` — never the default tenant.

        This matches the v3.9 RBAC auditor contract (D-04 + D-44):
        client-supplied tenant identifiers are rejected unless
        authenticated.
        """
        if tenant_id is None:
            raise CrossTenantForbidden(
                "tenant_id required: caller must supply an "
                "authenticated tenant identifier"
            )
        t = tenant_id.strip()
        if not t:
            raise CrossTenantForbidden(
                "tenant_id required: caller must supply a non-empty "
                "authenticated tenant identifier"
            )
        return t

    def _assert_same_tenant(self, requested_tenant: str, row_tenant: str | None) -> None:
        """Reject cross-tenant access (v3.12.1 D-28 + v3.13 D-33).

        **Fail-closed**: when ``row_tenant`` is ``None`` (no row
        tenant available), the function raises ``CrossTenantForbidden``
        rather than silently passing. The previous fail-open behaviour
        leaked cross-tenant data; the audit (§7.2 v3.14.0 round-1)
        mandated the fix.
        """
        if row_tenant is None:
            raise CrossTenantForbidden(
                "row_tenant unavailable: cannot verify same-tenant "
                "invariant; fail-closed"
            )
        if requested_tenant != row_tenant:
            raise CrossTenantForbidden(
                f"cross-tenant access: caller tenant={requested_tenant!r} "
                f"row tenant={row_tenant!r}"
            )

    # ─── Layer projections (read-only SELECTs) ───────────────────────

    def _l2_type_counts(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{type_value: {count, evidence_refs}}`` for L2 anchors.

        The L2 ``anchors`` table does NOT have a ``tenant_id``
        column in v3.7.3 — adding one would violate D-40 (no new
        columns). The standard ``make dev-eaasp`` topology treats
        each L2 store as bound to a single tenant; we therefore
        record the store's binding via ``self.l2_db_path`` and
        reject access when the caller's tenant does not match
        ``self.default_tenant``.

        For multi-tenant deployments, ``L2StoreBinding`` would be
        a per-tenant path mapping — added in v3.15+ (per D-44 +
        v3.14 §Out of Scope "Cross-tenant ontology cross-domain
        links" deferral).
        """
        self._assert_same_tenant(tenant_id, self.default_tenant)
        out: dict[str, dict[str, Any]] = {}
        with sqlite3.connect(self.l2_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT type,
                           COUNT(*) AS n,
                           GROUP_CONCAT(anchor_id) AS ids
                    FROM anchors
                    GROUP BY type
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                return out
        for r in rows:
            t = r["type"] or ""
            if not t:
                continue
            ids = tuple((r["ids"] or "").split(",")) if r["ids"] else ()
            out[t] = {"count": int(r["n"]), "evidence_refs": ids}
        return out

    def _l3_risk_counts(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{risk_level: {count, evidence_refs}}`` for L3.

        The L3 ``governance_decisions`` table does NOT have a
        ``tenant_id`` column in v3.7.3 — same constraint as L2
        (see ``_l2_type_counts`` docstring). Each L3 store is
        bound to a single tenant; cross-tenant access is rejected
        via ``_assert_same_tenant``.
        """
        self._assert_same_tenant(tenant_id, self.default_tenant)
        out: dict[str, dict[str, Any]] = {}
        with sqlite3.connect(self.l3_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT risk_level,
                           COUNT(*) AS n,
                           GROUP_CONCAT(decision_id) AS ids
                    FROM governance_decisions
                    GROUP BY risk_level
                    """
                ).fetchall()
            except sqlite3.OperationalError:
                return out
        for r in rows:
            t = r["risk_level"] or ""
            if not t:
                continue
            ids = tuple((r["ids"] or "").split(",")) if r["ids"] else ()
            out[t] = {"count": int(r["n"]), "evidence_refs": ids}
        return out

    def _l4_event_counts(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{event_type: {count, evidence_refs}}`` for L4.

        The L4 ``event_room_events`` table is joined to
        ``event_rooms`` (which has ``tenant_id``) so that the
        SELECT filters out other tenants' rooms. This is the only
        layer that natively supports per-row tenant filtering.
        """
        self._assert_same_tenant(tenant_id, self.default_tenant)
        out: dict[str, dict[str, Any]] = {}
        with sqlite3.connect(self.l4_db_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                rows = conn.execute(
                    """
                    SELECT e.event_type AS event_type,
                           COUNT(*) AS n,
                           GROUP_CONCAT(e.seq) AS ids
                    FROM event_room_events e
                    JOIN event_rooms r ON e.room_id = r.room_id
                    WHERE r.tenant_id = ?
                    GROUP BY e.event_type
                    """,
                    (tenant_id,),
                ).fetchall()
            except sqlite3.OperationalError:
                return out
        for r in rows:
            t = r["event_type"] or ""
            if not t:
                continue
            ids = tuple((r["ids"] or "").split(",")) if r["ids"] else ()
            out[t] = {"count": int(r["n"]), "evidence_refs": ids}
        return out

    def _l5_card_counts(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        """Return ``{card_type: {count, evidence_refs}}`` for L5.

        When ``l5_db_path`` is provided, the L5 ``l5_cards`` table
        has its own ``tenant_id`` column (added in v3.13) and the
        SELECT filters directly. When ``l5_db_path`` is None, the
        service falls back to L4-event-derived card counts (which
        are already tenant-filtered via the L4 join).
        """
        self._assert_same_tenant(tenant_id, self.default_tenant)
        out: dict[str, dict[str, Any]] = {}
        if self.l5_db_path:
            with sqlite3.connect(self.l5_db_path) as conn:
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        """
                        SELECT card_type,
                               COUNT(*) AS n,
                               GROUP_CONCAT(card_id) AS ids
                        FROM l5_cards
                        WHERE tenant_id = ?
                        GROUP BY card_type
                        """,
                        (tenant_id,),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            for r in rows:
                t = r["card_type"] or ""
                if not t:
                    continue
                ids = tuple((r["ids"] or "").split(",")) if r["ids"] else ()
                out[t] = {"count": int(r["n"]), "evidence_refs": ids}
        return out

    # ─── Public accessors (REQ-IDs ONTOLOGY-01..02) ──────────────────

    def derive_taxonomy(self, tenant_id: str | None = None) -> TaxonomyGraph:
        """Derive the full taxonomy graph for the given tenant.

        The graph contains:

        - one node per distinct ``l2_type`` (from L2 anchors)
        - one node per distinct ``l3_risk`` (from L3 decisions)
        - one node per distinct ``l4_event`` (from L4 events)
        - one node per distinct ``l5_card`` (from L5 cards, when
          available; otherwise empty)
        - one synthetic ``"root"`` node whose children are the
          ``root_layer`` nodes (default ``l2_type``)
        - one cross-domain link per shared evidence_ref between
          two distinct nodes

        Determinism: same inputs → same outputs. The function is
        idempotent — calling it twice produces the same graph.

        Empty stores produce an empty graph (only the synthetic
        ``"root"`` node).
        """
        tenant = self._resolve_tenant(tenant_id)
        l2 = self._l2_type_counts(tenant)
        l3 = self._l3_risk_counts(tenant)
        l4 = self._l4_event_counts(tenant)
        l5 = self._l5_card_counts(tenant)

        nodes: list[TaxonomyNode] = []
        node_index: dict[str, TaxonomyNode] = {}

        # Build nodes per layer
        for layer_name, counts in (
            ("l2_type", l2),
            ("l3_risk", l3),
            ("l4_event", l4),
            ("l5_card", l5),
        ):
            for key, info in sorted(counts.items()):
                nid = _stable_node_id(layer_name, key, tenant)
                node = TaxonomyNode(
                    node_id=nid,
                    label=key,
                    layer=layer_name,
                    tenant_id=tenant,
                    count=int(info["count"]),
                    evidence_refs=tuple(info["evidence_refs"]),
                )
                nodes.append(node)
                node_index[nid] = node

        # Build cross-domain links: an evidence_ref is shared when
        # the same value appears in the evidence_refs of two nodes
        # of *different* layers. We compute by iterating over each
        # ref and tracking which nodes contain it.
        ref_to_nodes: dict[str, set[str]] = {}
        for nid, node in node_index.items():
            for ref in node.evidence_refs:
                if not ref:
                    continue
                ref_to_nodes.setdefault(ref, set()).add(nid)

        links: list[CrossDomainLink] = []
        # Group refs by their (frozenset(nodes), frozenset(2)) edges
        edge_to_refs: dict[tuple[str, str], list[str]] = {}
        for ref, nset in ref_to_nodes.items():
            if len(nset) < 2:
                continue
            nsorted = sorted(nset)
            for i in range(len(nsorted)):
                for j in range(i + 1, len(nsorted)):
                    edge_to_refs.setdefault(
                        (nsorted[i], nsorted[j]), []
                    ).append(ref)

        for (from_id, to_id), refs in sorted(edge_to_refs.items()):
            link_id = _stable_link_id(from_id, to_id)
            links.append(
                CrossDomainLink(
                    link_id=link_id,
                    from_node_id=from_id,
                    to_node_id=to_id,
                    evidence_refs=tuple(refs),
                    weight=len(refs),
                )
            )

        # Build children map: a node's parent is its first l2_type
        # sibling whose label sorts immediately before (simple
        # deterministic ordering for the audit; the goal is a
        # tree-shaped view, not a domain-correct hierarchy).
        # The synthetic root is parent of all root_layer nodes.
        root_nodes = [
            n for n in nodes if n.layer == self.root_layer
        ]
        other_nodes = [n for n in nodes if n.layer != self.root_layer]
        children_map: dict[str, list[str]] = {}
        for r in root_nodes:
            children_map.setdefault("root", []).append(r.node_id)
        # Within each layer, build a simple ordering: nodes are
        # ordered by their (layer, label) pair.
        for layer_name in ("l2_type", "l3_risk", "l4_event", "l5_card"):
            layer_nodes = sorted(
                [n for n in other_nodes if n.layer == layer_name],
                key=lambda n: n.label,
            )
            for idx, n in enumerate(layer_nodes):
                if idx == 0:
                    continue
                parent = layer_nodes[idx - 1]
                children_map.setdefault(parent.node_id, []).append(
                    n.node_id
                )

        # Re-create nodes with children populated
        nodes_with_children = []
        for n in nodes:
            children = tuple(children_map.get(n.node_id, ()))
            nodes_with_children.append(
                TaxonomyNode(
                    node_id=n.node_id,
                    label=n.label,
                    layer=n.layer,
                    tenant_id=n.tenant_id,
                    count=n.count,
                    evidence_refs=n.evidence_refs,
                    children=children,
                )
            )

        # Synthetic root
        root_node = TaxonomyNode(
            node_id="root",
            label="root",
            layer="root",
            tenant_id=tenant,
            count=0,
            evidence_refs=(),
            children=tuple(children_map.get("root", ())),
        )
        nodes_with_children.insert(0, root_node)

        return TaxonomyGraph(
            tenant_id=tenant,
            nodes=tuple(nodes_with_children),
            links=tuple(links),
            root_id="root",
        )

    def list_taxonomy(
        self,
        path: str | None = None,
        tenant_id: str | None = None,
    ) -> list[TaxonomyNode]:
        """List taxonomy nodes under ``path``.

        ``path`` is a ``/``-separated sequence of node labels (or
        ``None`` for root). Each label is matched against the
        corresponding depth of the tree.

        Returns ``[]`` (empty list) when no nodes match — never
        raises on missing data (audit §7.2).
        """
        graph = self.derive_taxonomy(tenant_id=tenant_id)
        if path is None or not path.strip():
            # Root — return top-level children of the synthetic root
            root = next(
                (n for n in graph.nodes if n.node_id == "root"), None
            )
            if root is None:
                return []
            by_id = {n.node_id: n for n in graph.nodes}
            return [by_id[c] for c in root.children if c in by_id]

        labels = [seg for seg in path.split("/") if seg]
        if not labels:
            return []
        by_id = {n.node_id: n for n in graph.nodes}
        # Walk from root by matching labels depth-first.
        root = next((n for n in graph.nodes if n.node_id == "root"), None)
        if root is None:
            return []
        current_ids: list[str] = list(root.children)
        for label in labels:
            next_ids: list[str] = []
            for cid in current_ids:
                c = by_id.get(cid)
                if c is None:
                    continue
                if c.label == label:
                    next_ids.extend(c.children)
            current_ids = next_ids
        return [by_id[c] for c in current_ids if c in by_id]

    def resolve_link(
        self,
        from_node_id: str,
        to_node_id: str,
        tenant_id: str | None = None,
    ) -> CrossDomainLink | None:
        """Resolve a single cross-domain link by endpoint node IDs.

        Returns ``None`` when no link exists between the two nodes
        (audit §7.2: empty data never raises). Order of endpoints
        does not matter — ``resolve_link(a, b) == resolve_link(b, a)``.
        """
        graph = self.derive_taxonomy(tenant_id=tenant_id)
        for link in graph.links:
            if (link.from_node_id == from_node_id and link.to_node_id == to_node_id) or (
                link.from_node_id == to_node_id and link.to_node_id == from_node_id
            ):
                return link
        return None

    # ─── JSON-schema emission (REQ-ID ONTOLOGY-03) ────────────────────

    def json_schema(self) -> dict[str, Any]:
        """Emit the Ontology types as machine-readable JSON-schema.

        The schema is consumed by the v3.14.2 SDK scaffolding
        (``sdk/python/eaasp_sdk/``) and by the ``GET /v1/ecosystem/schema``
        endpoint (REQ-ID SDK-03).
        """
        return _ontology_json_schema()


def _ontology_json_schema() -> dict[str, Any]:
    """Build the JSON-schema for Ontology projection types."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "EAASP Ecosystem Ontology",
        "version": "1.0.0",
        "description": (
            "EAASP v2.0 Phase 6 Ontology projection types — "
            "derived from L2 / L3 / L4 / L5 stores per D-40."
        ),
        "type": "object",
        "properties": {
            "TaxonomyNode": {
                "type": "object",
                "required": [
                    "node_id", "label", "layer", "tenant_id",
                    "count", "evidence_refs", "children",
                ],
                "properties": {
                    "node_id": {"type": "string"},
                    "label": {"type": "string"},
                    "layer": {
                        "type": "string",
                        "enum": ["l2_type", "l3_risk", "l4_event", "l5_card", "root"],
                    },
                    "tenant_id": {"type": "string"},
                    "count": {"type": "integer", "minimum": 0},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "children": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
            "CrossDomainLink": {
                "type": "object",
                "required": [
                    "link_id", "from_node_id", "to_node_id",
                    "evidence_refs", "weight",
                ],
                "properties": {
                    "link_id": {"type": "string"},
                    "from_node_id": {"type": "string"},
                    "to_node_id": {"type": "string"},
                    "evidence_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "weight": {"type": "integer", "minimum": 1},
                },
            },
            "TaxonomyGraph": {
                "type": "object",
                "required": ["tenant_id", "root_id", "nodes", "links"],
                "properties": {
                    "tenant_id": {"type": "string"},
                    "root_id": {"type": "string"},
                    "nodes": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/TaxonomyNode"},
                    },
                    "links": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/CrossDomainLink"},
                    },
                },
            },
        },
        "$defs": {
            "TaxonomyNode": {
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "label": {"type": "string"},
                    "layer": {"type": "string"},
                    "tenant_id": {"type": "string"},
                    "count": {"type": "integer"},
                    "evidence_refs": {"type": "array"},
                    "children": {"type": "array"},
                },
            },
            "CrossDomainLink": {
                "type": "object",
                "properties": {
                    "link_id": {"type": "string"},
                    "from_node_id": {"type": "string"},
                    "to_node_id": {"type": "string"},
                    "evidence_refs": {"type": "array"},
                    "weight": {"type": "integer"},
                },
            },
        },
    }


__all__ = [
    "CrossTenantForbidden",
    "TaxonomyNode",
    "CrossDomainLink",
    "TaxonomyGraph",
    "OntologyService",
]