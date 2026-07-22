"""Deterministic SCADA telemetry samples used by the mock MCP server.

Keeping the samples here (not in server.py) lets tests import and assert on
them without needing to boot an MCP stdio transport.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

SCADA_WRITE_ERROR_MARKER = "scada_write_is_blocked"

SAMPLE_DEVICE_IDS: tuple[str, ...] = (
    "xfmr-042",
    "brk-17",
    "reactor-9",
)

_DEVICE_BASELINES: dict[str, dict[str, float]] = {
    "xfmr-042": {
        "temperature_c": 64.2,
        "load_pct": 0.78,
        "doa_h2_ppm": 24.3,
    },
    "brk-17": {
        "temperature_c": 41.8,
        "load_pct": 0.55,
        "doa_h2_ppm": 6.1,
    },
    "reactor-9": {
        "temperature_c": 72.5,
        "load_pct": 0.84,
        "doa_h2_ppm": 31.7,
    },
}

_DEFAULT_BASELINE: dict[str, float] = {
    "temperature_c": 60.0,
    "load_pct": 0.70,
    "doa_h2_ppm": 20.0,
}


# REQ-EAASP-06 (Phase 3.7.3): deterministic in-memory setpoint store for S8.
# Single-process fixture; the same store instance backs every ``scada_set_setpoint``
# call within one MCP server process. A hermetic test can call
# ``reset_setpoints_for_tests()`` to start from a clean baseline.
_SETPOINTS: dict[str, dict[str, float]] = {
    "xfmr-042": {
        "temperature_limit_c": 65.0,
    },
}

DEFAULT_S8_DEVICE = "xfmr-042"
DEFAULT_S8_SETPOINT = "temperature_limit_c"
DEFAULT_S8_VALUE = 70.0


def build_snapshot(device_id: str, time_window: str = "5m") -> dict[str, Any]:
    """Return a deterministic telemetry snapshot for a device.

    Output shape is stable across calls (given the same inputs) so e2e
    assertions and snapshot hashes are reproducible.
    """
    baseline = _DEVICE_BASELINES.get(device_id, _DEFAULT_BASELINE)
    samples = [
        {
            "t_offset_s": -240,
            "temperature_c": round(baseline["temperature_c"] - 1.1, 3),
            "load_pct": round(baseline["load_pct"] - 0.02, 3),
            "doa_h2_ppm": round(baseline["doa_h2_ppm"] - 0.8, 3),
        },
        {
            "t_offset_s": -120,
            "temperature_c": round(baseline["temperature_c"] - 0.3, 3),
            "load_pct": round(baseline["load_pct"] - 0.01, 3),
            "doa_h2_ppm": round(baseline["doa_h2_ppm"] - 0.2, 3),
        },
        {
            "t_offset_s": 0,
            "temperature_c": round(baseline["temperature_c"] + 0.6, 3),
            "load_pct": round(baseline["load_pct"] + 0.02, 3),
            "doa_h2_ppm": round(baseline["doa_h2_ppm"] + 0.5, 3),
        },
    ]
    return {
        "device_id": device_id,
        "time_window": time_window,
        "sample_count": len(samples),
        "samples": samples,
        "baseline": {
            "temperature_c": baseline["temperature_c"],
            "load_pct": baseline["load_pct"],
            "doa_h2_ppm": baseline["doa_h2_ppm"],
        },
    }


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    """Return a stable sha256 digest of a snapshot.

    Callers (skill authoring + e2e assertions) use this as the
    `snapshot_hash` argument to L2 `memory_write_anchor`.
    """
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ─── REQ-EAASP-06 — S8 setpoint helpers ─────────────────────────────────────


def get_setpoint(device_id: str, setpoint_name: str) -> float:
    """Return the current deterministic setpoint value.

    Raises ``KeyError`` if either the device or setpoint name is unknown —
    callers (skill instructions) must only invoke this for the S8 fixtures
    declared in the skill manifest.
    """
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("device_id must be a non-empty string")
    if not isinstance(setpoint_name, str) or not setpoint_name:
        raise ValueError("setpoint_name must be a non-empty string")
    return _SETPOINTS[device_id][setpoint_name]


def set_setpoint(device_id: str, setpoint_name: str, value: float) -> dict[str, Any]:
    """Atomically update a setpoint and return a result envelope.

    Validates input before mutating state, so invalid input never changes the
    stored value (audit §8.1 — "invalid input leaves state unchanged").
    """
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("device_id must be a non-empty string")
    if not isinstance(setpoint_name, str) or not setpoint_name:
        raise ValueError("setpoint_name must be a non-empty string")
    if not isinstance(value, (int, float)):
        raise ValueError(f"value must be a finite number, got {type(value).__name__}")
    fvalue = float(value)
    if not math.isfinite(fvalue):
        raise ValueError(f"value must be finite, got {value!r}")

    bucket = _SETPOINTS.setdefault(device_id, {})
    previous = bucket.get(setpoint_name)
    bucket[setpoint_name] = fvalue
    return {
        "device_id": device_id,
        "setpoint_name": setpoint_name,
        "previous_value": previous,
        "value": fvalue,
        "status": "updated",
    }


def reset_setpoints_for_tests() -> None:
    """Hermetic fixture reset — restores ``_SETPOINTS`` to its S8 baseline.

    NOT exposed via MCP / network. Tests that want isolation should call
    this in a fixture; production code never reaches it.
    """
    _SETPOINTS.clear()
    _SETPOINTS["xfmr-042"] = {"temperature_limit_c": 65.0}
