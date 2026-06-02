"""Pytest fixture wrapper for the stdio MCP server lifecycle.

Phase 7.1 T03 (CONTRACT-01 / D137 part 3). Spawns
``tests/contract/harness/test_mcp_server.py`` as a subprocess with
stdio piping. Yields an :class:`McpSubprocess` handle that tests can
use to introspect the subprocess (pid, kill, wait) — though most tests
only need the spawn-and-kill bracket via the fixture itself.

Teardown: SIGTERM the child + wait 2s; SIGKILL if still alive. The
fixture is function-scoped so each test gets a fresh subprocess
(matches the "disconnect → reconnect" test semantics).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pytest

_MCP_SERVER_PATH = Path(__file__).parent / "test_mcp_server.py"


@dataclass
class McpSubprocess:
    """Handle to a running stdio MCP server subprocess."""

    proc: subprocess.Popen
    command: list[str]

    @property
    def pid(self) -> int:
        return self.proc.pid

    def is_alive(self) -> bool:
        return self.proc.poll() is None

    def terminate(self, timeout: float = 2.0) -> None:
        if self.is_alive():
            try:
                self.proc.terminate()
                self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


@pytest.fixture
def mcp_subprocess_command() -> list[str]:
    """Command line tests pass into ``ConnectMCPRequest``.

    The runtime spawns the subprocess; this fixture returns the args so
    the test can construct an :class:`McpServerConfig` with the right
    stdio command pointing at our thin server.
    """
    return [sys.executable, str(_MCP_SERVER_PATH)]


@pytest.fixture
def mcp_subprocess(
    mcp_subprocess_command: list[str],
) -> Iterator[McpSubprocess]:
    """Spawn the thin MCP server directly.

    Used by tests that need to introspect the subprocess instead of
    letting the runtime spawn it via ``ConnectMCP``.
    """
    proc = subprocess.Popen(
        mcp_subprocess_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    handle = McpSubprocess(proc=proc, command=mcp_subprocess_command)
    try:
        yield handle
    finally:
        handle.terminate(timeout=2.0)
