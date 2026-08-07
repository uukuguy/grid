// OBSTACK Phase E.2 — TS mirror of eaasp_common.McpClient.
// Wraps the grid-server /api/v1/mcp/servers/* surface for the React
// UI. Same 1:1 surface as the Python client; method names,
// response shapes, and HTTP semantics are identical so the two
// stay in lockstep.
import { api } from "./client";
import type {
  CallToolRequest,
  CallToolResponse,
  McpClientOptions,
  McpServer,
  McpServerStatus,
  McpToolInfo,
} from "./mcp_types";

export type {
  CallToolRequest,
  CallToolResponse,
  McpClientOptions,
  McpServer,
  McpServerStatus,
  McpToolInfo,
};

export class McpClient {
  private baseUrl: string;
  private authToken: string | null;

  constructor(options: McpClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
  }

  // ─── Server CRUD + lifecycle ────────────────────────────
  async list_servers(): Promise<McpServer[]> {
    // OBSTACK Phase E.2 — the server returns a top-level JSON
    // array (``Json<Vec<McpServerResponse>>`` per
    // ``crates/grid-server::api::mcp_servers::list_servers``).
    // We pass the raw array through unchanged and let callers
    // narrow via typed construction.
    return (await this.fetch<unknown>("/api/v1/mcp/servers")) as McpServer[];
  }

  async get_server(id: string): Promise<McpServer> {
    return this.fetch<McpServer>(
      `/api/v1/mcp/servers/${encodeURIComponent(id)}`,
    );
  }

  async get_status(id: string): Promise<McpServerStatus | null> {
    // The endpoint returns ``Json<Option<McpServerStatusResponse>>``
    // — null when the server is unknown. We unwrap null here so
    // callers don't have to handle the nullable JSON shape.
    const body = await this.fetch<unknown>(
      `/api/v1/mcp/servers/${encodeURIComponent(id)}/status`,
    );
    return (body ?? null) as McpServerStatus | null;
  }

  async start_server(id: string): Promise<McpServerStatus> {
    return this.fetch<McpServerStatus>(
      `/api/v1/mcp/servers/${encodeURIComponent(id)}/start`,
      { method: "POST" },
    );
  }

  async stop_server(id: string): Promise<McpServerStatus> {
    return this.fetch<McpServerStatus>(
      `/api/v1/mcp/servers/${encodeURIComponent(id)}/stop`,
      { method: "POST" },
    );
  }

  // ─── Tools + executions ──────────────────────────────────
  async list_tools(server_id: string): Promise<McpToolInfo[]> {
    return (await this.fetch<unknown>(
      `/api/v1/mcp/servers/${encodeURIComponent(server_id)}/tools`,
    )) as McpToolInfo[];
  }

  async call_tool(
    server_id: string,
    req: CallToolRequest,
  ): Promise<CallToolResponse> {
    // The endpoint returns 200 OK even when the tool errors at
    // runtime — the error surfaces in the ``error`` field of the
    // response. Callers branch on ``response.error``.
    return this.fetch<CallToolResponse>(
      `/api/v1/mcp/servers/${encodeURIComponent(server_id)}/call`,
      { method: "POST", body: JSON.stringify(req) },
    );
  }

  async list_executions(server_id: string): Promise<CallToolResponse[]> {
    // ``Json<Vec<McpToolCallResponse>>`` — top-level array, same
    // passthrough as ``sessionsClient.list_executions``.
    return (await this.fetch<unknown>(
      `/api/v1/mcp/servers/${encodeURIComponent(server_id)}/executions`,
    )) as CallToolResponse[];
  }

  // ─── Internals ──────────────────────────────────────────
  private async fetch<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers ?? {});
    if (this.authToken) {
      headers.set("Authorization", `Bearer ${this.authToken}`);
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
        `MCP ${resp.status} ${resp.statusText || ""} from ${path}: ${text}`,
      );
    }
    if (resp.status === 204) return undefined as unknown as T;
    if (resp.headers.get("content-type")?.includes("application/json")) {
      return (await resp.json()) as T;
    }
    return undefined as unknown as T;
  }
}

// Phase E.2 — the default client reuses the existing `api`
// singleton (which already knows the auth token). The default
// base URL is ``http://127.0.0.1:3001`` — matches the
// eaasp-sessions-client default, so the two client families land
// on the same grid-server backend.
const authToken = api.getToken();

export const mcpClient = new McpClient({
  baseUrl:
    (typeof import.meta !== "undefined" &&
      (import.meta as { env?: Record<string, string> }).env
        ?.VITE_MCP_BASE_URL) ||
    "http://127.0.0.1:3001",
  authToken: authToken ?? undefined,
});
