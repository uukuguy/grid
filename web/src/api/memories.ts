// OBSTACK Phase E.5 — TS mirror of eaasp_common.MemoriesClient.
// Wraps the grid-server /api/v1/memories surface for the
// React UI (Memory.tsx). Same 1:1 surface as the Python
// client; method names, response shapes, and HTTP
// semantics are identical so the two stay in lockstep.
//
// Phase E.5 narrow scope — only the two endpoints the React
// UI consumes: list_memories + working_memory. The full CRUD
// surface (``create_memory`` / ``delete_memory`` / etc.) is
// out of scope here until a second caller needs it.
//
// Phase E.5 first-write security: Bearer header reaches the
// wire on every transport method (Phase E.4 lesson from
// commit 1787083e — locked on first write, no follow-up
// fix).
import { api } from "./client";
import type {
  ListMemoriesParams,
  ListMemoriesResponse,
  MemoriesClientOptions,
  WorkingMemoryResponse,
} from "./memories_types";

export type {
  ListMemoriesParams,
  ListMemoriesResponse,
  MemoriesClientOptions,
  WorkingMemoryResponse,
};

export class MemoriesClient {
  private baseUrl: string;
  private authToken: string | null;
  private getToken: (() => string | null) | null;

  constructor(options: MemoriesClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
    this.getToken = options.getToken ?? null;
  }

  async list_memories(
    params?: ListMemoriesParams,
  ): Promise<ListMemoriesResponse> {
    // Phase E.5 wire-shape note: the URL always carries
    // ``?limit=N`` (matches the legacy Memory.tsx ``?limit=100``).
    // ``search_params`` is built with explicit field checks so
    // omitted keys don't reach the URL (the legacy UI passed
    // ``session_id`` only when the user picked one).
    const search = new URLSearchParams();
    search.set("limit", String(params?.limit ?? 100));
    if (params?.session_id) search.set("session_id", params.session_id);
    if (params?.q) search.set("q", params.q);
    return this.fetch<ListMemoriesResponse>(
      `/api/v1/memories?${search.toString()}`,
    );
  }

  async working_memory(): Promise<WorkingMemoryResponse> {
    return this.fetch<WorkingMemoryResponse>(
      "/api/v1/memories/working",
    );
  }

  private async fetch<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});
    // E.4 lesson from commit 1787083e: read the token FRESH
    // per request. Module-load snapshots silently dropped
    // the Bearer on the wire.
    const token = this.getToken ? this.getToken() : this.authToken;
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const resp = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      throw new Error(
        `Memories ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    if (resp.status === 204) return undefined as unknown as T;
    if (resp.headers.get("content-type")?.includes("application/json")) {
      return (await resp.json()) as T;
    }
    return undefined as unknown as T;
  }
}

// Phase E.5 — the default client reuses the existing
// ``api`` singleton via the ``getToken`` callback. Same
// base URL default as the other clients (``http://
// 127.0.0.1:3001`` — grid-server).
export const memoriesClient = new MemoriesClient({
  baseUrl:
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_MEMORIES_BASE_URL) ||
    "http://127.0.0.1:3001",
  getToken: () => api.getToken(),
});
