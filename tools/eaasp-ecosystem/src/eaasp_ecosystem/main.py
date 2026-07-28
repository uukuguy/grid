"""Ecosystem backend — ``eaasp-ecosystem`` script entrypoint.

v3.14.0 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.

Mirrors the L4 / L5 ``main.py`` shape so ``make dev-eaasp`` can
drop the ecosystem service in alongside the existing L2 / L3 /
L4 / runtime processes with zero ceremony.

Default port: ``:18087`` (env-overridable via ``EAASP_ECOSYSTEM_PORT``).
"""

from __future__ import annotations

import os
import sys

import uvicorn

from .ecosystem import EcosystemConfig, create_app


def run() -> None:
    """Run the ecosystem backend via uvicorn."""
    cfg = EcosystemConfig()
    app = create_app(config=cfg)
    host = os.environ.get("EAASP_ECOSYSTEM_HOST", "127.0.0.1")
    port = cfg.port
    log_level = os.environ.get("EAASP_ECOSYSTEM_LOG_LEVEL", "info")
    print(f"EAASP ecosystem backend listening on http://{host}:{port}")
    sys.stdout.flush()
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )


if __name__ == "__main__":
    run()