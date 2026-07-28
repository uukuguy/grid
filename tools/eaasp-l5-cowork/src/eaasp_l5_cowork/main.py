"""L5 Cowork backend — ``eaasp-l5-cowork`` script entrypoint.

v3.13.0 — EAASP Phase 5 — L5 Cowork 四卡 (Event / Evidence / Action /
Approval) + 回溯闭环 (retrospective cycle).

Mirrors the L4 ``main.py`` shape so ``make dev-eaasp`` can drop the
L5 service in alongside the existing L2 / L3 / L4 / runtime
processes with zero ceremony.

Default port: ``:18086`` (env-overridable via ``EAASP_L5_PORT``).
"""

from __future__ import annotations

import os
import sys

import uvicorn

from .cowork import CoworkConfig, create_app


def run() -> None:
    """Run the Cowork backend via uvicorn (matches L4 conventions)."""
    cfg = CoworkConfig()
    app = create_app(config=cfg)
    host = os.environ.get("EAASP_L5_HOST", "127.0.0.1")
    port = cfg.port
    log_level = os.environ.get("EAASP_L5_LOG_LEVEL", "info")
    print(f"EAASP L5 Cowork backend listening on http://{host}:{port}")
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
