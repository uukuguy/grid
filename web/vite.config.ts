/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("src", import.meta.url).pathname,
    },
  },
  server: {
    // OBSTACK Phase C.0.1 fix: explicit IPv4 bind.
    //
    // Default `host: "localhost"` resolves to ::1 first (IPv6). When
    // the operator hits http://localhost:5180 in their browser the OS
    // may prefer IPv4 and get ECONNREFUSED. Pin to 127.0.0.1 to bind
    // IPv4 only — cross-platform stable for the Phase C.0 dashboard.
    host: "127.0.0.1",
    port: 5180,
    strictPort: true,
    proxy: {
      "/api": "http://127.0.0.1:3001",
      "/ws": {
        target: "ws://127.0.0.1:3001",
        ws: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // Exclude Playwright e2e specs — they run via `npx playwright test`,
    // not vitest. Without this, vitest tries to run them in jsdom and
    // chokes on the @playwright/test imports.
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
  },
});
