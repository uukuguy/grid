import { useState, useEffect } from "react";
import { mcpClient, type McpServer } from "../../api/mcp";

interface ServerFormData {
  name: string;
  transport: "stdio" | "sse";
  command: string;
  args: string;
  url: string;
}

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "running": return <span title="running">🟢</span>;
    case "stopped": return <span title="stopped">⚪</span>;
    case "error":   return <span title="error">🔴</span>;
    case "starting":return <span title="starting">⏳</span>;
    default:        return <span title={status}>⚪</span>;
  }
}

function TransportBadge({ transport, url }: { transport: string; url?: string }) {
  if (transport === "sse") {
    return (
      <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-mono">
        SSE {url ? `· ${url.slice(0, 30)}${url.length > 30 ? "…" : ""}` : ""}
      </span>
    );
  }
  return (
    <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-secondary text-muted-foreground font-mono">
      stdio
    </span>
  );
}

export function ServerList() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState<ServerFormData>({
    name: "",
    transport: "stdio",
    command: "",
    args: "",
    url: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadServers = () => {
    setLoading(true);
    // OBSTACK Phase E.2 — route through the shared McpClient (same
    // surface as the Python ``McpClient``). The default client
    // targets grid-server :3001 via the same base-URL config the
    // rest of the UI uses.
    mcpClient
      .list_servers()
      .then((data: McpServer[]) => {
        setServers(Array.isArray(data) ? data : []);
        setError(null);
        setLoading(false);
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
  };

  useEffect(() => { loadServers(); }, []);

  const toggleServer = async (serverId: string, currentStatus: string) => {
    // OBSTACK Phase E.2 — start/stop lifecycle routed through the
    // shared client. Returns the updated ``McpServerStatus``
    // payload; we reload the list to pick up the new
    // ``runtime_status`` (the status payload + the list row are
    // denormalized — the source of truth is the list endpoint).
    try {
      if (currentStatus === "running") {
        await mcpClient.stop_server(serverId);
      } else {
        await mcpClient.start_server(serverId);
      }
      loadServers();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      const payload: Record<string, unknown> = {
        name: formData.name,
        transport: formData.transport,
      };

      if (formData.transport === "stdio") {
        if (!formData.command) {
          setFormError("Command is required for stdio transport");
          setSubmitting(false);
          return;
        }
        payload.command = formData.command;
        payload.args = formData.args ? formData.args.split(",").map((s) => s.trim()).filter(Boolean) : [];
      } else {
        if (!formData.url) {
          setFormError("URL is required for SSE transport");
          setSubmitting(false);
          return;
        }
        payload.url = formData.url;
      }

      // OBSTACK Phase E.2 (out of scope) — server registration
      // (``POST /api/v1/mcp/servers``) is NOT exposed on the shared
      // McpClient yet (E.2 commit 1/2 was intentionally narrow —
      // the UI is the only consumer). Kept as a raw fetch for
      // now; the client surface lands when we have a second
      // caller (Python CLI or web) to share it with.
      const res = await fetch("/api/v1/mcp/servers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(err || `HTTP ${res.status}`);
      }

      setShowForm(false);
      setFormData({ name: "", transport: "stdio", command: "", args: "", url: "" });
      loadServers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="text-muted-foreground text-sm">Loading servers...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-medium">MCP Servers</h2>
        <div className="flex gap-2">
          <button
            onClick={loadServers}
            className="px-3 py-1 text-xs bg-secondary hover:bg-secondary/80 rounded border border-border"
          >
            Refresh
          </button>
          <button
            onClick={() => setShowForm(true)}
            className="px-3 py-1 text-xs bg-primary text-primary-foreground hover:bg-primary/80 rounded"
          >
            + Add Server
          </button>
        </div>
      </div>

      {error && (
        <div className="text-xs text-red-400 mb-3 p-2 rounded bg-red-500/10">
          API error: {error}
        </div>
      )}

      {servers.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p className="text-sm mb-2">No MCP servers configured</p>
          <p className="text-xs">
            Use <strong className="text-foreground">+ Add Server</strong> to register a Stdio or SSE MCP server.
          </p>
          <div className="mt-4 text-left bg-secondary/30 rounded p-3 text-xs font-mono space-y-1 max-w-sm mx-auto">
            <p className="text-muted-foreground mb-2">Example — Stdio server:</p>
            <p>name: filesystem</p>
            <p>command: npx</p>
            <p>args: -y @modelcontextprotocol/server-filesystem /tmp</p>
            <p className="text-muted-foreground mt-2 mb-1">Example — SSE server:</p>
            <p>name: my-sse-server</p>
            <p>transport: sse</p>
            <p>url: http://localhost:8080/sse</p>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          {servers.map((server) => (
            <div
              key={server.id}
              className="rounded-lg p-3 border border-border bg-card flex items-center justify-between"
            >
              <div className="flex items-start gap-3 min-w-0">
                <StatusIcon status={server.runtime_status} />
                <div className="min-w-0">
                  <div className="flex items-center flex-wrap gap-1">
                    <span className="font-medium text-sm">{server.name}</span>
                    <TransportBadge transport={server.transport ?? "stdio"} url={server.url ?? undefined} />
                  </div>
                  {server.transport !== "sse" && (
                    <div className="text-xs text-muted-foreground font-mono truncate mt-0.5">
                      {server.command} {server.args?.join(" ")}
                    </div>
                  )}
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {server.tool_count} tools
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                <button
                  onClick={() => toggleServer(server.id, server.runtime_status)}
                  className="px-2 py-1 text-xs bg-secondary hover:bg-secondary/80 rounded border border-border"
                >
                  {server.runtime_status === "running" ? "Stop" : "Start"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Server Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 w-full max-w-md shadow-xl">
            <h3 className="text-lg font-semibold mb-4">Add MCP Server</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Server Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="my-server"
                  className="w-full px-3 py-2 bg-background border border-border rounded text-sm"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Transport</label>
                <select
                  value={formData.transport}
                  onChange={(e) => setFormData({ ...formData, transport: e.target.value as "stdio" | "sse" })}
                  className="w-full px-3 py-2 bg-background border border-border rounded text-sm"
                >
                  <option value="stdio">Stdio (local process)</option>
                  <option value="sse">SSE (HTTP stream)</option>
                </select>
              </div>

              {formData.transport === "stdio" ? (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1">Command</label>
                    <input
                      type="text"
                      value={formData.command}
                      onChange={(e) => setFormData({ ...formData, command: e.target.value })}
                      placeholder="npx"
                      className="w-full px-3 py-2 bg-background border border-border rounded text-sm font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Arguments (comma-separated)</label>
                    <input
                      type="text"
                      value={formData.args}
                      onChange={(e) => setFormData({ ...formData, args: e.target.value })}
                      placeholder="-y @modelcontextprotocol/server-filesystem /tmp"
                      className="w-full px-3 py-2 bg-background border border-border rounded text-sm font-mono"
                    />
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-medium mb-1">SSE URL</label>
                  <input
                    type="url"
                    value={formData.url}
                    onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                    placeholder="http://localhost:8080/sse"
                    className="w-full px-3 py-2 bg-background border border-border rounded text-sm font-mono"
                  />
                </div>
              )}

              {formError && (
                <div className="text-xs text-red-400 p-2 rounded bg-red-500/10">
                  {formError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false);
                    setFormError(null);
                  }}
                  className="px-4 py-2 text-sm bg-secondary hover:bg-secondary/80 rounded border border-border"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 text-sm bg-primary text-primary-foreground hover:bg-primary/80 rounded disabled:opacity-50"
                >
                  {submitting ? "Adding..." : "Add Server"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
