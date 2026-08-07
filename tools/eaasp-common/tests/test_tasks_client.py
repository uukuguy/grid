"""eaasp-tasks-client tests — mirror test_obstack_client.py / test_sessions_client.py.

Phase E.3. Tests don't hit grid-server; they use an injected
http_getter that returns the parsed wire shape.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from eaasp_common import (
    AgentTask,
    AgentTaskConfig,
    AgentTaskDetail,
    CreateScheduledTaskRequest,
    ScheduledTask,
    ScheduledTaskListResponse,
    SubmitTaskRequest,
    TaskExecution,
    TasksClient,
    TasksClientError,
)


Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]


def _make_fake_getter(responses: dict[str, Any]) -> Handler:
    """Return a 4-arg handler that maps (method, url, headers, body) → response.

    Mirrors the ObstackClient / SessionsClient / McpClient test
    seam pattern.
    """
    def fake_getter(method, url, headers, json_body):
        if url not in responses:
            raise KeyError(f"unexpected URL: {url}")
        return responses[url]
    return fake_getter


def _agent_config(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {"input": "do the thing"}
    base.update(overrides)
    return base


# ─── Model dataclasses parse correctly ──────────────────────────────


def test_agent_task_from_dict() -> None:
    t = AgentTask(id="t1", status="running")
    assert t.id == "t1"
    assert t.status == "running"
    assert t.result is None
    assert t.error is None


def test_agent_task_detail_from_dict() -> None:
    t = AgentTaskDetail(
        task=AgentTask(id="t1", status="success", result="done"),
        executions=[
            TaskExecution(
                id="e1", task_id="t1", started_at="t1",
                status="success", result="done",
            ),
        ],
    )
    assert t.task.id == "t1"
    assert len(t.executions) == 1
    assert t.executions[0].status == "success"


def test_scheduled_task_from_dict() -> None:
    st = ScheduledTask(
        id="sch-1",
        name="daily",
        cron="0 9 * * *",
        agent_config=AgentTaskConfig(input="wake up"),
        enabled=True,
    )
    assert st.cron == "0 9 * * *"
    assert st.enabled is True


# ─── Agent tasks /api/v1/tasks ──────────────────────────────────────


def test_list_tasks_returns_typed_tasks() -> None:
    body = [
        {"id": "t1", "status": "running"},
        {"id": "t2", "status": "success", "result": "all good"},
        {"id": "t3", "status": "failed", "error": "boom"},
    ]
    c = TasksClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/tasks": body}
        ),
    )
    tasks = c.list_tasks()
    assert len(tasks) == 3
    assert all(isinstance(t, AgentTask) for t in tasks)
    assert tasks[0].status == "running"
    assert tasks[1].result == "all good"
    assert tasks[2].error == "boom"


def test_get_task_returns_detail_with_executions() -> None:
    body = {
        "task": {"id": "t1", "status": "failed", "error": "boom"},
        "executions": [
            {"id": "e1", "task_id": "t1", "started_at": "t1", "status": "success", "result": "first"},
            {"id": "e2", "task_id": "t1", "started_at": "t2", "status": "failed", "error": "boom"},
        ],
    }
    c = TasksClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/tasks/t1": body}
        ),
    )
    detail = c.get_task("t1")
    assert isinstance(detail, AgentTaskDetail)
    assert detail.task.error == "boom"
    assert len(detail.executions) == 2
    assert detail.executions[1].error == "boom"


def test_submit_task_sends_body_to_right_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["method"] = method
        captured["url"] = url
        captured["body"] = json_body
        return {"id": "new-task", "status": "pending"}

    c = TasksClient("http://x", http_getter=getter)
    task = c.submit_task(
        SubmitTaskRequest(prompt="explain X", model="gpt-4o", max_rounds=10, timeout_secs=300),
    )
    assert captured["method"] == "POST"
    assert captured["url"] == "http://x/api/v1/tasks"
    assert captured["body"] == {
        "prompt": "explain X",
        "model": "gpt-4o",
        "max_rounds": 10,
        "timeout_secs": 300,
    }
    assert isinstance(task, AgentTask)
    assert task.id == "new-task"


def test_cancel_task_uses_delete_semantics() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["method"] = method
        captured["url"] = url
        return None

    c = TasksClient("http://x", http_getter=getter)
    c.cancel_task("t1")
    assert captured["method"] == "DELETE"
    assert captured["url"] == "http://x/api/v1/tasks/t1"


# ─── Scheduler / cron tasks /api/v1/scheduler/tasks ─────────────────


def test_list_scheduled_tasks_unwraps_tasks_field() -> None:
    """Server returns ``{tasks: [...], total: N}`` — the unwrap
    into the typed ``ScheduledTaskListResponse`` is the contract."""
    body = {
        "tasks": [
            {"id": "sch-1", "name": "daily", "cron": "0 9 * * *",
             "agent_config": _agent_config(input="wake"), "enabled": True},
            {"id": "sch-2", "name": "weekly", "cron": "0 9 * * 1",
             "agent_config": _agent_config(input="report"), "enabled": False},
        ],
        "total": 2,
    }
    c = TasksClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/scheduler/tasks": body}
        ),
    )
    resp = c.list_scheduled_tasks()
    assert isinstance(resp, ScheduledTaskListResponse)
    assert len(resp.tasks) == 2
    assert all(isinstance(t, ScheduledTask) for t in resp.tasks)
    assert resp.total == 2


def test_list_scheduled_executions_returns_raw_list() -> None:
    """Server returns a top-level JSON array — preserve it."""
    body = [
        {"id": "e1", "task_id": "sch-1", "started_at": "t1", "status": "success", "result": "ok"},
        {"id": "e2", "task_id": "sch-1", "started_at": "t2", "status": "running"},
    ]
    c = TasksClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/scheduler/tasks/sch-1/executions?limit=20": body}
        ),
    )
    execs = c.list_scheduled_executions("sch-1", limit=20)
    assert len(execs) == 2
    assert execs[0].result == "ok"
    assert execs[1].status == "running"


def test_create_scheduled_task_sends_nested_agent_config() -> None:
    """Server expects ``{name, cron, agent_config: {...}, enabled}``.
    The client must forward the nested ``agent_config`` as-is.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["body"] = json_body
        return {
            "id": "sch-new", "name": json_body["name"], "cron": json_body["cron"],
            "agent_config": json_body["agent_config"], "enabled": json_body["enabled"],
        }

    c = TasksClient("http://x", http_getter=getter)
    task = c.create_scheduled_task(
        CreateScheduledTaskRequest(
            name="hourly-check",
            cron="0 * * * *",
            agent_config=AgentTaskConfig(
                input="check things",
                system_prompt="you are a watchdog",
                max_rounds=5,
                timeout_secs=60,
                model="gpt-4o",
            ),
            enabled=True,
        ),
    )
    assert isinstance(task, ScheduledTask)
    assert task.id == "sch-new"
    assert captured["body"]["agent_config"] == {
        "input": "check things",
        "system_prompt": "you are a watchdog",
        "max_rounds": 5,
        "timeout_secs": 60,
        "model": "gpt-4o",
    }


def test_run_scheduled_task_returns_execution() -> None:
    body = {"id": "e-new", "task_id": "sch-1", "started_at": "t-now", "status": "running"}
    c = TasksClient(
        "http://x", http_getter=_make_fake_getter(
            {"http://x/api/v1/scheduler/tasks/sch-1/run": body}
        ),
    )
    exec_resp = c.run_scheduled_task("sch-1")
    assert isinstance(exec_resp, TaskExecution)
    assert exec_resp.id == "e-new"
    assert exec_resp.status == "running"


def test_delete_scheduled_task_uses_delete_semantics() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["method"] = method
        captured["url"] = url
        return None

    c = TasksClient("http://x", http_getter=getter)
    c.delete_scheduled_task("sch-1")
    assert captured["method"] == "DELETE"
    assert captured["url"] == "http://x/api/v1/scheduler/tasks/sch-1"


# ─── Error paths ────────────────────────────────────────────────────


def test_raises_tasks_client_error_on_non_2xx_list() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 404, "Not Found", msg, None)

    c = TasksClient("http://x", http_getter=getter)
    with pytest.raises(TasksClientError) as exc:
        c.list_tasks()
    assert exc.value.status == 404


def test_raises_tasks_client_error_on_non_2xx_scheduled() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 500, "Server Error", msg, None)

    c = TasksClient("http://x", http_getter=getter)
    with pytest.raises(TasksClientError) as exc:
        c.list_scheduled_tasks()
    assert exc.value.status == 500


def test_raises_tasks_client_error_on_non_2xx_submit() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 422, "Unprocessable", msg, None)

    c = TasksClient("http://x", http_getter=getter)
    with pytest.raises(TasksClientError) as exc:
        c.submit_task(SubmitTaskRequest(prompt=""))
    assert exc.value.status == 422


def test_raises_tasks_client_error_on_non_2xx_cancel() -> None:
    def getter(method, url, headers, json_body):
        import http.client
        import urllib.error
        msg = http.client.HTTPMessage()
        for k, v in headers.items():
            msg[k] = v
        raise urllib.error.HTTPError(url, 404, "Not Found", msg, None)

    c = TasksClient("http://x", http_getter=getter)
    with pytest.raises(TasksClientError) as exc:
        c.cancel_task("missing")
    assert exc.value.status == 404


# ─── Auth + path-encoding guarantees (security review) ────────────


def test_auth_token_reaches_get_array_path() -> None:
    """Security fix: ``_get_array`` (used by list_tasks +
    list_scheduled_executions) used to drop the ``Authorization``
    header. Capture the headers on the wire and assert Bearer
    is present.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return []

    c = TasksClient("http://x", auth_token="SECRET", http_getter=getter)
    c.list_tasks()
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_auth_token_reaches_post_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return {"id": "t-new", "status": "pending"}

    c = TasksClient("http://x", auth_token="SECRET", http_getter=getter)
    c.submit_task(SubmitTaskRequest(prompt="x"))
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_auth_token_reaches_delete_path() -> None:
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["headers"] = headers
        return None

    c = TasksClient("http://x", auth_token="SECRET", http_getter=getter)
    c.cancel_task("t-1")
    assert captured["headers"] == {"Authorization": "Bearer SECRET"}


def test_path_injection_in_get_task_encodes_segment() -> None:
    """Security fix: ``f"/api/v1/tasks/{task_id}"`` used to
    forward raw input; the server receives a path segment,
    so a ``task_id`` containing ``/`` or ``?`` could
    restructure the URL. Percent-encode with ``safe=""``.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"task": {"id": "x", "status": "running"}, "executions": []}

    c = TasksClient("http://x", http_getter=getter)
    c.get_task("../admin/users?force=1")
    # The unreserved chars (letters / digits) survive; the
    # path-breaking chars (``,``/``/``?``/``=``) get
    # percent-encoded so they cannot restructure the URL.
    assert "%2F" in captured["url"]  # ``/`` → %2F
    assert "%3F" in captured["url"]  # ``?`` → %3F
    assert "%3D" in captured["url"]  # ``=`` → %3D
    # No literal ``?`` followed by ``force=`` (would mean an
    # attacker-supplied query string leaked through).
    assert "force=1" not in captured["url"]


def test_path_injection_in_run_scheduled_task_encodes_segment() -> None:
    """``task_id`` is path-encoded but the literal ``/run``
    suffix stays as a real separator (not part of ``task_id``).

    The URL ``sch%2F..%2Frestart/run`` proves the path-breaking
    ``/`` characters were percent-encoded — those are the
    characters RFC 3986 reserves as path separators and the
    ones that enable ``..``-style traversal / query-string
    smuggling. Dots and letters stay literal (RFC 3986
    unreserved chars); that's expected and safe.
    """
    captured: dict = {}

    def getter(method, url, headers, json_body):
        captured["url"] = url
        return {"id": "e", "task_id": "x", "started_at": "t", "status": "running"}

    c = TasksClient("http://x", http_getter=getter)
    c.run_scheduled_task("sch/../restart")
    # Exactly two percent-encoded slashes (the two ``/`` in
    # ``sch/../restart``); no encoded ``/`` separates
    # ``sch`` from the method suffix.
    assert captured["url"].count("%2F") == 2
    # The literal ``/run`` suffix is the method's own segment
    # separator — not part of the encoded task_id segment.
    assert captured["url"].endswith("/run")
    # The encoded segment is followed immediately by the method
    # suffix (no double-slash, no encoded prefix before run).
    assert captured["url"].endswith("..%2Frestart/run")
