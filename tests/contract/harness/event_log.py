"""EventStreamEntry capture helper for the contract observability tests.

Phase 7.1 T02 (CONTRACT-01 / D137 part 2). The grid-runtime
`PreCompactEmitter` hook (`crates/grid-runtime/src/pre_compact_emitter.rs`)
appends a JSON line per PRE_COMPACT firing to
``${GRID_CONTRACT_PROBE_OUT}/events.jsonl``. This module reads that file
and surfaces the captured event types as a `list[str]` so contract
tests can assert against the canonical `EVENT_TYPES_V1` whitelist
(see `tests/contract/harness/assertions.py`).

The file is opened with ``encoding="utf-8"`` and tolerates missing /
partial / non-JSON lines; the runtime's `PreCompactEmitter` writes one
line per fire with ``writeln!`` so torn writes are unlikely but not
impossible across concurrent fires. Any malformed line is logged and
skipped rather than raising.

The capture file is **append-only** — tests that want to assert against
a fresh window should call :func:`clear_captured_events` before
driving the runtime turn that may emit.
"""

from __future__ import annotations

import json
from pathlib import Path


def _events_path(probe_out_dir: str | Path) -> Path:
    return Path(probe_out_dir) / "events.jsonl"


def clear_captured_events(probe_out_dir: str | Path) -> None:
    """Truncate the events.jsonl capture file (no-op if absent).

    Use BEFORE driving the runtime so subsequent
    :func:`fetch_captured_events` returns only events from the new
    window.
    """
    path = _events_path(probe_out_dir)
    if path.exists():
        path.unlink()


def fetch_captured_events(probe_out_dir: str | Path) -> list[str]:
    """Return the ordered list of `event_type` strings captured so far.

    The capture file at ``${probe_out_dir}/events.jsonl`` is one JSON
    object per line, each carrying at minimum an ``event_type`` key
    (e.g. ``"PRE_COMPACT"``). Missing file ⇒ empty list. Malformed JSON
    lines are skipped silently.
    """
    path = _events_path(probe_out_dir)
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        et = obj.get("event_type")
        if isinstance(et, str):
            out.append(et)
    return out


def fetch_captured_event_records(
    probe_out_dir: str | Path,
) -> list[dict]:
    """Return the full captured event objects (debug / introspection).

    Tests that need to assert on more than just the event_type (e.g.
    `trigger`, `usage_pct`) call this instead of
    :func:`fetch_captured_events`.
    """
    path = _events_path(probe_out_dir)
    if not path.exists():
        return []
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out
