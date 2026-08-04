import { createRoot } from "react-dom/client";
import { Provider } from "jotai";
import App from "./App";
import { initConfig } from "./config";
import "./globals.css";

// OBSTACK Phase C.0.1 — render immediately. config.ts has a built-in
// fallback that is good enough for Phase C.0 development (Phase C.0
// only needs L4 OBSTACK endpoints, which flowsApi hits directly via
// L4_BASE_URL — it does NOT go through the grid-server proxy).
//
// Why we don't await initConfig:
//   1. main.tsx used to `await initConfig()` before rendering. If
//      /api/v1/config returns 401 (grid-server requires auth), the await
//      throws and we never render → blank page → ws/manager floods the
//      log with "WebSocket disconnected / attempting to reconnect".
//   2. initConfig() runs in the background; the first render uses the
//      fallback. Once config resolves, downstream components pick up
//      the real ws_url / api_url via getConfig().
//   3. This matches web-platform's behavior (no initConfig at all).
async function main() {
  // Kick off initConfig in the background; don't await it.
  void initConfig().catch((err) => {
    console.warn("[App] initConfig failed (using fallback):", err);
  });

  // Render immediately so the user sees the UI even if grid-server
  // is down or returns 401 (Phase C.0 dashboard only needs L4).
  createRoot(document.getElementById("root")!).render(
    <Provider>
      <App />
    </Provider>,
  );
}

main();
