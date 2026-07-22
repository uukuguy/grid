from __future__ import annotations

import json

import pytest

from mock_scada.server import (
    SERVER_NAME,
    SERVER_VERSION,
    _TOOL_MANIFEST,
    _handle_scada_read_snapshot,
    _handle_scada_set_setpoint,
    _handle_scada_write,
    build_server,
)
from mock_scada.snapshots import (
    SCADA_WRITE_ERROR_MARKER,
    DEFAULT_S8_DEVICE,
    DEFAULT_S8_SETPOINT,
    DEFAULT_S8_VALUE,
    get_setpoint,
    reset_setpoints_for_tests,
    set_setpoint,
)


@pytest.fixture(autouse=True)
def _reset_setpoints() -> None:
    """Per-test isolation: start each test from the canonical S8 baseline."""
    reset_setpoints_for_tests()


def test_server_identity() -> None:
    assert SERVER_NAME == "mock-scada"
    assert SERVER_VERSION == "0.1.0"


def test_tool_manifest_exposes_all_three_tools() -> None:
    names = {tool.name for tool in _TOOL_MANIFEST}
    assert names == {
        "scada_read_snapshot",
        "scada_write",
        "scada_set_setpoint",
    }


def test_tool_manifest_schemas_mark_required_fields() -> None:
    by_name = {tool.name: tool for tool in _TOOL_MANIFEST}

    read_schema = by_name["scada_read_snapshot"].inputSchema
    assert read_schema["type"] == "object"
    assert read_schema["required"] == ["device_id"]
    assert "device_id" in read_schema["properties"]
    assert "time_window" in read_schema["properties"]

    write_schema = by_name["scada_write"].inputSchema
    assert set(write_schema["required"]) == {"device_id", "field", "value"}

    setpoint_schema = by_name["scada_set_setpoint"].inputSchema
    assert set(setpoint_schema["required"]) == {"device_id", "setpoint_name", "value"}


def test_read_snapshot_returns_telemetry_with_hash() -> None:
    result = _handle_scada_read_snapshot({"device_id": "xfmr-042", "time_window": "5m"})
    assert result["device_id"] == "xfmr-042"
    assert result["sample_count"] >= 1
    assert isinstance(result["snapshot_hash"], str)
    assert len(result["snapshot_hash"]) == 64  # sha256 hex


def test_read_snapshot_defaults_time_window_when_missing_or_empty() -> None:
    result = _handle_scada_read_snapshot({"device_id": "xfmr-042"})
    assert result["time_window"] == "5m"

    result2 = _handle_scada_read_snapshot({"device_id": "xfmr-042", "time_window": ""})
    assert result2["time_window"] == "5m"


def test_read_snapshot_rejects_missing_device_id() -> None:
    with pytest.raises(ValueError, match="device_id"):
        _handle_scada_read_snapshot({})
    with pytest.raises(ValueError, match="device_id"):
        _handle_scada_read_snapshot({"device_id": ""})
    with pytest.raises(ValueError, match="device_id"):
        _handle_scada_read_snapshot({"device_id": 42})  # type: ignore[dict-item]


def test_scada_write_always_fails_with_marker() -> None:
    with pytest.raises(RuntimeError) as exc_info:
        _handle_scada_write(
            {"device_id": "xfmr-042", "field": "setpoint", "value": 1}
        )
    assert SCADA_WRITE_ERROR_MARKER in str(exc_info.value)
    # Error body must preserve args so callers/tests can assert on them.
    payload = str(exc_info.value).split("args=", 1)[1]
    parsed = json.loads(payload)
    assert parsed == {"device_id": "xfmr-042", "field": "setpoint", "value": 1}


def test_build_server_returns_configured_instance() -> None:
    server = build_server()
    assert server.name == SERVER_NAME


# ─── REQ-EAASP-06 — S8 setpoint fixture tests ───────────────────────────────


def test_scada_set_setpoint_updates_in_memory_value() -> None:
    before = get_setpoint(DEFAULT_S8_DEVICE, DEFAULT_S8_SETPOINT)
    assert before == 65.0  # canonical S8 baseline

    result = _handle_scada_set_setpoint(
        {
            "device_id": DEFAULT_S8_DEVICE,
            "setpoint_name": DEFAULT_S8_SETPOINT,
            "value": DEFAULT_S8_VALUE,
        }
    )
    assert result["status"] == "updated"
    assert result["previous_value"] == 65.0
    assert result["value"] == 70.0

    after = get_setpoint(DEFAULT_S8_DEVICE, DEFAULT_S8_SETPOINT)
    assert after == 70.0


def test_scada_set_setpoint_rejects_invalid_value_and_keeps_state() -> None:
    before = get_setpoint(DEFAULT_S8_DEVICE, DEFAULT_S8_SETPOINT)
    assert before == 65.0

    # NaN
    with pytest.raises(ValueError, match="finite"):
        _handle_scada_set_setpoint(
            {
                "device_id": DEFAULT_S8_DEVICE,
                "setpoint_name": DEFAULT_S8_SETPOINT,
                "value": float("nan"),
            }
        )
    # Inf
    with pytest.raises(ValueError, match="finite"):
        _handle_scada_set_setpoint(
            {
                "device_id": DEFAULT_S8_DEVICE,
                "setpoint_name": DEFAULT_S8_SETPOINT,
                "value": float("inf"),
            }
        )
    # String
    with pytest.raises(ValueError):
        _handle_scada_set_setpoint(
            {
                "device_id": DEFAULT_S8_DEVICE,
                "setpoint_name": DEFAULT_S8_SETPOINT,
                "value": "70",  # type: ignore[dict-item]
            }
        )
    # Empty device_id / setpoint_name
    with pytest.raises(ValueError, match="device_id"):
        _handle_scada_set_setpoint(
            {
                "device_id": "",
                "setpoint_name": DEFAULT_S8_SETPOINT,
                "value": DEFAULT_S8_VALUE,
            }
        )
    with pytest.raises(ValueError, match="setpoint_name"):
        _handle_scada_set_setpoint(
            {
                "device_id": DEFAULT_S8_DEVICE,
                "setpoint_name": "",
                "value": DEFAULT_S8_VALUE,
            }
        )

    after = get_setpoint(DEFAULT_S8_DEVICE, DEFAULT_S8_SETPOINT)
    assert after == 65.0, "invalid input must not mutate the store"


def test_set_setpoint_helper_returns_previous_value_on_update() -> None:
    out = set_setpoint("xfmr-042", "temperature_limit_c", 70.0)
    assert out == {
        "device_id": "xfmr-042",
        "setpoint_name": "temperature_limit_c",
        "previous_value": 65.0,
        "value": 70.0,
        "status": "updated",
    }


def test_reset_setpoints_restores_canonical_s8_baseline() -> None:
    # mutate
    set_setpoint("xfmr-042", "temperature_limit_c", 99.0)
    assert get_setpoint("xfmr-042", "temperature_limit_c") == 99.0
    # reset
    reset_setpoints_for_tests()
    assert get_setpoint("xfmr-042", "temperature_limit_c") == 65.0
