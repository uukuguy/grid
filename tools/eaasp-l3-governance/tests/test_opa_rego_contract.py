"""Hermetic end-to-end test for the OPABackend ↔ Rego contract (v3.11.1).

Strategy:

- The OPA binary is NOT a build/test dependency (per ADR-V2-034, OPA is a
  sidecar runtime binary downloaded on demand via `make opa-install`).
  CI on machines without OPA still runs the test suite — the OPA adapter
  tests in test_opa_backend.py cover the 5 fail-closed modes via
  MockTransport, and this module covers the *contract* (the shapes the
  adapter sends/receives to the Rego bundle).

- If the OPA binary IS available on the test host (third_party/opac/opa
  or $OPA_BIN), the test starts it as a sidecar on a free port, loads
  the policies/governance.rego bundle, and exercises the real HTTP
  surface end-to-end. This is the "smoke test" path the task spec
  mentions ("如果 OPA 已下载则起临时 sidecar").

- If OPA is NOT available, the test falls back to a HermeticOPAStub
  that returns the *same* response shape the Rego would produce, given
  the input. The stub is the spec-encoded truth table; if the real Rego
  diverges, the diff shows up as soon as OPA is installed and the
  hermetic path is exercised.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from eaasp_l3_governance.opa_backend import (
    DECISION_ALLOW,
    DECISION_APPROVAL,
    DECISION_DENY,
    OPABackend,
    OPAConfig,
)


# ─── Spec truth table (deny-always-wins; spec §15.9) ──────────────────────
#
# This is the *behavior* the Rego policy must encode. The Rego source
# (policies/governance.rego) is the implementation; this table is the
# spec. When OPA is installed and the real path runs, both paths MUST
# agree on the outcome for every (risk_level, mode, tool_name) tuple.
#
# Returned shape matches the OPABackend contract: {allow, decision,
# reason, obligations}.

HERMETIC_TRUTH_TABLE: list[dict[str, Any]] = [
    # ── Read risk: always allowed, no matter the mode ──────────────────
    {
        "input": {"risk_level": "read", "mode": "enforce", "tool_name": "scada_read_snapshot", "action_preview": "read xfmr-042"},
        "expected": {"allow": True, "decision": "allow", "obligations": []},
    },
    {
        "input": {"risk_level": "read", "mode": "shadow", "tool_name": "scada_read_snapshot", "action_preview": "read xfmr-042"},
        "expected": {"allow": True, "decision": "allow", "obligations": []},
    },
    # ── Write in shadow mode: allow + audit obligation ──────────────────
    {
        "input": {"risk_level": "write_local", "mode": "shadow", "tool_name": "local_write", "action_preview": "write foo=bar"},
        "expected": {"allow": True, "decision": "allow", "obligations": ["log:shadow"]},
    },
    {
        "input": {"risk_level": "write_external", "mode": "shadow", "tool_name": "scada_set_setpoint", "action_preview": "xfmr-042/temperature_limit_c=70.0"},
        "expected": {"allow": True, "decision": "allow", "obligations": ["log:shadow"]},
    },
    # ── Write in enforce mode: approval required ───────────────────────
    {
        "input": {"risk_level": "write_local", "mode": "enforce", "tool_name": "local_write", "action_preview": "write foo=bar"},
        "expected": {"allow": False, "decision": "approval", "obligations": ["notify:admin"]},
    },
    {
        "input": {"risk_level": "write_external", "mode": "enforce", "tool_name": "scada_set_setpoint", "action_preview": "xfmr-042/temperature_limit_c=70.0"},
        "expected": {"allow": False, "decision": "approval", "obligations": ["notify:admin"]},
    },
    # ── Deny-list tools: deny regardless of mode (spec §15.9) ──────────
    {
        "input": {"risk_level": "write_external", "mode": "enforce", "tool_name": "rm_rf", "action_preview": "rm -rf /etc"},
        "expected": {"allow": False, "decision": "deny", "obligations": ["log:incident", "alert:security"]},
    },
    {
        "input": {"risk_level": "write_local", "mode": "shadow", "tool_name": "drop_table", "action_preview": "drop accounts"},
        # Even in shadow mode, deny-list wins. The Rego encodes this as a
        # separate rule that runs after the allow/approval block; in the
        # stub we collapse the outcome to the spec contract.
        "expected": {"allow": False, "decision": "deny", "obligations": ["log:incident", "alert:security"]},
    },
    # ── Destructive preview pattern: deny regardless of mode ───────────
    {
        "input": {"risk_level": "write_external", "mode": "enforce", "tool_name": "sql", "action_preview": "DROP TABLE users"},
        "expected": {"allow": False, "decision": "deny", "obligations": ["log:incident", "alert:security"]},
    },
]


# ─── Hermetic stub (OPA-less path) ──────────────────────────────────────────


def _stub_decide(input_payload: dict[str, Any]) -> dict[str, Any]:
    """Encode the same truth table as the Rego policy.

    Used as a fallback when the OPA binary is not available. The Rego
    source (policies/governance.rego) is the primary implementation; this
    Python re-encoding is the *contract test* — if it diverges from the
    real OPA output, that divergence is captured as a test failure the
    moment a developer runs against a real OPA.
    """
    risk = input_payload.get("risk_level")
    mode = input_payload.get("mode")
    tool = input_payload.get("tool_name", "")
    preview = input_payload.get("action_preview", "")

    # Deny-list tools (spec §15.9 — deny-always-wins)
    if tool in {"rm_rf", "format_disk", "drop_table", "shutdown_host", "kill_all_sessions"}:
        return {
            "allow": False,
            "decision": "deny",
            "reason": f"tool {tool!r} is on the deny-list (spec §15.9)",
            "obligations": ["log:incident", "alert:security"],
        }
    # Destructive preview patterns
    if "rm -rf /" in preview or "DROP TABLE" in preview:
        return {
            "allow": False,
            "decision": "deny",
            "reason": "action_preview matches a destructive pattern (spec §15.9)",
            "obligations": ["log:incident", "alert:security"],
        }
    # Read risk: always allow
    if risk == "read":
        return {
            "allow": True,
            "decision": "allow",
            "reason": "read risk auto-allowed (spec §6.10)",
            "obligations": [],
        }
    # Write + shadow: allow + log
    if mode == "shadow":
        return {
            "allow": True,
            "decision": "allow",
            "reason": f"shadow mode permits {risk} (audit §5.2)",
            "obligations": ["log:shadow"],
        }
    # Write + enforce: approval required
    if mode == "enforce":
        return {
            "allow": False,
            "decision": "approval",
            "reason": f"{risk} in enforce mode requires human approval (spec §6.10)",
            "obligations": ["notify:admin"],
        }
    # Unknown mode: fail-closed (the Rego's default decision is deny).
    return {
        "allow": False,
        "decision": "deny",
        "reason": "default deny (unknown mode)",
        "obligations": [],
    }


# ─── Test class: each row in HERMETIC_TRUTH_TABLE is a parametrized test ──


def _build_stub_backend() -> OPABackend:
    """Build an OPABackend that points at a MockTransport implementing the
    hermetic stub. Used when the real OPA binary is not available."""
    cfg = OPAConfig(
        base_url="http://127.0.0.1:18181",
        timeout_seconds=2.0,
        bundle_dir="/tmp",
    )

    async def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        # OPA REST API wraps the request in {"input": ...}; the stub
        # operates on the inner input shape (not the OPA wire envelope).
        result = _stub_decide(body["input"])
        return httpx.Response(200, json={"result": result})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OPABackend(cfg, client=client)


@pytest.mark.parametrize("row", HERMETIC_TRUTH_TABLE, ids=lambda r: f"{r['input']['tool_name']}_{r['input']['risk_level']}_{r['input']['mode']}")
async def test_hermetic_stub_matches_truth_table(row: dict[str, Any]) -> None:
    """The hermetic stub (which encodes the same logic as the Rego
    policy) MUST return the documented outcome for every (risk, mode,
    tool) tuple. This is the contract guard: if the Rego policy ever
    diverges from this table, the real-OPA path test below will catch
    it on the next OPA install."""
    backend = _build_stub_backend()
    result = await backend.evaluate(row["input"])
    expected = row["expected"]
    assert result.allow == expected["allow"], f"allow mismatch: {result} vs {expected}"
    assert result.decision == expected["decision"], f"decision mismatch: {result} vs {expected}"
    for ob in expected["obligations"]:
        assert ob in result.obligations, f"missing obligation {ob!r} in {result.obligations}"
    await backend.aclose()


# ─── Real OPA path (runs only if opa binary is on disk) ────────────────────


def _opa_binary_path() -> str | None:
    """Return the path to the OPA binary if installed, else None.

    Looks in third_party/opac/opa (per scripts/eaasp-install-opa.sh) and
    in $OPA_BIN (override) and in $PATH."""
    repo_root = Path(__file__).resolve().parents[3]  # tools/eaasp-l3-governance/tests → repo root
    candidates = [
        os.environ.get("OPA_BIN"),
        str(repo_root / "third_party" / "opac" / "opa"),
        shutil.which("opa"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def _free_port() -> int:
    """Return an unused localhost port. Best-effort: the OS may re-use
    the port between this call and the OPA listen call. Tests that need
    stronger guarantees should pin the port and retry on EADDRINUSE."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.mark.skipif(
    _opa_binary_path() is None,
    reason="OPA binary not installed (run `make opa-install` to enable the real-OPA path)",
)
async def test_real_opa_sidecar_returns_truth_table() -> None:
    """End-to-end: start the real OPA sidecar on a free port, load
    policies/governance.rego, exercise every row in the truth table.

    This is the gold-master test for v3.11.1 — if it fails after a
    policy edit, the Rego source no longer matches the spec.
    """
    opa_bin = _opa_binary_path()
    assert opa_bin is not None
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    bundle_dir = str(Path(__file__).resolve().parent.parent / "policies")

    # Start OPA: `opa run -s -b <bundle_dir> --addr <addr>` (server mode)
    proc = subprocess.Popen(
        [opa_bin, "run", "-s", "-b", bundle_dir, "--addr", f"127.0.0.1:{port}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # Wait for OPA to be reachable. Health endpoint: GET /health
        deadline = time.time() + 10.0
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                async with httpx.AsyncClient(timeout=1.0) as c:
                    r = await c.get(f"{base_url}/health")
                    if r.status_code in (200, 204):
                        break
            except Exception as e:  # noqa: BLE001
                last_err = e
                await asyncio.sleep(0.1)
        else:
            stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
            raise RuntimeError(
                f"OPA sidecar did not become healthy within 10s. "
                f"Last err: {last_err!r}. Stderr: {stderr[:500]}"
            )

        # Exercise every row in the truth table
        cfg = OPAConfig(base_url=base_url, timeout_seconds=2.0, bundle_dir=bundle_dir)
        async with OPABackend(cfg) as backend:
            for row in HERMETIC_TRUTH_TABLE:
                result = await backend.evaluate(row["input"])
                expected = row["expected"]
                assert result.allow == expected["allow"], (
                    f"OPA truth-table mismatch for input {row['input']!r}: "
                    f"allow={result.allow}, expected={expected['allow']}, "
                    f"decision={result.decision!r}, reason={result.reason!r}"
                )
                assert result.decision == expected["decision"], (
                    f"OPA truth-table mismatch for input {row['input']!r}: "
                    f"decision={result.decision!r}, expected={expected['decision']!r}, "
                    f"reason={result.reason!r}"
                )
                # Obligations: spec-defined subset must be present; the
                # Rego may add more (e.g. obligations_by_risk) so we only
                # assert the documented obligations are in the result.
                for ob in expected["obligations"]:
                    assert ob in result.obligations, (
                        f"missing obligation {ob!r} in {result.obligations} "
                        f"for input {row['input']!r}"
                    )
    finally:
        # Graceful shutdown: send SIGTERM, then SIGKILL after 2s
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=1.0)


# ─── Rego file structural test (hermetic, always runs) ─────────────────────


def test_rego_bundle_file_exists_and_is_nonempty() -> None:
    """The in-repo Rego bundle must exist and have content. This guards
    against an accidental `git rm` of the policy file breaking the
    ADR-V2-034 §Decision item 2 'in-repo Rego templates' commitment."""
    policies_dir = Path(__file__).resolve().parent.parent / "policies"
    assert policies_dir.is_dir(), f"policies dir missing: {policies_dir}"
    rego = policies_dir / "governance.rego"
    data = policies_dir / "data.json"
    assert rego.is_file(), f"governance.rego missing: {rego}"
    assert rego.stat().st_size > 100, "governance.rego is unexpectedly small"
    assert data.is_file(), f"data.json missing: {data}"
    parsed = json.loads(data.read_text())
    assert "governance" in parsed
    assert "deny_list" in parsed["governance"]
    assert "tools" in parsed["governance"]["deny_list"]


def test_rego_bundle_cites_spec_sections() -> None:
    """The Rego file MUST cite the v2.0 spec sections it implements.
    This is the traceability requirement (REQ-EAASP-01..08 family +
    ADR-V2-034 §Decision item 1) — without these refs, a future Rego
    edit loses its spec anchor and the deny-always-wins rule can
    silently drift."""
    rego = (Path(__file__).resolve().parent.parent / "policies" / "governance.rego").read_text()
    for spec_ref in ("§6.1", "§6.9", "§6.10", "§15.9"):
        assert spec_ref in rego, f"Rego bundle missing spec ref: {spec_ref}"
    assert "ADR-V2-034" in rego, "Rego bundle missing ADR-V2-034 reference"
