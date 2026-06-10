"""Tests for NLU resolver and intent dispatch integration.

Unit tests (IntentResolver) and respx-mocked integration tests (API dispatch
with NLU branch). Per ROADMAP Pitfall 1: every new L4→L2/L3 call path must
have respx-mocked test.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from eaasp_l4_orchestration.nlu_resolver import IntentResolver, NoSkillMatchError

L2_DEFAULT = "http://127.0.0.1:18085"
L3_DEFAULT = "http://127.0.0.1:18083"

# ─── Unit tests for IntentResolver (no HTTP) ────────────────────────────────


def test_resolve_exact_match() -> None:
    """Intent text that closely matches a skill name+description resolves."""
    resolver = IntentResolver()
    resolver.build_index_from_list(
        [
            {
                "skill_id": "skill.deploy-scada",
                "name": "Deploy SCADA",
                "description": "Deploy SCADA calibration",
            },
            {
                "skill_id": "skill.read-modbus",
                "name": "Read Modbus",
                "description": "Read Modbus registers",
            },
        ]
    )
    skill_id, candidates = resolver.resolve_intent("deploy the scada calibration")
    assert skill_id == "skill.deploy-scada"
    assert len(candidates) >= 1
    assert candidates[0]["score"] >= 0.6


def test_resolve_typo_tolerant() -> None:
    """Typo in intent text still matches via token_sort_ratio."""
    resolver = IntentResolver()
    resolver.build_index_from_list(
        [
            {
                "skill_id": "skill.deploy-scada",
                "name": "Deploy SCADA",
                "description": "Calibration workflow",
            },
        ]
    )
    skill_id, _ = resolver.resolve_intent("deploy the scada calibraton")  # typo
    assert skill_id == "skill.deploy-scada"


def test_resolve_below_threshold_returns_none() -> None:
    """Intent unrelated to any skill returns None + ranked candidates."""
    resolver = IntentResolver(confidence_threshold=0.6)
    resolver.build_index_from_list(
        [
            {
                "skill_id": "skill.deploy-scada",
                "name": "Deploy SCADA",
                "description": "",
            },
            {"skill_id": "skill.read-modbus", "name": "Read Modbus", "description": ""},
        ]
    )
    skill_id, candidates = resolver.resolve_intent("completely unrelated query")
    assert skill_id is None
    assert len(candidates) > 0  # Still returns ranked list for disambiguation


def test_resolve_empty_index_raises() -> None:
    """Empty index raises NoSkillMatchError."""
    resolver = IntentResolver()
    with pytest.raises(NoSkillMatchError):
        resolver.resolve_intent("anything")


def test_resolve_with_10plus_skills() -> None:
    """D34 success criteria: tested with full skill-registry fixture (≥10 skills)."""
    skills = []
    for i in range(15):
        skills.append(
            {
                "skill_id": f"skill.test-{i}",
                "name": f"Test Skill {i}",
                "description": f"Description for test skill {i}",
            }
        )
    resolver = IntentResolver()
    resolver.build_index_from_list(skills)
    skill_id, candidates = resolver.resolve_intent("test skill 7")
    assert skill_id == "skill.test-7"
    assert len(candidates) >= 1


def test_resolve_skill_without_description() -> None:
    """Skill with no description still matches via name only."""
    resolver = IntentResolver()
    resolver.build_index_from_list(
        [
            {"skill_id": "skill.only-name", "name": "Only Name"},
        ]
    )
    skill_id, _ = resolver.resolve_intent("only name")
    assert skill_id == "skill.only-name"


def test_resolve_skips_empty_skill_id() -> None:
    """Skills with empty skill_id are skipped with warning, not added to index."""
    resolver = IntentResolver()
    resolver.build_index_from_list(
        [
            {"skill_id": "", "name": "Bad Skill", "description": "no id"},
            {"skill_id": "skill.good", "name": "Good Skill", "description": ""},
        ]
    )
    skill_id, _ = resolver.resolve_intent("good skill")
    assert skill_id == "skill.good"


# ─── Integration tests: NLU dispatch via API (respx-mocked) ─────────────────


@respx.mock
async def test_dispatch_intent_without_skill_id_resolves_via_nlu(
    app_client: httpx.AsyncClient,
) -> None:
    """D34: POST /v1/intents/dispatch without skill_id uses NLU to find one."""
    # Mock L2 search (required by handshake).
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    # Mock L3 validate (required by handshake).
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )

    resp = await app_client.post(
        "/v1/intents/dispatch",
        json={
            "intent_text": "deploy scada calibration",
            "skill_id": "",  # Empty → NLU should resolve.
            "runtime_pref": "strict",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"
    # The session should have been created with the resolved skill_id.
    sid = body["session_id"]
    get_resp = await app_client.get(f"/v1/sessions/{sid}")
    assert get_resp.status_code == 200
    # Verify the skill was resolved (not empty).
    assert get_resp.json()["skill_id"] != ""


@respx.mock
async def test_dispatch_intent_ambiguous_returns_300(
    app_client: httpx.AsyncClient,
) -> None:
    """D34: Intent below confidence threshold returns 300 with candidate list."""
    # No L2/L3 mocks needed — should fail before handshake.
    resp = await app_client.post(
        "/v1/intents/dispatch",
        json={
            "intent_text": "xyzzy something totally unrelated to any skill",
            "skill_id": "",
            "runtime_pref": "strict",
        },
    )
    # Should return 300 (ambiguous) or 400 (no skills) depending on
    # whether any candidate meets threshold.
    assert resp.status_code in (300, 400), resp.text
    if resp.status_code == 300:
        detail = resp.json()["detail"]
        assert detail["code"] == "ambiguous_intent"
        assert len(detail["candidates"]) > 0
    else:
        detail = resp.json()["detail"]
        assert detail["code"] == "no_skills_available"


@respx.mock
async def test_dispatch_intent_with_skill_id_still_works(
    app_client: httpx.AsyncClient,
) -> None:
    """D34: Existing skill_id path is preserved — NLU is a fallback, not replacement."""
    respx.post(f"{L2_DEFAULT}/api/v1/memory/search").mock(
        return_value=httpx.Response(200, json={"hits": []})
    )
    respx.post(url__regex=rf"{L3_DEFAULT}/v1/sessions/.*/validate").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "placeholder",
                "hooks_to_attach": [],
                "managed_settings_version": 1,
                "validated_at": "2026-04-12 02:00:00",
                "runtime_tier": "strict",
            },
        )
    )

    resp = await app_client.post(
        "/v1/intents/dispatch",
        json={
            "intent_text": "anything",
            "skill_id": "skill.explicit",
            "runtime_pref": "strict",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
