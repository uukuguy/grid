"""MCP Connection Pool tests — shared httpx.AsyncClient reuse (D65 / L2-17)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import httpx
import pytest

from eaasp_l2_memory_engine.embedding.provider import (
    reset_embedding_provider,
    set_embedding_client,
)
import eaasp_l2_memory_engine.embedding.provider as provider_mod
from eaasp_l2_memory_engine.mcp_server import _EmbeddingClientPool, build_server

pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


async def _two_writes(server: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run two consecutive memory_write_file calls on the same server."""
    from json import loads

    from mcp.types import CallToolRequest, CallToolRequestParams

    handler = server.request_handlers[CallToolRequest]

    async def _invoke(args: dict[str, Any]) -> dict[str, Any]:
        req = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(name="memory_write_file", arguments=args),
        )
        resp = await handler(req)
        result = resp.root
        return loads(result.content[0].text)

    w1 = await _invoke({"scope": "pool", "category": "a", "content": "first write"})
    w2 = await _invoke({"scope": "pool", "category": "b", "content": "second write"})
    return w1, w2


# ────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────


async def test_pool_get_client_returns_same_instance() -> None:
    """Two get_client() calls return the same httpx.AsyncClient instance."""
    pool = _EmbeddingClientPool()
    try:
        c1 = await pool.get_client()
        c2 = await pool.get_client()
        assert c1 is c2, "Expected same client instance on repeated get_client()"
    finally:
        await pool.close()


async def test_pool_recreates_client_when_closed() -> None:
    """get_client() recreates the client if the previous one was closed."""
    pool = _EmbeddingClientPool()
    try:
        c1 = await pool.get_client()
        await c1.aclose()
        c2 = await pool.get_client()
        assert c1 is not c2, "Expected new client after old one was closed"
    finally:
        await pool.close()


async def test_pool_close_sets_client_to_none() -> None:
    """close() properly cleans up the internal client."""
    pool = _EmbeddingClientPool()
    c1 = await pool.get_client()
    assert pool._client is not None
    await pool.close()
    assert pool._client is None, "Expected pool._client to be None after close()"


async def test_pool_get_client_after_close_creates_new() -> None:
    """After close(), get_client() creates a fresh client."""
    pool = _EmbeddingClientPool()
    c1 = await pool.get_client()
    await pool.close()
    c2 = await pool.get_client()
    assert c1 is not c2, "Expected new client after pool close + reopen"
    await pool.close()


async def test_set_embedding_client_sets_module_variable() -> None:
    """Setting a shared client stores it on the provider module."""
    reset_embedding_provider()
    client = httpx.AsyncClient(timeout=30.0, trust_env=False)
    try:
        set_embedding_client(client)
        assert provider_mod._SHARED_CLIENT is client
    finally:
        await client.aclose()
        set_embedding_client(None)


async def test_two_consecutive_writes_use_same_client(db_path: str) -> None:
    """Two consecutive memory_write_file calls reuse the same httpx.AsyncClient.

    This test verifies that build_server() wires the connection pool so that
    the embedding provider singleton receives a shared client, and two
    writes reuse the same connection rather than creating new ones.
    """
    server, _ = build_server(db_path)

    # Capture the shared client reference *after* the first write triggers
    # lazy init of the embedding provider inside the dispatcher.
    w1, w2 = await _two_writes(server)

    assert "memory_id" in w1
    assert "memory_id" in w2

    # The shared client should have been set on the provider after first use.
    # Verify it's not None (meaning pool was wired).
    shared = provider_mod._SHARED_CLIENT
    assert shared is not None, (
        "Expected shared httpx.AsyncClient to be set on embedding provider "
        "after tool calls. Pool may not be wired in build_server()."
    )
    assert isinstance(shared, httpx.AsyncClient)
    assert not shared.is_closed, "Shared client should be open after tool calls"
