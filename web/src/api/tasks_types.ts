// OBSTACK Phase E.3 — TS mirror of eaasp_common.TasksClient
// models. 1:1 mirror of tools/eaasp-common/.../tasks_models.py.
// When grid-server changes a wire field, both these files (and
// the Python parent) get updated together.

export interface TaskExecution {
  id: string;
  task_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  result: string | null;
  error: string | null;
}

export interface AgentTask {
  id: string;
  status: string;
  result: string | null;
  error: string | null;
}

export interface AgentTaskDetail {
  task: AgentTask;
  executions: TaskExecution[];
}

export interface SubmitTaskRequest {
  prompt: string;
  model: string | null;
  max_rounds: number;
  timeout_secs: number;
}

export interface AgentTaskConfig {
  input: string;
  system_prompt: string | null;
  max_rounds: number | null;
  timeout_secs: number | null;
  model: string | null;
}

export interface ScheduledTask {
  id: string;
  name: string;
  cron: string;
  agent_config: AgentTaskConfig;
  enabled: boolean;
  user_id: string | null;
  last_run: string | null;
  next_run: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskListResponse {
  tasks: ScheduledTask[];
  total: number;
}

export interface CreateScheduledTaskRequest {
  name: string;
  cron: string;
  agent_config: AgentTaskConfig;
  enabled: boolean;
}

export interface TasksClientOptions {
  baseUrl: string;
  authToken?: string | null;
}
