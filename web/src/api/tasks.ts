// OBSTACK Phase E.3 — TS mirror of eaasp_common.TasksClient.
// Wraps the grid-server /api/v1/tasks/* (agent tasks) +
// /api/v1/scheduler/tasks/* (cron tasks) surfaces for the React
// UI (Tasks.tsx + Schedule.tsx). Same 1:1 surface as the Python
// client; method names, response shapes, and HTTP semantics are
// identical so the two stay in lockstep.
import { api } from "./client";
import type {
  AgentTask,
  AgentTaskDetail,
  CreateScheduledTaskRequest,
  ScheduledTask,
  ScheduledTaskListResponse,
  SubmitTaskRequest,
  TaskExecution,
  TasksClientOptions,
} from "./tasks_types";

export type {
  AgentTask,
  AgentTaskDetail,
  CreateScheduledTaskRequest,
  ScheduledTask,
  ScheduledTaskListResponse,
  SubmitTaskRequest,
  TaskExecution,
  TasksClientOptions,
};

export class TasksClient {
  private baseUrl: string;
  private authToken: string | null;

  constructor(options: TasksClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
  }

  // ─── Agent tasks /api/v1/tasks ──────────────────────────
  async list_tasks(): Promise<AgentTask[]> {
    // Server returns top-level JSON array
    // (``Json<Vec<TaskResponse>>`` per crates/grid-server::api::tasks::list_tasks)
    // — preserved as-is via ``unknown`` cast (matches Python
    // TasksClient ``list_tasks`` shape).
    return (await this.fetch<unknown>("/api/v1/tasks")) as AgentTask[];
  }

  async get_task(id: string): Promise<AgentTaskDetail> {
    return this.fetch<AgentTaskDetail>(
      `/api/v1/tasks/${encodeURIComponent(id)}`,
    );
  }

  async submit_task(req: SubmitTaskRequest): Promise<AgentTask> {
    return this.fetch<AgentTask>("/api/v1/tasks", {
      method: "POST",
      body: JSON.stringify({
        prompt: req.prompt,
        model: req.model,
        max_rounds: req.max_rounds,
        timeout_secs: req.timeout_secs,
      }),
    });
  }

  async cancel_task(id: string): Promise<void> {
    // DELETE /api/v1/tasks/:id is graceful cancel on grid-server,
    // not a permanent delete — D-08 semantics. The Tasks.tsx UI
    // also exposes a "Delete" affordance that maps here.
    await this.fetch<void>(
      `/api/v1/tasks/${encodeURIComponent(id)}`,
      { method: "DELETE" },
      { allow204: true },
    );
  }

  // ─── Scheduler / cron tasks /api/v1/scheduler/tasks ──────
  async list_scheduled_tasks(): Promise<ScheduledTaskListResponse> {
    return this.fetch<ScheduledTaskListResponse>(
      "/api/v1/scheduler/tasks",
    );
  }

  async list_scheduled_executions(
    task_id: string,
    limit = 20,
  ): Promise<TaskExecution[]> {
    // Top-level JSON array — preserved as-is.
    return (await this.fetch<unknown>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(task_id)}/executions?limit=${limit}`,
    )) as TaskExecution[];
  }

  async create_scheduled_task(
    req: CreateScheduledTaskRequest,
  ): Promise<ScheduledTask> {
    return this.fetch<ScheduledTask>(
      "/api/v1/scheduler/tasks",
      {
        method: "POST",
        body: JSON.stringify({
          name: req.name,
          cron: req.cron,
          agent_config: req.agent_config,
          enabled: req.enabled,
        }),
      },
    );
  }

  async run_scheduled_task(task_id: string): Promise<TaskExecution> {
    return this.fetch<TaskExecution>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(task_id)}/run`,
      { method: "POST" },
    );
  }

  async delete_scheduled_task(task_id: string): Promise<void> {
    // Distinct from cancel_task — the scheduler DELETE is the
    // real "remove the schedule" call (not a graceful cancel).
    await this.fetch<void>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(task_id)}`,
      { method: "DELETE" },
      { allow204: true },
    );
  }

  // ─── Internals ──────────────────────────────────────────
  private async fetch<T>(
    path: string,
    init: RequestInit = {},
    extra: { allow204?: boolean } = {},
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});
    if (this.authToken) {
      headers.set("Authorization", `Bearer ${this.authToken}`);
    }
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const resp = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `Tasks ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    if (extra.allow204 || resp.status === 204) return undefined as unknown as T;
    if (resp.headers.get("content-type")?.includes("application/json")) {
      return (await resp.json()) as T;
    }
    return undefined as unknown as T;
  }
}

// Phase E.3 — the default client reuses the existing ``api`` singleton
// (which already knows the auth token). Same base URL default as the
// other clients (``http://127.0.0.1:3001`` — grid-server).
const authToken = api.getToken();

export const tasksClient = new TasksClient({
  baseUrl:
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_TASKS_BASE_URL) ||
    "http://127.0.0.1:3001",
  authToken: authToken ?? undefined,
});
