"""Phase 5.3 CONTRACT-01 — CLI _ALLOWED_CHUNK_TYPES whitelist regression.

Pins the literal CLI whitelist against the contract-v1.2.0 expected set.
The authoritative descriptor-vs-whitelist drift guard lives at
`tests/contract/cases/test_chunk_type_contract.py::test_whitelist_matches_adr`
(common to all runtimes); this file is a CLI-local copy so a CLI
maintainer running just `pytest tools/eaasp-cli-v2/tests/` sees the
break immediately without spinning up the full contract harness.

Created by Phase 5.3 Plan A Task 5.3-01-06 — complementary to the
existing `test_cmd_session_chunk_types.py` whitelist test (which was
updated to the 9-value set in the same task).
"""

from __future__ import annotations

from eaasp_cli_v2.cmd_session import _ALLOWED_CHUNK_TYPES

# Canonical set for contract-v1.2.0 — kept in sync with
# `proto/eaasp/runtime/v2/common.proto` ChunkType enum (ADR-V2-021,
# Phase 5.3 amendment).
_EXPECTED_CHUNK_TYPES = frozenset(
    {
        "text_delta",
        "thinking",
        "tool_start",
        "tool_result",
        "done",
        "error",
        "workflow_continuation",
        # Phase 5.3 (contract-v1.2.0):
        "thinking_trace",
        "attachment_ref",
    }
)


def test_whitelist_contains_new_5_3_wires() -> None:
    """Concrete pin of the 5.3 additions (defensive readability check)."""
    assert "thinking_trace" in _ALLOWED_CHUNK_TYPES
    assert "attachment_ref" in _ALLOWED_CHUNK_TYPES


def test_whitelist_matches_contract_v1_2_0() -> None:
    """CLI whitelist MUST equal the canonical contract-v1.2.0 set.

    If this fails, either (1) the proto enum grew and the CLI did not
    follow (run `make build-eaasp-all` to confirm + update
    `_ALLOWED_CHUNK_TYPES`), or (2) the CLI inserted a stray value that
    is not in the proto enum (delete it — contract-level drift).
    """
    assert _ALLOWED_CHUNK_TYPES == _EXPECTED_CHUNK_TYPES, (
        f"CLI whitelist drift detected.\n"
        f"Missing: {_EXPECTED_CHUNK_TYPES - _ALLOWED_CHUNK_TYPES}\n"
        f"Extra: {_ALLOWED_CHUNK_TYPES - _EXPECTED_CHUNK_TYPES}"
    )
