import { useState, useEffect, useCallback } from "react";
import { useSetAtom } from "jotai";
import { Play, Square, ListTodo } from "lucide-react";
import { addToastAtom } from "../atoms/ui";
import { cn } from "@/lib/utils";

interface Task {
  id: string;
  status: "pending" | "running" | "success" | "failed";
  result?: string;
  error?: string;
}

interface TaskDetail {
  task: Task;
  executions: TaskExecution[];
}

interface TaskExecution {
  id: string;
  task_id: string;
  started_at: string;
  finished_at?: string;
  status: "pending" | "running" | "success" | "failed";
  result?: string;
  error?: string;
}

function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

export default function Tasks() {
  const addToast = useSetAtom(addToastAtom);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedTask, setSelectedTask] = useState<TaskDetail | null>(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Tracks which task ids have an in-flight Stop/Resume action so the
  // corresponding icon button can be aria-busy.
  const [pendingTaskActions, setPendingTaskActions] = useState<Set<string>>(
    new Set(),
  );

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/tasks");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      setTasks(data);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to fetch tasks";
      console.error("Failed to fetch tasks:", msg);
      addToast({ type: "error", message: msg });
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  const fetchTaskDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/v1/tasks/${id}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: TaskDetail = await res.json();
      setSelectedTask(data);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to fetch task detail";
      console.error("Failed to fetch task detail:", msg);
      addToast({ type: "error", message: msg });
    } finally {
      setDetailLoading(false);
    }
  }, [addToast]);

  const submitTask = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch("/api/v1/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, max_rounds: 10, timeout_secs: 300 }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      setPrompt("");
      await fetchTasks();
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to submit task";
      console.error("Failed to submit task:", msg);
      addToast({ type: "error", message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const deleteTask = async (id: string) => {
    if (!confirm("Are you sure you want to delete this task?")) return;
    try {
      const res = await fetch(`/api/v1/tasks/${id}`, { method: "DELETE" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      await fetchTasks();
      if (selectedTask?.task.id === id) {
        setSelectedTask(null);
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to delete task";
      console.error("Failed to delete task:", msg);
      addToast({ type: "error", message: msg });
    }
  };

  /**
   * Cancel a running task (UI-SPEC §9.3 + REQ-WEB-07).
   * grid-server treats DELETE /api/v1/tasks/:id as a graceful cancel; the
   * 4xx-without-confirm() pattern matches D-08 "instant" semantics.
   */
  const cancelTask = async (id: string, e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (pendingTaskActions.has(id)) return;
    setPendingTaskActions((prev) => new Set(prev).add(id));
    try {
      const res = await fetch(`/api/v1/tasks/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      await fetchTasks();
      if (selectedTask?.task.id === id) await fetchTaskDetail(id);
    } catch (error) {
      const msg = error instanceof Error ? error.message : "Failed to cancel task";
      addToast({ type: "error", message: msg });
    } finally {
      setPendingTaskActions((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Background Tasks</h2>
          <p className="text-sm text-muted-foreground">
            Submit and manage AI agent tasks
          </p>
        </div>
        <button
          onClick={fetchTasks}
          disabled={loading}
          className="text-xs px-2 py-1 rounded border border-border hover:bg-secondary/50 disabled:opacity-40 font-normal"
        >
          Refresh
        </button>
      </div>

      {/* Submit Form */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex gap-2">
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submitTask()}
            placeholder="Enter task prompt... (Press Enter to submit)"
            className="flex-1 px-3 py-2 text-sm bg-secondary border border-border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button
            onClick={submitTask}
            disabled={submitting || !prompt.trim()}
            className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed font-normal"
          >
            {submitting ? "Sending..." : "Send task"}
          </button>
        </div>
      </div>

      {/* Task List and Detail */}
      <div className="flex-1 overflow-hidden flex">
        {/* Task List */}
        <div className="w-1/2 border-r border-border overflow-auto">
          {loading ? (
            <SkeletonRows count={3} />
          ) : tasks.length === 0 ? (
            <EmptyTasks />
          ) : (
            <div className="divide-y divide-border">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  onClick={() => fetchTaskDetail(task.id)}
                  className={`p-3 cursor-pointer hover:bg-secondary/50 transition-colors ${
                    selectedTask?.task.id === task.id ? "bg-secondary" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-muted-foreground">
                      {task.id.slice(0, 8)}...
                    </span>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={task.status} />
                      {/* Inline Stop (icon-only) when running — UI-SPEC §9.3 */}
                      {task.status === "running" && (
                        <button
                          type="button"
                          onClick={(e) => cancelTask(task.id, e)}
                          disabled={pendingTaskActions.has(task.id)}
                          aria-busy={pendingTaskActions.has(task.id)}
                          aria-label={`Stop task ${truncateId(task.id)}`}
                          title={`Stop task ${truncateId(task.id)}`}
                          className={cn(
                            "inline-flex items-center justify-center rounded-md text-muted-foreground transition-colors h-6 w-6",
                            "hover:bg-destructive/10 hover:text-destructive",
                            "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
                            pendingTaskActions.has(task.id) &&
                              "opacity-50 cursor-wait",
                          )}
                        >
                          <Square className="h-3.5 w-3.5 fill-current" />
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteTask(task.id);
                        }}
                        className="text-xs text-muted-foreground hover:text-destructive px-2 py-1 rounded font-normal"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {task.status === "failed" && task.error && (
                    <p className="text-xs text-destructive mt-1 truncate">
                      {task.error}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Task Detail */}
        <div className="w-1/2 overflow-auto">
          {detailLoading ? (
            <SkeletonRows count={2} />
          ) : selectedTask ? (
            <TaskDetailView
              task={selectedTask}
              onCancel={cancelTask}
              isCancelling={pendingTaskActions.has(selectedTask.task.id)}
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <span className="text-muted-foreground text-sm">
                Select a task to view details
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Stats Footer */}
      <div className="px-4 py-2 border-t border-border bg-card text-xs text-muted-foreground">
        <span>{tasks.length} tasks</span>
        <span className="mx-2">|</span>
        <span>
          {tasks.filter((t) => t.status === "running").length} running
        </span>
        <span className="mx-2">|</span>
        <span>
          {tasks.filter((t) => t.status === "success").length} completed
        </span>
      </div>
    </div>
  );
}

function TaskDetailView({
  task: taskDetail,
  onCancel,
  isCancelling,
}: {
  task: TaskDetail;
  onCancel: (id: string, e?: React.MouseEvent) => Promise<void>;
  isCancelling: boolean;
}) {
  const { task, executions } = taskDetail;
  const showResume = task.status === "pending" || task.status === "failed";
  // Resume not supported on tasks in this phase — surface a warning toast
  // instead of silently failing.
  const addToast = useSetAtom(addToastAtom);

  return (
    <div className="p-4 space-y-4">
      {/* Task Info */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="font-medium">Task Details</h3>
          <div className="flex items-center gap-2">
            <StatusBadge status={task.status} />
            {task.status === "running" && (
              <button
                type="button"
                onClick={(e) => onCancel(task.id, e)}
                disabled={isCancelling}
                aria-busy={isCancelling}
                aria-label={`Stop task ${truncateId(task.id)}`}
                title={`Stop task ${truncateId(task.id)}`}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-1 text-xs font-normal text-foreground",
                  "transition-colors duration-150",
                  "hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                  isCancelling && "opacity-50 cursor-wait",
                )}
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                <span>Stop</span>
              </button>
            )}
            {showResume && (
              <button
                type="button"
                onClick={() =>
                  addToast({
                    type: "warning",
                    title: "Resume not supported",
                    message: "Tasks cannot be resumed — re-submit if needed.",
                  })
                }
                aria-label="Resume not supported for tasks"
                title="Resume not supported for tasks"
                className={cn(
                  "inline-flex items-center gap-1 rounded-md bg-secondary px-2 py-1 text-xs font-normal text-muted-foreground",
                  "transition-colors duration-150",
                  "hover:bg-secondary/70",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                )}
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Resume</span>
              </button>
            )}
          </div>
        </div>
        <div className="text-sm text-muted-foreground">
          <p>
            <span className="text-foreground">ID:</span>{" "}
            <span className="font-mono">{task.id}</span>
          </p>
        </div>
      </div>

      {/* Result or Error */}
      {(task.result || task.error) && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">
            {task.status === "failed" ? "Error" : "Result"}
          </h4>
          <pre
            className={`p-3 rounded-lg text-xs overflow-auto max-h-64 ${
              task.status === "failed"
                ? "bg-destructive/10 text-destructive"
                : "bg-secondary"
            }`}
          >
            {task.error || task.result || "No output"}
          </pre>
        </div>
      )}

      {/* Execution History */}
      {executions.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-medium">Execution History</h4>
          <div className="space-y-2">
            {executions.map((exec) => (
              <div key={exec.id} className="p-3 bg-secondary rounded-lg text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-muted-foreground">
                    {exec.id.slice(0, 8)}...
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded ${
                      exec.status === "success"
                        ? "bg-green-100 text-green-800"
                        : exec.status === "running"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {exec.status}
                  </span>
                </div>
                <p className="text-muted-foreground">
                  {new Date(exec.started_at).toLocaleString()}
                  {exec.finished_at &&
                    ` - ${new Date(exec.finished_at).toLocaleString()}`}
                </p>
                {exec.result && (
                  <pre className="mt-2 text-xs whitespace-pre-wrap">
                    {exec.result.slice(0, 500)}
                    {exec.result.length > 500 && "..."}
                  </pre>
                )}
                {exec.error && (
                  <pre className="mt-2 text-xs text-destructive whitespace-pre-wrap">
                    {exec.error.slice(0, 500)}
                    {exec.error.length > 500 && "..."}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: "pending" | "running" | "success" | "failed" }) {
  const styles = {
    pending: "bg-yellow-100 text-yellow-800",
    running: "bg-blue-100 text-blue-800",
    success: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };
  const style = styles[status as keyof typeof styles] || "";

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${style}`}>
      {status}
    </span>
  );
}

/** Three skeleton rows (UI-SPEC §15.2 — Tasks page loading state). */
function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="flex flex-col gap-2 p-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-muted animate-pulse h-12 rounded-md"
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

/** Empty state with ListTodo icon (UI-SPEC §10.4). */
function EmptyTasks() {
  return (
    <div className="flex items-center justify-center h-full px-4">
      <div className="text-center text-muted-foreground">
        <ListTodo className="mx-auto h-12 w-12 text-muted-foreground" aria-hidden="true" />
        <p className="mt-3 font-medium">No tasks yet</p>
        <p className="text-sm mt-1">Submit a task above to get started</p>
      </div>
    </div>
  );
}