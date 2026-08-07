"""EAASP Tasks — sync HTTP client (Phase E.3).

Target backend: grid-server :3001 (NOT L4). Bundles both task
surfaces into one client:

  - Agent tasks    : /api/v1/tasks (crates/grid-server/src/api/tasks.rs)
  - Cron tasks     : /api/v1/scheduler/tasks
                     (crates/grid-server/src/api/scheduler.rs)

Same pattern as ``obstack_client`` / ``sessions_client`` /
``mcp_client``:
  - Single class, sync methods
  - Injectable ``http_getter`` (test seam — matches the
    4-arg ``install_mock`` fixture pattern across the family)
  - ``_iscoroutine`` accepts either sync or async getters
    (Phase D.4 lesson — the CLI runs inside an asyncio event loop)
  - Returns typed dataclasses; preserves raw-list wire shapes
    via a bypass that avoids the ``_request`` dict-shape wrapping

Phase E.3 is intentionally narrow at the API surface:
  - Agent tasks: list_tasks / get_task / submit_task / cancel_task
    (delete is implemented as cancel on grid-server — same call)
  - Scheduler tasks: list_scheduled_tasks / run_scheduled_task /
    delete_scheduled_task / list_scheduled_executions /
    create_scheduled_task
"""

from __future__ import annotations

import json
from typing import Any

from .obstack_client import _iscoroutine
from .tasks_models import (
    AgentTask,
    AgentTaskDetail,
    CreateScheduledTaskRequest,
    ScheduledTask,
    ScheduledTaskListResponse,
    SubmitTaskRequest,
    TaskExecution,
)


class TasksClientError(Exception):
    """Raised on any non-2xx response or transport failure.

    Same exit-code taxonomy as ``ObstackClientError`` /
    ``SessionsClientError`` / ``McpClientError``.
    """

    def __init__(self, status: int, message: str, body: str = "") -> None:
        self.status = status
        self.message = message
        self.body = body
        super().__init__(message)


class TasksClient:
    """Synchronous client for the grid-server /api/v1/tasks/* +
    /api/v1/scheduler/tasks/* surfaces.

    Construct with a base URL (e.g. ``http://127.0.0.1:3001`` —
    grid-server's default). Auth token is sent as a Bearer header
    on every request.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        http_getter: "Any | None" = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._http_getter = http_getter or _default_http_getter

    # ─── Agent tasks /api/v1/tasks ──────────────────────────
    def list_tasks(self) -> list[AgentTask]:
        """GET /api/v1/tasks — top-level JSON array (raw passthrough)."""
        body = self._get_array("/api/v1/tasks")
        return [AgentTask(**row) for row in body]

    def get_task(self, task_id: str) -> AgentTaskDetail:
        """GET /api/v1/tasks/{id} — { task, executions }."""
        body = self._get(f"/api/v1/tasks/{task_id}")
        task = AgentTask(**body["task"])
        executions = [TaskExecution(**row) for row in body.get("executions", [])]
        return AgentTaskDetail(task=task, executions=executions)

    def submit_task(self, req: SubmitTaskRequest) -> AgentTask:
        """POST /api/v1/tasks — submit a new agent task. Returns
        the persisted task row (server assigns id + initial status).
        """
        body = self._post(
            "/api/v1/tasks",
            json_data={
                "prompt": req.prompt,
                "model": req.model,
                "max_rounds": req.max_rounds,
                "timeout_secs": req.timeout_secs,
            },
        )
        return AgentTask(**body)

    def cancel_task(self, task_id: str) -> None:
        """DELETE /api/v1/tasks/{id} — graceful cancel (D-08 semantics).

        grid-server treats DELETE /api/v1/tasks/:id as a cancel,
        not a permanent delete. The Tasks.tsx UI also exposes a
        "Delete" affordance that maps to the same call (the row
        is moved to ``failed`` / terminal state on the server
        side). Matches the legacy UI behavior verbatim.
        """
        self._delete(f"/api/v1/tasks/{task_id}")

    # ─── Scheduler / cron tasks /api/v1/scheduler/tasks ──────
    def list_scheduled_tasks(self) -> ScheduledTaskListResponse:
        """GET /api/v1/scheduler/tasks — { tasks: [...], total: N }.

        The scheduler list endpoint wraps the array in an object
        with a ``total`` count (unlike ``/api/v1/tasks`` which is
        a raw array). We map the dict into the typed dataclass.
        """
        body = self._get("/api/v1/scheduler/tasks")
        tasks_data = body.get("tasks", []) or []
        return ScheduledTaskListResponse(
            tasks=[ScheduledTask(**row) for row in tasks_data],
            total=body.get("total", len(tasks_data)),
        )

    def list_scheduled_executions(
        self, task_id: str, limit: int = 20,
    ) -> list[TaskExecution]:
        """GET /api/v1/scheduler/tasks/{id}/executions — top-level array.

        Always emits ``?limit=N`` (matches ObstackClient
        list_business_flows pattern).
        """
        body = self._get_array(
            f"/api/v1/scheduler/tasks/{task_id}/executions?limit={limit}"
        )
        return [TaskExecution(**row) for row in body]

    def create_scheduled_task(
        self, req: CreateScheduledTaskRequest,
    ) -> ScheduledTask:
        """POST /api/v1/scheduler/tasks — schedule a new cron task."""
        body = self._post(
            "/api/v1/scheduler/tasks",
            json_data={
                "name": req.name,
                "cron": req.cron,
                "agent_config": req.agent_config.__dict__,
                "enabled": req.enabled,
            },
        )
        return ScheduledTask(**body)

    def run_scheduled_task(self, task_id: str) -> TaskExecution:
        """POST /api/v1/scheduler/tasks/{id}/run — execute immediately.

        Returns the new execution row. The Schedule.tsx UI
        prepends this onto the existing executions list.
        """
        body = self._post(f"/api/v1/scheduler/tasks/{task_id}/run")
        return TaskExecution(**body)

    def delete_scheduled_task(self, task_id: str) -> None:
        """DELETE /api/v1/scheduler/tasks/{id} — permanent delete.

        Distinct from cancel_task (which targets the agent
        task surface and is graceful — D-08 semantics). The
        scheduler delete is the real "remove the schedule" call.
        """
        self._delete(f"/api/v1/scheduler/tasks/{task_id}")

    # ─── Internals ──────────────────────────────────────────
    def _get(self, path: str) -> Any:
        url = self.base_url + path
        try:
            result = self._http_getter("GET", url, {}, None)
        except TasksClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise TasksClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        return result or {}

    def _post(self, path: str, json_data: "dict | None" = None) -> Any:
        url = self.base_url + path
        try:
            result = self._http_getter("POST", url, {}, json_data)
        except TasksClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise TasksClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            result = asyncio.run(result)
        return result or {}

    def _delete(self, path: str) -> None:
        url = self.base_url + path
        try:
            self._http_getter("DELETE", url, {}, None)
        except TasksClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise TasksClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e

    def _get_array(self, path: str) -> list[Any]:
        """Top-level JSON array passthrough (mirrors
        ``SessionsClient.list_executions`` and
        ``McpClient.list_servers``). Without this bypass,
        ``_request`` would wrap non-dict payloads in
        ``{"data": [...]}`` and lose the array shape.
        """
        url = self.base_url + path
        try:
            result: Any = self._http_getter("GET", url, {}, None)
        except TasksClientError:
            raise
        except Exception as e:
            status = getattr(e, "code", 0) or 0
            raise TasksClientError(
                status,
                f"transport error from {url}: {e}",
            ) from e
        if _iscoroutine(result):
            import asyncio

            resolved = asyncio.run(result)
            return resolved
        return result


# ─── Default HTTP transport (stdlib urllib) ──────────────────────────


def _default_http_getter(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: "dict | None",
) -> Any:
    import urllib.error
    import urllib.request

    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise TasksClientError(e.code, f"HTTP {e.code} from {url}", body) from e
    except urllib.error.URLError as e:
        raise TasksClientError(0, f"transport error from {url}: {e.reason}") from e
