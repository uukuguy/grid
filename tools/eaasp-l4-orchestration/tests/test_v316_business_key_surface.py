"""HTTP coverage for persisted L4 session business-key reads."""

from __future__ import annotations

import httpx

from eaasp_l4_orchestration.db import connect


async def _insert_session(
    db_path: str,
    *,
    session_id: str,
    status: str,
    business_key: str | None,
    created_at: int,
) -> None:
    db = await connect(db_path)
    try:
        await db.execute(
            """
            INSERT INTO sessions
                (session_id, skill_id, runtime_id, status, payload_json,
                 created_at, business_key)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                "skill.test",
                "grid-runtime",
                status,
                "{}",
                created_at,
                business_key,
            ),
        )
        await db.commit()
    finally:
        await db.close()


async def test_session_read_endpoints_return_persisted_business_key(
    app_client: httpx.AsyncClient,
    tmp_db_path: str,
) -> None:
    """GET and both list branches preserve populated and legacy NULL values."""
    business_key = "session-a|skill.test|work-order-7"
    await _insert_session(
        tmp_db_path,
        session_id="sess_with_key",
        status="active",
        business_key=business_key,
        created_at=200,
    )
    await _insert_session(
        tmp_db_path,
        session_id="sess_legacy_null",
        status="active",
        business_key=None,
        created_at=100,
    )

    populated = await app_client.get("/v1/sessions/sess_with_key")
    assert populated.status_code == 200
    assert populated.json()["business_key"] == business_key

    legacy = await app_client.get("/v1/sessions/sess_legacy_null")
    assert legacy.status_code == 200
    assert legacy.json()["business_key"] is None

    unfiltered = await app_client.get("/v1/sessions")
    assert unfiltered.status_code == 200
    assert {
        row["session_id"]: row["business_key"]
        for row in unfiltered.json()["sessions"]
    } == {
        "sess_with_key": business_key,
        "sess_legacy_null": None,
    }

    filtered = await app_client.get("/v1/sessions?status=active")
    assert filtered.status_code == 200
    assert filtered.json()["sessions"] == [
        {
            "session_id": "sess_with_key",
            "status": "active",
            "runtime_id": "grid-runtime",
            "skill_id": "skill.test",
            "created_at": 200,
            "closed_at": None,
            "business_key": business_key,
        },
        {
            "session_id": "sess_legacy_null",
            "status": "active",
            "runtime_id": "grid-runtime",
            "skill_id": "skill.test",
            "created_at": 100,
            "closed_at": None,
            "business_key": None,
        },
    ]
