import { useCallback, useEffect, useState } from "react";
import { useAtomValue, useSetAtom } from "jotai";
import { Play, Square } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  activeSessionIdAtom,
  sessionStatusAtom,
  stoppedByUserAtom,
} from "@/atoms/session";
import { addToastAtom, connectionStatusAtom } from "@/atoms/ui";

/** Truncate a session ID for aria-labels. */
function truncateId(id: string): string {
  return id.length > 8 ? id.slice(0, 8) : id;
}

/** Detect macOS for the Cmd+. shortcut label. */
function isMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Mac|iPhone|iPad/.test(navigator.platform);
}

/**
 * Global Stop/Resume + live indicator (REQ-WEB-03, D-02).
 *
 * Mounted unconditionally in AppLayout. The session pills stay in SessionBar
 * (chat-only); this component exposes the always-visible Stop/Resume actions
 * the user needs on every tab.
 */
export function SessionControls() {
  const sessionId = useAtomValue(activeSessionIdAtom);
  const status = useAtomValue(sessionStatusAtom);
  const connection = useAtomValue(connectionStatusAtom);
  const setStoppedByUser = useSetAtom(stoppedByUserAtom);
  const addToast = useSetAtom(addToastAtom);

  const [isStopping, setIsStopping] = useState(false);
  const [isResuming, setIsResuming] = useState(false);

  const isRunning = status === "running";

  const handleStop = useCallback(async () => {
    if (!sessionId || isStopping) return;
    // Optimistic: mark stopped-by-user immediately (synchronous setState)
    setStoppedByUser(true);
    setIsStopping(true);
    try {
      const res = await fetch(
        `/api/v1/sessions/${encodeURIComponent(sessionId)}/kill`,
        { method: "POST" },
      );
      if (!res.ok) {
        // Rollback optimistic state
        setStoppedByUser(false);
        addToast({
          type: "error",
          title: "Failed to stop",
          message: "Try again, or refresh the page.",
        });
      }
    } catch {
      // Network/parse failure — rollback
      setStoppedByUser(false);
      addToast({
        type: "error",
        title: "Failed to stop",
        message: "Try again, or refresh the page.",
      });
    } finally {
      setIsStopping(false);
    }
  }, [sessionId, isStopping, setStoppedByUser, addToast]);

  const handleResume = useCallback(async () => {
    if (!sessionId || isResuming) return;
    // Optimistic: clear stopped flag (synchronous setState)
    setStoppedByUser(false);
    setIsResuming(true);
    try {
      const res = await fetch(
        `/api/v1/sessions/${encodeURIComponent(sessionId)}/resume`,
        { method: "POST" },
      );
      if (!res.ok) {
        // Rollback optimistic state
        setStoppedByUser(true);
        addToast({
          type: "error",
          title: "Failed to resume",
          message: "Try again, or refresh the page.",
        });
      }
    } catch {
      setStoppedByUser(true);
      addToast({
        type: "error",
        title: "Failed to resume",
        message: "Try again, or refresh the page.",
      });
    } finally {
      setIsResuming(false);
    }
  }, [sessionId, isResuming, setStoppedByUser, addToast]);

  // Cmd+. (macOS) / Ctrl+. (others) → Stop when running
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (e: KeyboardEvent) => {
      const isStopShortcut =
        isMac() ? e.metaKey && e.key === "." : e.ctrlKey && e.key === ".";
      if (isStopShortcut && isRunning && !isStopping) {
        e.preventDefault();
        void handleStop();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isRunning, isStopping, handleStop]);

  // Live indicator dot color — UI-SPEC §9.1
  let dotClass = "bg-emerald-500";
  let dotLabel = "Agent is idle";
  if (connection === "disconnected") {
    dotClass = "bg-red-500";
    dotLabel = "Connection lost";
  } else if (isRunning) {
    dotClass = "bg-primary animate-pulse";
    dotLabel = "Agent is streaming";
  } else if (status === "stopped") {
    dotClass = "bg-red-500";
    dotLabel = "Agent is stopped";
  }

  if (!sessionId) {
    // No active session — render only the live dot for status visibility
    return (
      <div
        className="flex items-center gap-1.5 text-xs text-muted-foreground"
        aria-label="No active session"
      >
        <span className={cn("h-2 w-2 rounded-full bg-emerald-500")} />
        <span className="hidden sm:inline">Idle</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      {/* Live indicator dot — always visible */}
      <div
        className="flex items-center gap-1.5 text-xs text-muted-foreground"
        aria-label={dotLabel}
      >
        <span className={cn("h-2 w-2 rounded-full", dotClass)} />
        <span className="hidden sm:inline">
          {connection === "disconnected"
            ? "Disconnected"
            : isRunning
              ? "Live"
              : status === "stopped"
                ? "Stopped"
                : "Idle"}
        </span>
      </div>

      {/* Stop button — visible only when running */}
      {isRunning && (
        <button
          type="button"
          onClick={handleStop}
          disabled={isStopping}
          aria-label={`Stop session ${truncateId(sessionId)} (${isMac() ? "⌘" : "Ctrl+"}.`}
          aria-busy={isStopping}
          aria-disabled={isStopping}
          title={`Stop session (${isMac() ? "⌘" : "Ctrl+"}.`}
          className={cn(
            "inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-1 text-xs font-normal text-foreground",
            "transition-colors duration-150",
            "hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30",
            "active:scale-95",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            isStopping && "opacity-50 cursor-wait",
          )}
        >
          <Square className="h-3.5 w-3.5 fill-current" />
          <span>Stop</span>
        </button>
      )}

      {/* Resume button — visible only when stopped/paused */}
      {!isRunning && status !== "idle" && (
        <button
          type="button"
          onClick={handleResume}
          disabled={isResuming}
          aria-label={`Resume session ${truncateId(sessionId)}`}
          aria-busy={isResuming}
          aria-disabled={isResuming}
          title="Resume session"
          className={cn(
            "inline-flex items-center gap-1 rounded-md bg-primary px-2 py-1 text-xs font-normal text-primary-foreground",
            "transition-colors duration-150",
            "hover:bg-primary/90",
            "active:scale-95",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            isResuming && "opacity-50 cursor-wait",
          )}
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span>Resume</span>
        </button>
      )}
    </div>
  );
}