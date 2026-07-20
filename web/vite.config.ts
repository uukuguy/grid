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
    port: 5180,
    proxy: {
      "/api": "http://localhost:3001",
      "/ws": {
        target: "ws://localhost:3001",
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
