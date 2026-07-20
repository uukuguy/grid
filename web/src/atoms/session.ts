import { atom } from "jotai";

export interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  timestamp: number;
}

export interface ToolExecution {
  toolId: string;
  toolName: string;
  input: Record<string, unknown>;
  output?: string;
  success?: boolean;
  status: "running" | "complete";
}

// ── Session Status (D-02, REQ-WEB-03) ──

/**
 * Lifecycle flag toggled by the SessionControls Stop/Resume buttons.
 * - `true` when the user explicitly clicked Stop
 * - `false` when the user clicked Resume or a new session starts
 */
export const stoppedByUserAtom = atom<boolean>(false);

/**
 * Derived session status:
 *   - `running` when isStreaming is true OR any tool is in `running` state
 *   - `stopped` when stoppedByUserAtom is true (user pressed Stop)
 *   - `idle` otherwise (no streaming, no tool, not user-stopped)
 *   - `paused` reserved for future use (server-driven pause)
 */
export const sessionStatusAtom = atom<
  "running" | "paused" | "stopped" | "idle"
>((get) => {
  const isStreaming = get(isStreamingAtom);
  const hasRunningTool = get(toolExecutionsAtom).some(
    (t) => t.status === "running",
  );
  if (isStreaming || hasRunningTool) return "running";
  const stopped = get(stoppedByUserAtom);
  return stopped ? "stopped" : "idle";
});

/**
 * Recently-added memory IDs (REQ-WEB-04). Each id is removed 4500ms after
 * being added (3s highlight + 1.5s fade buffer per UI-SPEC §9.4).
 *
 * Read/write primitive atom so pages can subscribe to the current set.
 * The auto-expiration logic lives in `addRecentlyAddedMemoryIdAtom` below.
 */
const MEMORY_HIGHLIGHT_MS = 4500;

export const recentlyAddedMemoryIdsAtom = atom<string[]>([]);

/** Write-only atom: add a memory id (auto-expires after 4500ms). */
export const addRecentlyAddedMemoryIdAtom = atom(
  null,
  (get, set, id: string) => {
    const prev = get(recentlyAddedMemoryIdsAtom);
    if (prev.includes(id)) return;
    set(recentlyAddedMemoryIdsAtom, [...prev, id]);
    setTimeout(() => {
      set(
        recentlyAddedMemoryIdsAtom,
        get(recentlyAddedMemoryIdsAtom).filter((x) => x !== id),
      );
    }, MEMORY_HIGHLIGHT_MS);
  },
);

export interface SessionInfo {
  id: string;
  createdAt: string;
}

// ── Multi-Session State ──

/** List of all active sessions */
export const sessionsAtom = atom<SessionInfo[]>([]);

/** Currently active session ID */
export const activeSessionIdAtom = atom<string | null>(null);

/** Per-session messages storage */
export const perSessionMessagesAtom = atom<Map<string, ChatMsg[]>>(new Map());

// ── Backward-Compatible Derived Atoms ──

/**
 * sessionIdAtom — read/write alias for activeSessionIdAtom.
 * Existing consumers (ChatInput, WsEventBridge, pages) keep working unchanged.
 */
export const sessionIdAtom = atom(
  (get) => get(activeSessionIdAtom),
  (_get, set, value: string | null) => set(activeSessionIdAtom, value),
);

/**
 * messagesAtom — read/write that operates on the active session's messages
 * within perSessionMessagesAtom.
 *
 * When there is no active session yet (initial load), we use a standalone
 * fallback array so early messages are not lost.
 */
const fallbackMessagesAtom = atom<ChatMsg[]>([]);

export const messagesAtom = atom(
  (get) => {
    const activeId = get(activeSessionIdAtom);
    if (!activeId) return get(fallbackMessagesAtom);
    return get(perSessionMessagesAtom).get(activeId) ?? [];
  },
  (get, set, update: ChatMsg[] | ((prev: ChatMsg[]) => ChatMsg[])) => {
    const activeId = get(activeSessionIdAtom);
    if (!activeId) {
      // No active session yet — write to fallback
      if (typeof update === "function") {
        set(fallbackMessagesAtom, update(get(fallbackMessagesAtom)));
      } else {
        set(fallbackMessagesAtom, update);
      }
      return;
    }
    const map = new Map(get(perSessionMessagesAtom));
    const current = map.get(activeId) ?? [];
    const next = typeof update === "function" ? update(current) : update;
    map.set(activeId, next);
    set(perSessionMessagesAtom, map);
  },
);

/**
 * Migrate fallback messages into the active session's slot.
 * Called once after the first session_created event sets activeSessionIdAtom.
 */
export const migrateFallbackMessagesAtom = atom(null, (get, set) => {
  const activeId = get(activeSessionIdAtom);
  const fallback = get(fallbackMessagesAtom);
  if (!activeId || fallback.length === 0) return;
  const map = new Map(get(perSessionMessagesAtom));
  const existing = map.get(activeId) ?? [];
  map.set(activeId, [...fallback, ...existing]);
  set(perSessionMessagesAtom, map);
  set(fallbackMessagesAtom, []);
});

// ── Per-Turn Streaming State (not per-session, reset on each turn) ──

export const isStreamingAtom = atom(false);
export const streamingTextAtom = atom("");
export const streamingThinkingAtom = atom("");
export const toolExecutionsAtom = atom<ToolExecution[]>([]);
