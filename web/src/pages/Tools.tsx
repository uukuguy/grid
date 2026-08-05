import { useCallback } from "react";
import { useAtomValue, useSetAtom } from "jotai";
import { ExecutionList } from "@/components/tools/ExecutionList";
import { executionRecordsAtom } from "@/atoms/debug";
import { sessionIdAtom } from "@/atoms/session";
import type { ToolExecutionRecord } from "@/atoms/debug";
import { sessionsClient } from "@/api/sessions";

export default function Tools() {
  const sessionId = useAtomValue(sessionIdAtom);
  const executions = useAtomValue(executionRecordsAtom);
  const setExecutions = useSetAtom(executionRecordsAtom);

  const refresh = useCallback(() => {
    if (!sessionId) return;
    // OBSTACK Phase E.1 — route through the shared sessions client
    // (same surface as the Python ``SessionsClient``). The wire
    // shape is a top-level JSON array (``Json<Vec<ToolExecution>>``
    // per ``crates/grid-server/src/api/executions.rs``).
    sessionsClient
      .list_executions(sessionId, { limit: 100 })
      .then((data: unknown) => {
        const records = Array.isArray(data) ? (data as ToolExecutionRecord[]) : [];
        setExecutions(records);
      })
      .catch(() => {/* ignore */});
  }, [sessionId, setExecutions]);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="px-4 py-2 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium">Tool Executions</h2>
          {executions.length > 0 && (
            <span className="text-xs text-muted-foreground">{executions.length} records</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {sessionId && (
            <span className="text-xs text-muted-foreground font-mono">
              session: {sessionId.slice(0, 8)}…
            </span>
          )}
          <button
            onClick={refresh}
            disabled={!sessionId}
            className="text-xs px-2 py-1 rounded border border-border hover:bg-secondary/50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Refresh
          </button>
        </div>
      </div>
      <ExecutionList />
    </div>
  );
}
