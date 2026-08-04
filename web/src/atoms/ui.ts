import { atom } from "jotai";

// OBSTACK Phase C.0 — add "flows" tab for the global observability
// dashboard (OBSTACK_HANDBOOK.md Ch14.3 Phase C.0).
export type TabId =
  | "chat"
  | "tasks"
  | "schedule"
  | "tools"
  | "debug"
  | "memory"
  | "mcp"
  | "collaboration"
  | "flows";
// OBSTACK Phase C.0.3 — configurable default tab.
//
// Why this exists:
//   1. Chat.tsx mounts WsEventBridge which calls wsManager.connect()
//      on mount. If grid-server doesn't expose /ws (current state —
//      grid-server is HTTP+SSE only), every connect attempt 404s →
//      reconnect loop → "Connection Lost / WebSocket disconnected"
//      toast on every page load.
//   2. Defaulting to a tab that needs a working WS connection is the
//      root cause of that toast. Operators don't need chat on landing.
//   3. The default is now `VITE_DEFAULT_TAB` (env var) so operators
//      can pick what they see first. Without it, we pick "flows"
//      (Phase C.0 OBSTACK dashboard — the new entry point).
//
// Phase D will revisit when grid-server exposes /ws (real WS or SSE
// upgrade); at that point chat can be the default again.

const DEFAULT_TAB_FROM_ENV = (
  // Vite injects VITE_-prefixed env vars into the bundle at build time.
  // In dev mode, undefined → fallback to "flows".
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ((import.meta as any).env?.VITE_DEFAULT_TAB as TabId | undefined)
) ?? "flows";

export const activeTabAtom = atom<TabId>(DEFAULT_TAB_FROM_ENV);
export const sidebarOpenAtom = atom(false);

// ── Tab metadata (Phase C.0.3 user feedback) ────────────────────────
//
// Each tab declares what it needs to be useful. This lets the boot
// path make smart defaults and lets SessionBar / ws/manager skip
// work when a tab that doesn't need it is active.
//
// Why this exists:
//   - The original code unconditionally tried to connect WS even when
//     the active tab (Chat) couldn't succeed because grid-server
//     doesn't expose /ws today. That caused the "Connection Lost"
//     toast on every page load.
//   - With TabMetadata, App.tsx can choose what to initialize based
//     on what the active tab actually needs. Phase D (multi-tenant)
//     will add `requiresAuth: true` for tabs that need grid-server.

export interface TabMetadata {
  /** Display label shown in the TabBar. */
  label: string;
  /** True if this tab needs a WebSocket / SSE connection to function.
   *  When false, the WS manager stays idle and the user doesn't see
   *  the "Connection Lost" toast. */
  requiresWebSocket: boolean;
  /** True if this tab needs grid-server's chat sessions REST API
   *  (/api/v1/sessions/...). Phase C.0 flows doesn't; chat does. */
  requiresGridServer: boolean;
}

export const TAB_METADATA: Record<TabId, TabMetadata> = {
  // Phase C.0 — operators land here. No WS, no grid-server needed.
  flows: {
    label: "Business Flows",
    requiresWebSocket: false,
    requiresGridServer: false,
  },
  // Chat mounts WS + grid-server; only initialized when ChatTab active.
  chat: {
    label: "Chat",
    requiresWebSocket: true,
    requiresGridServer: true,
  },
  tasks: { label: "Tasks", requiresWebSocket: false, requiresGridServer: true },
  schedule: { label: "Schedule", requiresWebSocket: false, requiresGridServer: true },
  tools: { label: "Tools", requiresWebSocket: false, requiresGridServer: true },
  memory: { label: "Memory", requiresWebSocket: false, requiresGridServer: false },
  debug: { label: "Debug", requiresWebSocket: false, requiresGridServer: false },
  mcp: { label: "MCP", requiresWebSocket: false, requiresGridServer: false },
  collaboration: {
    label: "Collab",
    requiresWebSocket: false,
    requiresGridServer: false,
  },
};

// ── Toast Notifications ──

export type ToastType = "success" | "error" | "warning" | "info" | "memory";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  title?: string;
  /** Auto-dismiss duration in ms (default: 5000, memory=4000) */
  duration?: number;
}

export type AddToastInput = Omit<Toast, "id">;

/** Read-only atom holding the current toast stack */
export const toastsAtom = atom<Toast[]>([]);

/** Write-only atom: add a toast */
export const addToastAtom = atom(null, (get, set, input: AddToastInput) => {
  const toast: Toast = { ...input, id: crypto.randomUUID() };
  set(toastsAtom, [...get(toastsAtom), toast]);
});

/** Truncate a string to `max` characters, appending "…" if cut. */
export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "…";
}

export interface MemoryEventInput {
  content: string;
  /** Optional explicit memory id (else a random one is generated). */
  id?: string;
}

/**
 * Write-only atom: emit a `memory` toast for a new memory write (D-02, REQ-WEB-02).
 * Title: "Memory written" (verbatim per UI-SPEC §9.2).
 * Message: "Stored: {first 60 chars}…".
 * Duration: 4000ms (UI-SPEC §9.2 default).
 */
export const pushMemoryEventAtom = atom(
  null,
  (_get, set, input: MemoryEventInput) => {
    const body = truncate(input.content, 60);
    set(addToastAtom, {
      type: "memory",
      title: "Memory written",
      message: `Stored: ${body}`,
      duration: 4000,
    });
  },
);

/** Write-only atom: remove a toast by id */
export const removeToastAtom = atom(null, (get, set, id: string) => {
  set(
    toastsAtom,
    get(toastsAtom).filter((t) => t.id !== id),
  );
});

// ── WebSocket Connection Status ──

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

/** Current WebSocket connection status */
export const connectionStatusAtom = atom<ConnectionStatus>("disconnected");

/** Current reconnect attempt count (0 when connected) */
export const reconnectAttemptAtom = atom<number>(0);
