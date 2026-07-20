import { atom } from "jotai";

export type TabId = "chat" | "tasks" | "schedule" | "tools" | "debug" | "memory" | "mcp" | "collaboration";
export const activeTabAtom = atom<TabId>("chat");
export const sidebarOpenAtom = atom(false);

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
