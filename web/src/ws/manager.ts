import type { ClientMessage, ServerMessage } from "./types";
import { mapWireMessageToServerMessage } from "./types";
import { isConfigReady, getWsUrl } from "../config";
import type { ConnectionStatus } from "@/atoms/ui";

type MessageHandler = (msg: ServerMessage) => void;
// OBSTACK Phase C.0.8 — disconnect reason so consumers can suppress
// the toast when we already gave up (server unavailable) vs. the user
// genuinely losing a working connection.
export type DisconnectReason = "server_unavailable" | "gave_up" | "server_disconnected";
type DisconnectHandler = (reason: DisconnectReason) => void;
type StatusChangeHandler = (status: ConnectionStatus, attempt?: number) => void;

class WsManager {
  private ws: WebSocket | null = null;
  private url: string = '';
  private handler: MessageHandler | null = null;
  private disconnectHandler: DisconnectHandler | null = null;
  private statusChangeHandler: StatusChangeHandler | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalDisconnect = false;
  private currentSessionId: string | null = null;

  // OBSTACK Phase C.0.5 — disabled by default. Caller (App.tsx)
  // enables WS only when the active tab requires it (per TAB_METADATA).
  // When false, connect() is a no-op and disconnect() is also a no-op.
  // This is what stops the "Connection Lost" cycle from running when
  // the user is on the Business Flows dashboard (which doesn't need WS)
  // and tabs that don't require WS are active.
  private enabled = false;
  /** Subscribe to enable/disable events so consumers (e.g. Chat's
   *  WsEventBridge) can react if needed. */
  private enabledHandlers: Set<(enabled: boolean) => void> = new Set();

  constructor() {}

  /**
   * Get WebSocket URL from config or fallback.
   * Appends ?session_id=xxx when a session is active.
   * Appends &token=xxx when an auth token is available (browser WS API
   * cannot send custom HTTP headers, so the token travels as a query param).
   */
  private getUrl(sessionId?: string | null): string {
    // OBSTACK Phase D.0 — grid-server's actual canonical WebSocket
    // path is `/v1/sessions/{id}/stream`, NOT `/ws` (the `/ws` legacy
    // path was removed in Phase A.1, per the comment in
    // crates/grid-server/src/ws.rs). Hitting `/ws` returns 404 and the
    // user sees "Disconnected" — the original symptom this whole
    // Phase C.0 saga was trying to silence.
    let base: string;
    if (isConfigReady()) {
      try {
        const proto = getWsUrl().replace(/^ws/, "http");
        base = `${proto}/v1/sessions/`;
      } catch {
        const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        base = `${proto}//${window.location.host}/v1/sessions/`;
      }
    } else {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      base = `${proto}//${window.location.host}/v1/sessions/`;
    }

    // Append the session id from caller or most recent switchSession.
    const sid = sessionId ?? this.currentSessionId;
    if (!sid) {
      // No session yet — caller forgot to call switchSession first.
      // Returning the bare /v1/sessions/ path will produce a routing
      // 404 ("missing path parameter"), which the ws manager will
      // surface as a one-shot toast on disconnect (legitimate case:
      // operator hasn't started a session yet). Don't fabricate a
      // placeholder; fail loudly.
      throw new Error("[WS] cannot build URL: no currentSessionId");
    }
    base = `${base}${encodeURIComponent(sid)}/stream`;

    // Phase D.0 — grid-server reads auth token from a query param
    // (browsers can't send custom headers on a WebSocket upgrade).
    const params: string[] = [];
    const token = localStorage.getItem("grid_token") ?? undefined;
    if (token) {
      params.push(`token=${encodeURIComponent(token)}`);
    }
    if (params.length > 0) {
      base += `?${params.join("&")}`;
    }
    return base;
  }

  connect(sessionId?: string | null) {
    // OBSTACK Phase C.0.5 — no-op when disabled.
    if (!this.enabled) {
      return;
    }
    if (sessionId !== undefined) {
      this.currentSessionId = sessionId ?? null;
    }
    // Get URL on each connect to support dynamic config
    this.url = this.getUrl();

    // Already connected or connecting - don't create another connection
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    // Close any existing connection before creating a new one
    if (this.ws) {
      this.ws.close();
    }

    // Reset intentional disconnect flag on new connect attempt
    this.intentionalDisconnect = false;

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log("[WS] Connected", this.currentSessionId ? `(session: ${this.currentSessionId})` : "");
      this.reconnectAttempts = 0;
      this.statusChangeHandler?.("connected", 0);
    };

    this.ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        // Phase E.3 commit fix (2026-08-08) — the wire sends
        // ``{"type":"chunk", "chunk_type": 1-9, "payload": {...}}``
        // envelopes (per ``crates/grid-server/src/ws_chunk.rs``),
        // but ``web/src/ws/types.ts`` historically declared a
        // flat discriminator (``type: "text_delta"`` etc.).
        // Translating here keeps every existing
        // ``web/src/ws/events.ts`` switch case working.
        const msg = mapWireMessageToServerMessage(raw);
        if (msg === null) {
          // Unknown wire envelope — log once (per session) so
          // the developer notices schema drift, but don't
          // pollute the console on every frame.
          if (!(this as unknown as { __loggedUnknownWire: boolean }).__loggedUnknownWire) {
            console.warn("[WS] unknown wire envelope (dropped):", raw);
            (this as unknown as { __loggedUnknownWire: boolean }).__loggedUnknownWire = true;
          }
          return;
        }
        this.handler?.(msg);
      } catch (e) {
        console.error("[WS] Parse error:", e);
      }
    };

    this.ws.onclose = () => {
      console.log("[WS] Disconnected");
      if (!this.intentionalDisconnect) {
        // OBSTACK Phase C.0.8 — pass a reason so consumers (Chat's
        // WsEventBridge) can suppress toasts when the disconnect was
        // caused by our own give-up logic (Phase C.0.5 / commit 17),
        // not by a transient server outage the user should see.
        this.disconnectHandler?.("server_unavailable");
        this.statusChangeHandler?.("disconnected", 0);
      }
      this.scheduleReconnect();
    };

    this.ws.onerror = (err) => {
      console.error("[WS] Error:", err);
      // OBSTACK Phase C.0.5 — if the WS server is unreachable (404,
      // refused, etc.), stop retrying. Otherwise the user sees the
      // "Connection Lost / WebSocket disconnected. Attempting to
      // reconnect..." toast forever even though the underlying
      // problem (grid-server doesn't expose /ws today) won't fix
      // itself. Disable the manager and the user can switch tabs
      // without seeing the loop.
      //
      // Phase D (multi-tenant) adds grid-server /ws — at that point
      // removing this disable gives the user a normal retry loop
      // until the server comes back.
      if (this.reconnectAttempts >= 1) {
        console.warn("[WS] Giving up after repeated failures; disabling until next enable().");
        this.intentionalDisconnect = true;
        this.setEnabled(false);
        // C.0.8 — surface the give-up to the disconnect handler so
        // consumers can suppress the toast (the user doesn't need to
        // see "Connection Lost" if we already gave up).
        this.disconnectHandler?.("gave_up");
      }
    };
  }

  /**
   * Switch to a different session. Disconnects the current WS and
   * reconnects with the new session_id query parameter.
   */
  switchSession(sessionId: string) {
    console.log(`[WS] Switching to session ${sessionId}`);
    this.currentSessionId = sessionId;

    // Tear down the current connection without triggering auto-reconnect
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.intentionalDisconnect = true;
    this.ws?.close();
    this.ws = null;

    // Reset reconnect state and connect fresh — but only if WS is
    // enabled (Phase C.0.5). When the active tab doesn't need WS, we
    // still record the session id so a future enable() can pick up
    // without losing the selection, but we don't trigger a connect.
    this.reconnectAttempts = 0;
    this.intentionalDisconnect = false;
    if (this.enabled) {
      this.connect(sessionId);
    } else {
      this.statusChangeHandler?.("disconnected", 0);
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    // Mark as intentional disconnect to prevent reconnection
    this.intentionalDisconnect = true;
    this.ws?.close();
    this.ws = null;
    // Reset the attempt counter so the next connect() starts at attempt 1
    this.reconnectAttempts = 0;
    this.statusChangeHandler?.("disconnected", 0);
  }

  /**
   * Enable / disable the manager. When `enabled` is false, `connect()`
   * is a no-op, `switchSession()` is a no-op, and any in-flight
   * reconnect attempts are cancelled.
   *
   * Phase C.0.5: App.tsx calls this based on the active tab's
   * TAB_METADATA.requiresWebSocket. The default-tab change in
   * commit b9006a15 stopped the *initial* Connection Lost cycle, but
   * clicking Chat still triggered SessionBar → wsManager.switchSession
   * → connect() → grid-server /ws → 404. With enabled=false set when
   * the user lands on a non-WS tab (Business Flows by default), the
   * "Connection Lost" cycle stops even when the user later clicks Chat
   * before the Chat component is ready — and resumes cleanly when the
   * user clicks Chat.
   */
  setEnabled(enabled: boolean): void {
    if (this.enabled === enabled) return;
    this.enabled = enabled;
    this.enabledHandlers.forEach((h) => h(enabled));
    if (!enabled) {
      // Cancel any in-flight reconnect attempts and close the socket.
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = null;
      }
      this.intentionalDisconnect = true;
      this.ws?.close();
      this.ws = null;
      this.reconnectAttempts = 0;
      this.statusChangeHandler?.("disconnected", 0);
    }
  }

  /** Subscribe to enable/disable transitions. Returns an unsubscribe
   *  function so consumers (e.g. Chat's WsEventBridge) can react. */
  onEnabledChange(handler: (enabled: boolean) => void): () => void {
    this.enabledHandlers.add(handler);
    return () => this.enabledHandlers.delete(handler);
  }

  send(msg: ClientMessage) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn("[WS] Not connected, cannot send");
      return;
    }
    this.ws.send(JSON.stringify(msg));
  }

  onMessage(handler: MessageHandler) {
    this.handler = handler;
  }

  onDisconnect(handler: DisconnectHandler) {
    this.disconnectHandler = handler;
  }

  onStatusChange(handler: StatusChangeHandler) {
    this.statusChangeHandler = handler;
  }

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect() {
    // Don't reconnect if this was an intentional disconnect
    if (this.intentionalDisconnect) return;

    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.statusChangeHandler?.("reconnecting", this.reconnectAttempts);
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }
}

export const wsManager = new WsManager();
