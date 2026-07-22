"""Shared pytest fixtures — temp SQLite DB per test + HTTP client."""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from eaasp_l3_governance.audit import AuditStore
from eaasp_l3_governance.api import create_app
from eaasp_l3_governance.db import init_db
from eaasp_l3_governance.policy_engine import PolicyEngine

# REQ-EAASP-06: S8 hermetic flow exercises the real mock-scada handlers so
# the governance gate + the deterministic setpoint store run against the
# same code that would be wired in production. Make ``mock_scada`` importable
# without an external `pip install -e` step by adding ``../mock-scada/src``
# to ``sys.path`` at conftest load time.
_MOCK_SCADA_SRC = Path(__file__).resolve().parent.parent.parent / "mock-scada" / "src"
if _MOCK_SCADA_SRC.is_dir() and str(_MOCK_SCADA_SRC) not in sys.path:
    sys.path.insert(0, str(_MOCK_SCADA_SRC))


@pytest_asyncio.fixture
async def db_path() -> AsyncIterator[str]:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    await init_db(path)
    try:
        yield path
    finally:
        if os.path.exists(path):
            os.unlink(path)


@pytest_asyncio.fixture
async def policy_engine(db_path: str) -> PolicyEngine:
    return PolicyEngine(db_path)


@pytest_asyncio.fixture
async def audit_store(db_path: str) -> AuditStore:
    return AuditStore(db_path)


@pytest_asyncio.fixture
async def app(db_path: str) -> AsyncIterator:
    from httpx import ASGITransport, AsyncClient

    application = create_app(db_path)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
