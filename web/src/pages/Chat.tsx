import { useEffect } from "react";
import { useStore, useAtomValue } from "jotai";
import { MessageList } from "@/components/chat/MessageList";
import { ChatInput } from "@/components/chat/ChatInput";
import { StreamingDisplay } from "@/components/chat/StreamingDisplay";
import { wsManager } from "@/ws/manager";
import { handleWsEvent } from "@/ws/events";
import { sessionIdAtom } from "@/atoms/session";
import { executionRecordsAtom } from "@/atoms/debug";
import type { ToolExecutionRecord } from "@/atoms/debug";
import {
  addToastAtom,
  connectionStatusAtom,
  reconnectAttemptAtom,
} from "@/atoms/ui";
import { sessionsClient } from "@/api/sessions";

export default function Chat() {
  return (
    <>
      <WsEventBridge />
      <div className="flex flex-1 flex-col overflow-hidden">
        <MessageList />
        <StreamingDisplay />
        <ChatInput />
      </div>
    </>
  );
}

function WsEventBridge() {
  const store = useStore();
  const sessionId = useAtomValue(sessionIdAtom);

  // When session is established, load execution history from API
  useEffect(() => {
    if (!sessionId) return;
    // OBSTACK Phase E.1 — route through the shared sessions client
    // (same surface as the Python ``SessionsClient``). The wire
    // shape is a top-level JSON array (``Json<Vec<ToolExecution>>``
    // per ``crates/grid-server/src/api/executions.rs``), so we
    // narrow ``unknown`` -> array via Array.isArray.
    sessionsClient
      .list_executions(sessionId, { limit: 100 })
      .then((data: unknown) => {
        if (!Array.isArray(data) || data.length === 0) return;
        const records = data as ToolExecutionRecord[];
        store.set(executionRecordsAtom, (prev) => {
          // Merge: keep any newer real-time records, backfill with DB history
          const existingIds = new Set(prev.map((e) => e.id));
          const newRecords = records.filter((e) => !existingIds.has(e.id));
          // Prepend history (older), append real-time (newer)
          return [...newRecords, ...prev];
        });
      })
      .catch(() => {/* ignore */});
  }, [sessionId, store]);

  useEffect(() => {
    wsManager.connect();
    wsManager.onMessage((msg) => {
      handleWsEvent(msg, store.set, store.get);
    });
    // OBSTACK Phase C.0.8 — only surface the "Connection Lost" toast
    // when the server actually dropped the connection, not when we
    // ourselves gave up (404 / refused / handshake failed). When the
    // give-up path fires (grid-server doesn't expose /ws today),
    // the user has already seen the give-up message in the console
    // and we're now in "auto-retry disabled" mode — no point alarming
    // them with a toast that would loop otherwise.
    wsManager.onDisconnect((reason) => {
      if (reason === "gave_up" || reason === "server_unavailable") {
        return;
      }
      store.set(addToastAtom, {
        type: "warning",
        title: "Connection Lost",
        message: "WebSocket disconnected. Attempting to reconnect...",
      });
    });
    wsManager.onStatusChange((status, attempt) => {
      store.set(connectionStatusAtom, status);
      store.set(reconnectAttemptAtom, attempt ?? 0);
    });
    return () => wsManager.disconnect();
  }, [store]);

  return null;
}
