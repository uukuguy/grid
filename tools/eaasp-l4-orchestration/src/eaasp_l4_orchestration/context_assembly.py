"""SessionPayload assembly helpers — P1..P5 block builder.

MVP scope: produces a JSON-serializable dict matching the SessionPayload proto
shape. Budget flags default per blueprint:

- ``allow_trim_p5=True``  — user preferences are the first to go
- ``allow_trim_p4=False`` — skill instructions are critical
- ``allow_trim_p3=False`` — memory refs are critical in MVP
"""

from __future__ import annotations

import os
from typing import Any


def build_session_payload(
    *,
    session_id: str,
    user_id: str,
    runtime_id: str,
    policy_context: dict[str, Any],
    event_context: dict[str, Any] | None,
    memory_refs: list[dict[str, Any]],
    skill_instructions: dict[str, Any],
    user_preferences: dict[str, Any],
    created_at: int,
) -> dict[str, Any]:
    """Assemble a five-block SessionPayload dict.

    ``memory_refs`` comes from L2 ``/api/v1/memory/search`` hits — the helper
    normalizes each hit into the MemoryRef shape so downstream consumers can
    rely on the keys being present.
    """
    normalized_refs = [_normalize_memory_ref(hit) for hit in (memory_refs or [])]

    return {
        "session_id": session_id,
        "runtime_id": runtime_id,
        "created_at": created_at,
        # P1 — PolicyContext (from L3 validate response).
        "policy_context": _normalize_policy_context(policy_context),
        # P2 — EventContext (currently empty; D32 will backfill from L2 anchors).
        "event_context": event_context or {},
        # P3 — MemoryRefs (from L2 hybrid search).
        "memory_refs": normalized_refs,
        # P4 — SkillInstructions (resolved from L2 registry in later phases).
        "skill_instructions": _normalize_skill_instructions(skill_instructions or {}),
        # P5 — UserPreferences (with LLM provider hint from env).
        "user_preferences": _enrich_user_preferences(
            user_preferences or {"user_id": user_id, "prefs": {}}
        ),
        # Budget trim flags — P5 first, P4/P3 locked in MVP.
        "allow_trim_p5": True,
        # L4-07 / D37 — allow_trim_p4 configurable via env var (copy L3 pattern).
        "allow_trim_p4": os.environ.get("L4_ALLOW_TRIM_P4", "false").lower()
        in ("true", "1"),
        "allow_trim_p3": False,
    }


def _normalize_memory_ref(hit: dict[str, Any]) -> dict[str, Any]:
    """Map an L2 search hit into the MemoryRef dict shape.

    L2 hits vary in shape across versions; fall back to sensible defaults so
    the payload is always well-formed.

    L2's actual response shape (post S3.T2):
        {"hits": [{"memory": {"memory_id": ..., "category": ..., "content": ...},
                   "score": 0.99, "fts_score": 1.0, "time_decay": 0.99}, ...]}
    The L2 hybrid search wraps each memory file inside a ``"memory"`` key
    alongside the ranking signals. Earlier versions surfaced these fields
    flat at the top level (S2 prototype). Both shapes are accepted here so
    L4 stays compatible across L2 minor versions.
    """
    nested = hit.get("memory")
    inner: dict[str, Any] = nested if isinstance(nested, dict) else hit
    return {
        "memory_id": str(inner.get("memory_id") or inner.get("id") or ""),
        "memory_type": str(inner.get("memory_type") or inner.get("category") or ""),
        "relevance_score": float(
            hit.get("score")
            or hit.get("relevance_score")
            or inner.get("relevance_score")
            or 0.0
        ),
        "summary": str(inner.get("summary") or inner.get("content") or ""),
    }


def _normalize_skill_instructions(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize SkillInstructions shape for downstream consumers."""
    if not raw:
        return raw

    # L4-15 / D110 — normalize dependencies to {name, kind} dicts.
    # Backward-compat: flat string deps default to kind="runtime".
    raw_deps = raw.get("dependencies") or []
    normalized_deps: list[dict[str, str]] = []
    for dep in raw_deps:
        if isinstance(dep, str):
            # Legacy flat string → default kind="runtime"
            normalized_deps.append({"name": dep, "kind": "runtime"})
        elif isinstance(dep, dict):
            name = dep.get("name") or dep.get("dep") or ""
            kind = dep.get("kind", "runtime")
            if kind not in ("runtime", "intent"):
                kind = "runtime"  # Invalid kind → default
            if name:
                normalized_deps.append({"name": name, "kind": kind})
        # Silently skip malformed entries (no name).

    return {
        "skill_id": str(raw.get("skill_id") or ""),
        "name": str(raw.get("name") or ""),
        "content": str(raw.get("content") or ""),
        "frontmatter_hooks": list(raw.get("frontmatter_hooks") or []),
        "metadata": dict(raw.get("metadata") or {}),
        "dependencies": normalized_deps,
        # D87 L1 metadata (proto field 7).
        "required_tools": list(raw.get("required_tools") or []),
    }


def _normalize_policy_context(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure PolicyContext always has the expected keys for downstream code."""
    return {
        "hooks": list(raw.get("hooks") or []),
        "policy_version": str(raw.get("policy_version") or ""),
        "deploy_timestamp": str(raw.get("deploy_timestamp") or ""),
        "org_unit": str(raw.get("org_unit") or ""),
        "quotas": dict(raw.get("quotas") or {}),
    }


def _enrich_user_preferences(prefs: dict[str, Any]) -> dict[str, Any]:
    """Inject LLM provider/model hints from environment into P5 UserPreferences.

    L1 runtimes read these as hints; env vars on the runtime side take
    precedence. This allows L4 to suggest a provider/model without forcing it.
    """
    if not prefs.get("llm_provider"):
        llm_provider = os.environ.get("LLM_PROVIDER", "")
        if llm_provider:
            prefs["llm_provider"] = llm_provider
    if not prefs.get("llm_model"):
        llm_model = os.environ.get("LLM_MODEL", "")
        if llm_model:
            prefs["llm_model"] = llm_model
    return prefs
