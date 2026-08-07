"""EAASP Tasks — shared response / request models.

Phase E.3 (eaasp-tasks-client). Mirrors the wire-format of
grid-server's /api/v1/tasks/* (agent tasks) and
/api/v1/scheduler/tasks/* (cron / scheduled tasks) surfaces,
which the React UI (Tasks.tsx + Schedule.tsx) and (future)
eaasp-cli-v2 task subcommands both consume.

Wire sources:
  - crates/grid-server/src/api/tasks.rs (agent task CRUD + execs)
  - crates/grid-server/src/api/scheduler.rs (cron task CRUD +
    run + executions)

Phase E.3 intentionally bundles both surfaces into one client
(domain cohesion > route-prefix symmetry — analogous to the
SessionsClient scope rationale in commit 27).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─── Agent task responses (/api/v1/tasks) ────────────────────────────


@dataclass(frozen=True)
class TaskExecution:
    """Wire shape for both ``TaskExecutionResponse`` (tasks.rs)
    and ``ExecutionResponse`` (scheduler.rs). The fields are
    identical so the client uses one dataclass for both surfaces.
    """

    id: str
    task_id: str
    started_at: str
    finished_at: str | None = None
    status: str = "pending"  # "pending" | "running" | "success" | "failed"
    result: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentTask:
    """Mirrors ``crates/grid-server::api::tasks::TaskResponse``.
    Returned by GET /api/v1/tasks, POST /api/v1/tasks, GET
    /api/v1/tasks/{id}.task.
    """

    id: str
    status: str  # "pending" | "running" | "success" | "failed"
    result: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentTaskDetail:
    """Mirrors ``crates/grid-server::api::tasks::TaskDetailResponse``.

    Returned by GET /api/v1/tasks/{id}. Wraps the task + its
    execution history.
    """

    task: AgentTask
    executions: list[TaskExecution] = field(default_factory=list)


@dataclass(frozen=True)
class SubmitTaskRequest:
    """Body of POST /api/v1/tasks.

    Mirrors ``crates/grid-server::api::tasks::CreateTaskRequest``.
    """

    prompt: str
    model: str | None = None
    max_rounds: int = 0
    timeout_secs: int = 0


# ─── Scheduler / cron task responses (/api/v1/scheduler/tasks) ──────


@dataclass(frozen=True)
class AgentTaskConfig:
    """``crate::grid_engine::scheduler::AgentTaskConfig`` wire shape.

    The ``Input`` field is mandatory (per scheduler.rs validation
    rules); other fields are optional and surface as ``null``
    when omitted.
    """

    input: str
    system_prompt: str | None = None
    max_rounds: int | None = None
    timeout_secs: int | None = None
    model: str | None = None


@dataclass(frozen=True)
class ScheduledTask:
    """Mirrors ``crates/grid-server::api::scheduler::TaskResponse``.

    Returned by GET /api/v1/scheduler/tasks (wrapped in
    ``TaskListResponse.tasks``) and POST /api/v1/scheduler/tasks.
    """

    id: str
    name: str
    cron: str
    agent_config: AgentTaskConfig
    enabled: bool
    user_id: str | None = None
    last_run: str | None = None
    next_run: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class ScheduledTaskListResponse:
    """Mirrors ``crates/grid-server::api::scheduler::TaskListResponse``.

    Returned by GET /api/v1/scheduler/tasks. Wraps the list of
    scheduled tasks + a ``total`` count.
    """

    tasks: list[ScheduledTask] = field(default_factory=list)
    total: int = 0


@dataclass(frozen=True)
class CreateScheduledTaskRequest:
    """Body of POST /api/v1/scheduler/tasks.

    Mirrors ``crates/grid-server::api::scheduler::CreateTaskRequest``.
    """

    name: str
    cron: str
    agent_config: AgentTaskConfig
    enabled: bool = True
