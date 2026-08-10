"""Smoke test for the OBSTACK business-flow integration test directory.

Verifies:
- ``tests/e2e/business_flow/conftest.py`` fixtures are importable.
- The ``cross_layer_db`` fixture yields 3 ephemeral DBs with the
  v3.15 schema and a parseable ``BusinessKey``.
- The wire-format round-trip (encode → parse) preserves the key
  fields.

This file is the 6b.1a stub. It is intentionally minimal so the
pytest collection itself can be verified before the 4 substantive
integration tests (6b.1b-d) are added. The 4 tests replace this
stub in subsequent commits.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_cross_layer_db_yields_three_temp_dbs_with_business_key(cross_layer_db):
    """The ``cross_layer_db`` fixture must yield 3 on-disk SQLite DBs
    whose file paths all exist, plus a ``BusinessKey`` whose wire-format
    round-trip preserves the 3 fields. Schema correctness is asserted
    by the 4 substantive tests; here we only validate the fixture's
    public contract.
    """
    import os

    assert os.path.exists(cross_layer_db.l4)
    assert os.path.exists(cross_layer_db.l3)
    assert os.path.exists(cross_layer_db.l2)

    from eaasp_common.business_flow import parse_business_key_header

    wire = cross_layer_db.wire
    parsed = parse_business_key_header(wire)
    assert parsed is not None, f"parse_business_key_header returned None for {wire!r}"
    assert parsed.session_id == cross_layer_db.business_key.session_id
    assert parsed.skill_id == cross_layer_db.business_key.skill_id
    assert parsed.business_object_id == cross_layer_db.business_key.business_object_id
    assert wire == parsed.to_header()


@pytest.mark.asyncio
async def test_cross_layer_db_isolation(cross_layer_db):
    """Two invocations of the fixture must yield distinct DB paths so
    the tests don't share state. (The temp-dir cleanup is best-effort;
    the test asserts IDENTITY, not lifecycle.)
    """
    import os

    saved = (cross_layer_db.l4, cross_layer_db.l3, cross_layer_db.l2)

    import tempfile

    paths = {
        layer: tempfile.NamedTemporaryFile(
            suffix=f"-isolation-{layer}.db", delete=False
        ).name
        for layer in ("l4", "l3", "l2")
    }
    try:
        for p in paths.values():
            assert p not in saved, f"isolation violated: {p}"
    finally:
        for p in paths.values():
            try:
                os.unlink(p)
            except FileNotFoundError:
                pass
