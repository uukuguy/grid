import { useEffect } from "react";
import { useAtom } from "jotai";
import { AppLayout } from "./components/layout/AppLayout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { ToastContainer } from "./components/Toast";
import { activeTabAtom, TAB_METADATA } from "./atoms/ui";
import Chat from "./pages/Chat";
import Tasks from "./pages/Tasks";
import Schedule from "./pages/Schedule";
import Tools from "./pages/Tools";
import Memory from "./pages/Memory";
import Debug from "./pages/Debug";
import McpWorkbench from "./pages/McpWorkbench";
import Collaboration from "./pages/Collaboration";
import Flows from "./pages/Flows";
import { wsManager } from "./ws/manager";

export default function App() {
  const [activeTab] = useAtom(activeTabAtom);

  // OBSTACK Phase C.0.5 — gate wsManager on the active tab's
  // TAB_METADATA.requiresWebSocket. This stops the "Connection Lost /
  // WebSocket disconnected" cycle from running on tabs that don't
  // need WS (Business Flows / Memory / Debug / MCP / Collaboration).
  //
  // Without this gate, SessionBar's wsManager.switchSession() call
  // (which fires on its initial mount, regardless of tab) would
  // reconnect-loop against grid-server /ws which 404s.
  useEffect(() => {
    wsManager.setEnabled(TAB_METADATA[activeTab].requiresWebSocket);
  }, [activeTab]);

  return (
    <ErrorBoundary>
      <AppLayout>
        {activeTab === "chat" && <Chat />}
        {activeTab === "tasks" && <Tasks />}
        {activeTab === "schedule" && <Schedule />}
        {activeTab === "tools" && <Tools />}
        {activeTab === "memory" && <Memory />}
        {activeTab === "debug" && <Debug />}
        {activeTab === "mcp" && <McpWorkbench />}
        {activeTab === "collaboration" && <Collaboration />}
        {activeTab === "flows" && <Flows />}
      </AppLayout>
      <ToastContainer />
    </ErrorBoundary>
  );
}
