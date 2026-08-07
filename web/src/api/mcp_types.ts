// OBSTACK Phase E.2 — TS mirror of eaasp_common.McpClient.
// 1:1 mirror of tools/eaasp-common/src/eaasp_common/mcp_models.py
// + mcp_client.py. When grid-server changes a wire field, both
// these files (and the Python parent) get updated together.

export interface McpServer {
  id: string;
  name: string;
  source: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  transport: "stdio" | "sse";
  url: string | null;
  enabled: boolean;
  runtime_status: string;
  tool_count: number;
  created_at: string;
  updated_at: string;
}

export interface McpServerStatus {
  id: string;
  name: string;
  status: string;
  pid: number | null;
  error: string | null;
  tool_count: number;
}

export interface McpToolInfo {
  name: string;
  description: string | null;
  input_schema: unknown;
  annotations?: Record<string, unknown> | null;
}

export interface CallToolRequest {
  tool_name: string;
  arguments: unknown;
}

export interface CallToolResponse {
  id: string;
  server_id: string;
  tool_name: string;
  result: unknown;
  error: string | null;
  duration_ms: number;
  executed_at: string;
}

export interface McpClientOptions {
  baseUrl: string;
  /** Snapshotted auth token (refresh-invisible). Prefer
   *  ``getToken`` when the caller owns its own auth state. */
  authToken?: string | null;
  /** Per-request token getter — LOGOUT / refresh propagate
   *  without re-creating the client. Wins over ``authToken``
   *  when both are supplied. */
  getToken?: () => string | null;
}
