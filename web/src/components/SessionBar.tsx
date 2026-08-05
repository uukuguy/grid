import { useAtom, useSetAtom } from "jotai";
import { Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  sessionsAtom,
  activeSessionIdAtom,
  perSessionMessagesAtom,
  isStreamingAtom,
  migrateFallbackMessagesAtom,
  type SessionInfo,
} from "@/atoms/session";
import { addToastAtom } from "@/atoms/ui";
import { wsManager } from "@/ws/manager";
import { sessionsClient } from "@/api/sessions";
import { useEffect, useCallback, useRef } from "react";

/** Truncate a session ID to the first 8 characters */
function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

export function SessionBar() {
  const [sessions, setSessions] = useAtom(sessionsAtom);
  const [activeId, setActiveId] = useAtom(activeSessionIdAtom);
  const setPerSessionMessages = useSetAtom(perSessionMessagesAtom);
  const [isStreaming] = useAtom(isStreamingAtom);
  const addToast = useSetAtom(addToastAtom);
  const migrateFallback = useSetAtom(migrateFallbackMessagesAtom);
  const initializedRef = useRef(false);

  // On mount: fetch active sessions from the backend
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    fetchActiveSessions()
      .then((sessionIds) => {
        if (sessionIds.length > 0) {
          const infos: SessionInfo[] = sessionIds.map((id) => ({
            id,
            createdAt: new Date().toISOString(),
          }));
          setSessions(infos);
          // Activate the first session if none is active
          if (!activeId) {
            const first = infos[0]!;
            setActiveId(first.id);
            migrateFallback();
            wsManager.switchSession(first.id);
          }
        }
        // If no sessions exist, we stay in single-session mode until user
        // sends a message (which triggers session_created from the server)
      })
      .catch(() => {
        // Silently fail — single-session mode
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreate = useCallback(async () => {
    if (isStreaming) return;
    try {
      // OBSTACK Phase E.1 — route through the shared sessions client so the
      // web UI and eaasp-cli-v2 stay in lockstep (same surface as the
      // Python ``SessionsClient``). The default client targets grid-server
      // :3001 via the same base-URL config the rest of the UI uses.
      const resp = await sessionsClient.start_session({
        agent_id: "threshold-calibration",
        input: {},
      });
      const info: SessionInfo = {
        id: resp.session_id,
        createdAt: new Date().toISOString(),
      };
      setSessions((prev) => [...prev, info]);
      setActiveId(info.id);
      wsManager.switchSession(info.id);
    } catch (err) {
      addToast({
        type: "error",
        title: "Session Error",
        message: `Failed to create session: ${err instanceof Error ? err.message : String(err)}`,
      });
    }
  }, [isStreaming, setSessions, setActiveId, addToast]);

  const handleSwitch = useCallback(
    (id: string) => {
      if (id === activeId || isStreaming) return;
      setActiveId(id);
      wsManager.switchSession(id);
    },
    [activeId, isStreaming, setActiveId],
  );

  const handleClose = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (isStreaming) return;

      // Don't close the last session
      if (sessions.length <= 1) {
        addToast({
          type: "warning",
          title: "Cannot Close",
          message: "At least one session must remain active.",
        });
        return;
      }

      try {
        // OBSTACK Phase E.1 — best-effort DELETE through the shared client.
        // Failure here is intentionally swallowed (the UI removes the
        // session optimistically; server-side cleanup is eventually-consistent).
        await sessionsClient.stop_session(id);
      } catch {
        // Best-effort — still remove from UI
      }

      // Clean up per-session messages
      setPerSessionMessages((prev) => {
        const map = new Map(prev);
        map.delete(id);
        return map;
      });

      setSessions((prev) => prev.filter((s) => s.id !== id));

      // If we closed the active session, switch to the first remaining
      if (id === activeId) {
        const remaining = sessions.filter((s) => s.id !== id);
        if (remaining.length > 0) {
          const next = remaining[0]!;
          setActiveId(next.id);
          wsManager.switchSession(next.id);
        }
      }
    },
    [isStreaming, sessions, activeId, setSessions, setActiveId, setPerSessionMessages, addToast],
  );

  // Don't render if no sessions (single-session fallback mode)
  if (sessions.length === 0) return null;

  return (
    <div className="flex h-9 items-center gap-1 border-b border-border bg-card/50 px-4 overflow-x-auto">
      {sessions.map((session) => (
        <button
          key={session.id}
          onClick={() => handleSwitch(session.id)}
          className={cn(
            "group flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors shrink-0",
            session.id === activeId
              ? "bg-primary/10 text-primary border border-primary/30"
              : "text-muted-foreground hover:text-foreground hover:bg-secondary/50 border border-transparent",
          )}
        >
          <span className="font-mono">{truncateId(session.id)}</span>
          <span
            onClick={(e) => handleClose(session.id, e)}
            className={cn(
              "ml-0.5 rounded p-0.5 transition-colors",
              "opacity-0 group-hover:opacity-100",
              session.id === activeId && "opacity-60",
              "hover:bg-destructive/20 hover:text-destructive",
            )}
            role="button"
            tabIndex={-1}
            aria-label={`Close session ${truncateId(session.id)}`}
          >
            <X className="h-3 w-3" />
          </span>
        </button>
      ))}
      <button
        onClick={handleCreate}
        disabled={isStreaming}
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-50"
        aria-label="New session"
      >
        <Plus className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ── API Helpers ──

async function fetchActiveSessions(): Promise<string[]> {
  // OBSTACK Phase E.1 — route through the shared sessions client so the
  // web client and eaasp-cli-v2 stay in lockstep (same surface as the
  // Python ``SessionsClient``). The default client targets grid-server
  // :3001 via the same base-URL config the rest of the UI uses.
  try {
    const data = await sessionsClient.list_active();
    return data.sessions.map((s) => s.id);
  } catch {
    // Network / 4xx / 5xx → fall back to single-session mode (existing UX).
    return [];
  }
}
