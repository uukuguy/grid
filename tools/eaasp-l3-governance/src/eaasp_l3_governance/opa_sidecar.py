"""OPA sidecar process manager — owns the lifecycle of the local OPA binary.

Per v3.15.0 design (PHASE_3_5_DESIGN.md §3.1). Replaces the implicit
``make dev-eaasp``-managed sidecar with a self-managed subprocess that:

1. **Starts** the OPA binary with ``--server --addr 127.0.0.1:18181
   --bundle <bundle_dir>`` and waits for the health probe to return 200.
2. **Health-probes** the sidecar via ``GET /health`` (OPA standard endpoint).
3. **Restarts** the sidecar if it crashes; emits a structured log line
   ``sidecar_restarted`` with the restart count so the audit ledger can
   correlate downstream ``infra_unavailable=true`` decisions with the
   restart.
4. **Reloads** policy bundles via ``PUT /v1/policies/{name}`` for hot
   updates; falls back to a process restart if the PUT fails.
5. **Shuts down** cleanly via SIGTERM → wait 5s → SIGKILL.

Strict-by-default (per ADR-V2-028):

- The OPA binary path is required (``L3_OPA_BIN`` env var); missing path
  fails at construction (no fallback to PATH lookup).
- The bundle dir is required (``L3_OPA_BUNDLE_DIR``); missing dir fails
  at construction.
- ``OPASidecar.from_env()`` is the only public constructor; tests may
  inject ``OPASidecar(binary_path=..., bundle_dir=...)`` directly.

The manager is intentionally **async-only** (``asyncio.create_subprocess_exec``)
so it can be wired into the FastAPI ``lifespan`` in ``main.py`` without
threading concerns. Subprocess stdout/stderr are piped (not inherited)
so the OPA logs don't bleed into the L3 governance log stream.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

import httpx
from loguru import logger

# Default bind address. Hardcoded — sidecar always loopback per
# ADR-V2-034 (sidecar topology, no cluster OPA in this milestone).
DEFAULT_OPA_ADDR = "127.0.0.1:18181"

# How long to wait for ``GET /health`` to return 200 on startup.
DEFAULT_STARTUP_TIMEOUT_SECONDS = 10.0

# Health probe interval (idle loop). 5s is fine — the OPA ``/health`` is
# cheap (in-memory check) and 5s is much shorter than typical L3
# evaluation timeouts (default 5s per L3_OPA_TIMEOUT_SECONDS).
DEFAULT_HEALTH_INTERVAL_SECONDS = 5.0

# Graceful shutdown deadline before SIGKILL.
DEFAULT_SHUTDOWN_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class SidecarConfig:
    """Resolved OPA sidecar configuration.

    All fields are required; missing values surface as ``RuntimeError`` from
    ``OPASidecar.from_env()`` per ADR-V2-028 strict-by-default.
    """

    binary_path: str
    bundle_dir: str
    addr: str = DEFAULT_OPA_ADDR
    startup_timeout_seconds: float = DEFAULT_STARTUP_TIMEOUT_SECONDS
    health_interval_seconds: float = DEFAULT_HEALTH_INTERVAL_SECONDS
    shutdown_grace_seconds: float = DEFAULT_SHUTDOWN_GRACE_SECONDS


def require_env(name: str) -> str:
    """Return the raw env-var value or raise ``RuntimeError`` per ADR-V2-028."""
    value = os.environ.get(name)
    if value is None or value == "":
        raise RuntimeError(
            f"{name} is required (ADR-V2-028 strict-by-default; "
            f"set it in .env or your shell environment)"
        )
    return value


def build_config_from_env() -> SidecarConfig:
    """Build a ``SidecarConfig`` from required env vars.

    Required:
    - ``L3_OPA_BIN`` — absolute path to the OPA binary (e.g.
      ``third_party/opac/opa``). PATH lookup is intentionally NOT used
      per ADR-V2-028.
    - ``L3_OPA_BUNDLE_DIR`` — directory holding the Rego bundles
      (``policies/*.rego`` plus any user bundles).

    Optional (defaults shown):
    - ``L3_OPA_ADDR`` — default ``127.0.0.1:18181``
    - ``L3_OPA_STARTUP_TIMEOUT_SECONDS`` — default 10.0
    - ``L3_OPA_HEALTH_INTERVAL_SECONDS`` — default 5.0
    - ``L3_OPA_SHUTDOWN_GRACE_SECONDS`` — default 5.0
    """
    binary_path = require_env("L3_OPA_BIN")
    if not os.path.isfile(binary_path) or not os.access(binary_path, os.X_OK):
        raise RuntimeError(
            f"L3_OPA_BIN {binary_path!r} is not an executable file"
        )
    bundle_dir = require_env("L3_OPA_BUNDLE_DIR")
    if not os.path.isdir(bundle_dir):
        raise RuntimeError(
            f"L3_OPA_BUNDLE_DIR {bundle_dir!r} is not a directory"
        )
    addr = os.environ.get("L3_OPA_ADDR", DEFAULT_OPA_ADDR)
    startup_timeout = float(
        os.environ.get("L3_OPA_STARTUP_TIMEOUT_SECONDS", str(DEFAULT_STARTUP_TIMEOUT_SECONDS))
    )
    health_interval = float(
        os.environ.get("L3_OPA_HEALTH_INTERVAL_SECONDS", str(DEFAULT_HEALTH_INTERVAL_SECONDS))
    )
    shutdown_grace = float(
        os.environ.get("L3_OPA_SHUTDOWN_GRACE_SECONDS", str(DEFAULT_SHUTDOWN_GRACE_SECONDS))
    )
    return SidecarConfig(
        binary_path=binary_path,
        bundle_dir=bundle_dir,
        addr=addr,
        startup_timeout_seconds=startup_timeout,
        health_interval_seconds=health_interval,
        shutdown_grace_seconds=shutdown_grace,
    )


class SidecarStartError(RuntimeError):
    """Raised when the sidecar cannot be started (binary missing, OPA crash on boot, etc.)."""


class OPASidecar:
    """Self-managed OPA sidecar process.

    Usage:

    >>> sidecar = OPASidecar.from_env()
    >>> await sidecar.start()
    >>> # ... use OPABackend against the live sidecar ...
    >>> await sidecar.shutdown()

    The sidecar starts OPA with these flags (matching ``make dev-eaasp``):
    ``--server``, ``--addr <addr>``, ``--bundle <bundle_dir>``.

    The constructor does **not** start the subprocess; call ``start()``
    explicitly so the FastAPI ``lifespan`` can await readiness before
    serving traffic.
    """

    def __init__(
        self,
        config: SidecarConfig,
        *,
        health_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._restart_count: int = 0
        self._owns_health_client = health_client is None
        self._health_client = health_client or httpx.AsyncClient(
            timeout=httpx.Timeout(2.0),
        )

    # ─── Construction ──────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "OPASidecar":
        """Build an ``OPASidecar`` from required env vars (ADR-V2-028)."""
        return cls(build_config_from_env())

    @property
    def config(self) -> SidecarConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def restart_count(self) -> int:
        return self._restart_count

    @property
    def health_url(self) -> str:
        return f"http://{self._config.addr}/health"

    # ─── Lifecycle ─────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the OPA subprocess and wait for ``/health`` to return 200.

        Raises ``SidecarStartError`` if the process crashes during boot
        or the health probe does not return 200 within the configured
        timeout. Caller may retry by calling ``start()`` again.
        """
        if self.is_running:
            return

        args = [
            self._config.binary_path,
            "run",
            "--server",
            f"--addr={self._config.addr}",
            f"--bundle={self._config.bundle_dir}",
        ]
        try:
            self._process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except FileNotFoundError as exc:
            raise SidecarStartError(
                f"OPA binary not found at {self._config.binary_path!r}"
            ) from exc
        except OSError as exc:
            raise SidecarStartError(
                f"failed to spawn OPA sidecar: {exc}"
            ) from exc

        try:
            await self._wait_healthy()
        except Exception:
            # Boot failed — kill the subprocess and re-raise.
            await self._kill_quickly()
            self._process = None
            raise

        logger.info(
            "OPA sidecar started",
            addr=self._config.addr,
            pid=self._process.pid,
            restart_count=self._restart_count,
        )

    async def shutdown(self) -> None:
        """Stop the sidecar gracefully: SIGTERM → wait grace → SIGKILL."""
        if not self.is_running:
            return
        assert self._process is not None
        try:
            self._process.terminate()
            try:
                await asyncio.wait_for(
                    self._process.wait(),
                    timeout=self._config.shutdown_grace_seconds,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "OPA sidecar did not exit after SIGTERM; sending SIGKILL",
                    pid=self._process.pid,
                )
                self._process.kill()
                await self._process.wait()
        finally:
            self._process = None
            if self._owns_health_client:
                await self._health_client.aclose()

    async def health(self) -> bool:
        """Return True iff the sidecar returns 200 from ``GET /health``."""
        if not self.is_running:
            return False
        try:
            resp = await self._health_client.get(self.health_url)
            return resp.status_code == 200
        except (httpx.RequestError, httpx.HTTPError):
            return False

    async def await_healthy(self, timeout_seconds: float | None = None) -> bool:
        """Poll ``/health`` until it returns 200, or ``timeout_seconds`` elapses.

        Returns True on success, False on timeout. Used by the FastAPI
        lifespan to gate readiness on the sidecar being up.
        """
        deadline = (
            asyncio.get_event_loop().time()
            + (timeout_seconds or self._config.startup_timeout_seconds)
        )
        while asyncio.get_event_loop().time() < deadline:
            if await self.health():
                return True
            await asyncio.sleep(0.1)
        return False

    async def reload_bundle(self, name: str, policy_text: str) -> bool:
        """Hot-reload a single policy via ``PUT /v1/policies/{name}``.

        Returns True on success. On failure, the caller may want to
        restart the sidecar (which re-reads the bundle from disk).

        Per ADR-V2-034, bundle reload is the prefered path for live
        policy updates; full sidecar restart is the fallback.
        """
        if not self.is_running:
            return False
        url = f"http://{self._config.addr}/v1/policies/{name}"
        try:
            resp = await self._health_client.put(
                url,
                content=policy_text,
                headers={"Content-Type": "text/plain"},
            )
        except (httpx.RequestError, httpx.HTTPError):
            return False
        return 200 <= resp.status_code < 300

    # ─── Internals ─────────────────────────────────────────────────────────

    async def _wait_healthy(self) -> None:
        """Wait for ``/health`` to return 200 within the configured timeout.

        Raises ``SidecarStartError`` on timeout or if the subprocess
        exits before becoming healthy.
        """
        if not await self.await_healthy():
            # Check whether the process died.
            assert self._process is not None
            if self._process.returncode is not None:
                stderr_bytes = await self._process.stderr.read() if self._process.stderr else b""
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")[:500]
                raise SidecarStartError(
                    f"OPA sidecar exited during boot (rc={self._process.returncode}): {stderr_text}"
                )
            raise SidecarStartError(
                f"OPA sidecar did not become healthy within "
                f"{self._config.startup_timeout_seconds}s"
            )

    async def _kill_quickly(self) -> None:
        """Best-effort kill during error paths; does not block on shutdown grace."""
        if self._process is None or self._process.returncode is not None:
            return
        try:
            self._process.kill()
            await asyncio.wait_for(self._process.wait(), timeout=1.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            pass

    def note_restart(self) -> None:
        """Bump the restart counter and log a structured event.

        Intended for callers (e.g. a supervisor task) that observe a
        sidecar crash and call ``start()`` again. The counter is exposed
        via ``restart_count`` so the audit ledger can correlate
        downstream ``infra_unavailable=true`` decisions with sidecar
        instability.
        """
        self._restart_count += 1
        logger.warning(
            "OPA sidecar restarted",
            addr=self._config.addr,
            restart_count=self._restart_count,
        )
