//! MCP server management commands — list/add/remove/status/logs via McpManager

use crate::commands::{AppState, McpCommands};
use crate::output::{self, TextOutput};
use crate::ui::table::Table;
use anyhow::Result;
use serde::Serialize;
use std::collections::HashMap;

/// Handle MCP commands
pub async fn handle_mcp(action: McpCommands, state: &AppState) -> Result<()> {
    match action {
        McpCommands::List => list_servers(state).await?,
        McpCommands::Add {
            name,
            command,
            args,
            env_vars,
        } => add_server(name, command, args, env_vars, state).await?,
        McpCommands::Remove { name } => remove_server(name, state).await?,
        McpCommands::Status { name } => show_status(name, state).await?,
        McpCommands::Logs {
            name,
            lines,
            follow,
            level,
            output,
        } => show_logs(name, lines, follow, level, output, state).await?,
    }
    Ok(())
}

// ── Output types ──────────────────────────────────────────────

#[derive(Serialize)]
struct McpListOutput {
    servers: Vec<McpServerRow>,
}

#[derive(Serialize)]
struct McpServerRow {
    name: String,
    status: String,
    tools: usize,
}

impl TextOutput for McpListOutput {
    fn to_text(&self) -> String {
        if self.servers.is_empty() {
            return "No MCP servers configured.".to_string();
        }
        let mut t = Table::new(vec!["Name", "Status", "Tools"]);
        for s in &self.servers {
            t.add_row(vec![
                s.name.clone(),
                s.status.clone(),
                s.tools.to_string(),
            ]);
        }
        format!("{} MCP server(s):\n\n{}", self.servers.len(), t.render())
    }
}

#[derive(Serialize)]
struct McpAddOutput {
    name: String,
    tools_count: usize,
    tool_names: Vec<String>,
}

impl TextOutput for McpAddOutput {
    fn to_text(&self) -> String {
        let mut out = format!(
            "Added MCP server '{}' ({} tools)\n",
            self.name, self.tools_count
        );
        for name in &self.tool_names {
            out.push_str(&format!("  - {}\n", name));
        }
        out
    }
}

#[derive(Serialize)]
struct McpRemoveOutput {
    name: String,
}

impl TextOutput for McpRemoveOutput {
    fn to_text(&self) -> String {
        format!("Removed MCP server '{}'", self.name)
    }
}

#[derive(Serialize)]
struct McpStatusOutput {
    servers: Vec<McpStatusRow>,
}

#[derive(Serialize)]
struct McpStatusRow {
    name: String,
    state: String,
    tools: Vec<String>,
}

impl TextOutput for McpStatusOutput {
    fn to_text(&self) -> String {
        if self.servers.is_empty() {
            return "No MCP servers found.".to_string();
        }
        let mut out = String::new();
        for s in &self.servers {
            out.push_str(&format!("{} [{}]\n", s.name, s.state));
            for t in &s.tools {
                out.push_str(&format!("  - {}\n", t));
            }
        }
        out
    }
}

// Phase 3.7.1 Plan 03: per-line log entry output (text + JSON).
// Per-line emission is required for --follow streaming; the previous
// McpLogsOutput was a single-message wrapper, insufficient.

fn format_log_entry_text(entry: &grid_engine::mcp::LogEntry) -> String {
    format!(
        "{} [{}] {}",
        entry.timestamp.to_rfc3339(),
        match entry.level {
            grid_engine::mcp::LogLevel::Info => "INFO ",
            grid_engine::mcp::LogLevel::Warn => "WARN ",
            grid_engine::mcp::LogLevel::Error => "ERROR",
        },
        entry.message,
    )
}

fn format_log_entry_json(entry: &grid_engine::mcp::LogEntry) -> String {
    serde_json::json!({
        "timestamp": entry.timestamp.to_rfc3339(),
        "level": match entry.level {
            grid_engine::mcp::LogLevel::Info => "info",
            grid_engine::mcp::LogLevel::Warn => "warn",
            grid_engine::mcp::LogLevel::Error => "error",
        },
        "message": entry.message,
    })
    .to_string()
}

/// D-14: text default; JSON when --output json OR stdout is not a TTY.
fn resolve_output_format(explicit: Option<&str>) -> &'static str {
    match explicit {
        Some("json") => "json",
        Some("text") => "text",
        _ => {
            if std::io::IsTerminal::is_terminal(&std::io::stdout()) {
                "text"
            } else {
                "json"
            }
        }
    }
}

/// D-13: parse --level value to a LogLevel filter; None = all levels.
fn parse_level_filter(value: Option<&str>) -> Option<grid_engine::mcp::LogLevel> {
    match value.map(str::to_ascii_lowercase).as_deref() {
        Some("info") => Some(grid_engine::mcp::LogLevel::Info),
        Some("warn") => Some(grid_engine::mcp::LogLevel::Warn),
        Some("error") => Some(grid_engine::mcp::LogLevel::Error),
        _ => None,
    }
}

// ── Handlers ──────────────────────────────────────────────────

async fn list_servers(state: &AppState) -> Result<()> {
    let mgr = state.agent_runtime.mcp_manager();
    let guard = mgr.lock().await;
    let states = guard.all_runtime_states();
    let servers: Vec<McpServerRow> = states
        .iter()
        .map(|(name, runtime_state)| {
            let status = format!("{:?}", runtime_state);
            let tools = guard.get_tool_count(name);
            McpServerRow {
                name: name.clone(),
                status,
                tools,
            }
        })
        .collect();
    drop(guard);

    let out = McpListOutput { servers };
    output::print_output(&out, &state.output_config);
    Ok(())
}

async fn add_server(
    name: String,
    command: String,
    args: Vec<String>,
    env_vars: Vec<String>,
    state: &AppState,
) -> Result<()> {
    use grid_engine::mcp::{McpManager, McpServerConfig};

    // Parse KEY=VALUE env vars
    let mut env = HashMap::new();
    for kv in &env_vars {
        if let Some((key, value)) = kv.split_once('=') {
            env.insert(key.to_string(), value.to_string());
        } else {
            anyhow::bail!("Invalid env var format '{}', expected KEY=VALUE", kv);
        }
    }

    let config = McpServerConfig {
        name: name.clone(),
        command,
        args,
        env,
        auto_start: true,
    };

    // Persist to .grid/mcp.json
    let config_path = state.grid_root.project_root().join("mcp.json");
    McpManager::add_to_config_file(&config_path, &config)?;

    // Connect the server at runtime
    let mgr = state.agent_runtime.mcp_manager();
    let mut guard = mgr.lock().await;
    let tools = guard.add_server(config).await?;

    let out = McpAddOutput {
        name,
        tools_count: tools.len(),
        tool_names: tools.iter().map(|t| t.name.clone()).collect(),
    };
    drop(guard);
    output::print_output(&out, &state.output_config);
    Ok(())
}

async fn remove_server(name: String, state: &AppState) -> Result<()> {
    use grid_engine::mcp::McpManager;

    // Remove from runtime
    let mgr = state.agent_runtime.mcp_manager();
    let mut guard = mgr.lock().await;
    guard.remove_server(&name).await?;
    drop(guard);

    // Remove from config file
    let config_path = state.grid_root.project_root().join("mcp.json");
    McpManager::remove_from_config_file(&config_path, &name)?;

    let out = McpRemoveOutput { name };
    output::print_output(&out, &state.output_config);
    Ok(())
}

async fn show_status(name: Option<String>, state: &AppState) -> Result<()> {
    let mgr = state.agent_runtime.mcp_manager();
    let guard = mgr.lock().await;
    let all_states = guard.all_runtime_states();

    let servers: Vec<McpStatusRow> = match name {
        Some(ref n) => {
            let state_val = guard.get_runtime_state(n);
            let tools = guard
                .get_tool_infos(n)
                .unwrap_or_default()
                .iter()
                .map(|t| t.name.clone())
                .collect();
            vec![McpStatusRow {
                name: n.clone(),
                state: format!("{:?}", state_val),
                tools,
            }]
        }
        None => all_states
            .keys()
            .map(|n| {
                let state_val = guard.get_runtime_state(n);
                let tools = guard
                    .get_tool_infos(n)
                    .unwrap_or_default()
                    .iter()
                    .map(|t| t.name.clone())
                    .collect();
                McpStatusRow {
                    name: n.clone(),
                    state: format!("{:?}", state_val),
                    tools,
                }
            })
            .collect(),
    };
    drop(guard);

    let out = McpStatusOutput { servers };
    output::print_output(&out, &state.output_config);
    Ok(())
}

async fn show_logs(
    name: String,
    lines: usize,
    follow: bool,
    level: Option<String>,
    output: Option<String>,
    state: &AppState,
) -> Result<()> {
    let format = resolve_output_format(output.as_deref());
    let level_filter = parse_level_filter(level.as_deref());

    let mgr = state.agent_runtime.mcp_manager();
    let mut stdout = std::io::stdout().lock();

    if follow {
        // ── Follow mode (D-13 push path) ──
        // The buffer must exist before subscribe; if no log line
        // has been captured yet, subscribe would panic. Create a
        // placeholder entry to materialize the buffer.
        {
            let mut guard = mgr.lock().await;
            if !guard.has_log_buffer(&name) {
                guard.push_log_entry(
                    &name,
                    grid_engine::mcp::LogEntry::now(String::new()),
                );
            }
        }
        let mut rx = {
            let guard = mgr.lock().await;
            guard.subscribe_logs(&name)
        };
        // Ctrl-C handler: tokio::signal::ctrl_c breaks the loop and
        // returns Ok(()) so exit code is 0 (D-13 "clean exit").
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                return Ok(());
            }
            _ = async {
                while let Ok(entry) = rx.recv().await {
                    // Skip the placeholder empty-message entries.
                    if entry.message.is_empty() {
                        continue;
                    }
                    if let Some(filter) = level_filter {
                        if entry.level != filter {
                            continue;
                        }
                    }
                    let line = match format {
                        "json" => format_log_entry_json(&entry),
                        _ => format_log_entry_text(&entry),
                    };
                    use std::io::Write;
                    let _ = writeln!(stdout, "{}", line);
                    let _ = stdout.flush();
                }
            } => {}
        }
        Ok(())
    } else {
        // ── Pull mode (D-10 take_recent_logs) ──
        let entries = {
            let guard = mgr.lock().await;
            guard.take_recent_logs(&name, lines)
        };
        if entries.is_empty() {
            // Fall back to status info if buffer is empty (e.g. user
            // asked for logs on a server that was never connected
            // or hasn't emitted anything yet).
            let state_val = {
                let guard = mgr.lock().await;
                guard.get_runtime_state(&name)
            };
            eprintln!(
                "{}: no log entries yet (server state: {:?}). Use --follow to wait for new lines.",
                name, state_val
            );
            return Ok(());
        }
        use std::io::Write;
        for entry in entries {
            if let Some(filter) = level_filter {
                if entry.level != filter {
                    continue;
                }
            }
            let line = match format {
                "json" => format_log_entry_json(&entry),
                _ => format_log_entry_text(&entry),
            };
            let _ = writeln!(stdout, "{}", line);
        }
        let _ = stdout.flush();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mcp_list_empty() {
        let out = McpListOutput { servers: vec![] };
        assert!(out.to_text().contains("No MCP servers"));
    }

    #[test]
    fn test_mcp_list_with_servers() {
        let out = McpListOutput {
            servers: vec![McpServerRow {
                name: "test-server".to_string(),
                status: "Running".to_string(),
                tools: 3,
            }],
        };
        let text = out.to_text();
        assert!(text.contains("test-server"));
        assert!(text.contains("1 MCP"));
    }

    #[test]
    fn test_mcp_add_output() {
        let out = McpAddOutput {
            name: "my-server".to_string(),
            tools_count: 2,
            tool_names: vec!["tool_a".to_string(), "tool_b".to_string()],
        };
        let text = out.to_text();
        assert!(text.contains("my-server"));
        assert!(text.contains("2 tools"));
        assert!(text.contains("tool_a"));
    }

    #[test]
    fn test_mcp_remove_output() {
        let out = McpRemoveOutput {
            name: "old-server".to_string(),
        };
        assert!(out.to_text().contains("Removed"));
    }

    #[test]
    fn test_mcp_status_empty() {
        let out = McpStatusOutput { servers: vec![] };
        assert!(out.to_text().contains("No MCP servers"));
    }

    #[test]
    fn test_mcp_status_with_server() {
        let out = McpStatusOutput {
            servers: vec![McpStatusRow {
                name: "srv".to_string(),
                state: "Running".to_string(),
                tools: vec!["t1".to_string()],
            }],
        };
        let text = out.to_text();
        assert!(text.contains("srv"));
        assert!(text.contains("Running"));
        assert!(text.contains("t1"));
    }

    #[test]
    fn test_format_log_entry_text_and_json() {
        let entry = grid_engine::mcp::LogEntry {
            timestamp: chrono::DateTime::parse_from_rfc3339("2026-07-20T10:23:45Z")
                .unwrap()
                .with_timezone(&chrono::Utc),
            level: grid_engine::mcp::LogLevel::Info,
            message: "Server started".to_string(),
        };
        let text = format_log_entry_text(&entry);
        assert!(text.contains("2026-07-20T10:23:45"));
        assert!(text.contains("INFO"));
        assert!(text.contains("Server started"));
        let json = format_log_entry_json(&entry);
        assert!(json.contains("\"level\":\"info\""));
        assert!(json.contains("\"message\":\"Server started\""));
    }

    #[test]
    fn test_resolve_output_format() {
        assert_eq!(resolve_output_format(Some("json")), "json");
        assert_eq!(resolve_output_format(Some("text")), "text");
        // When explicit is None, the result depends on TTY status; just
        // confirm it returns one of the two valid values.
        let auto = resolve_output_format(None);
        assert!(auto == "text" || auto == "json");
    }

    #[test]
    fn test_parse_level_filter() {
        assert_eq!(
            parse_level_filter(Some("info")),
            Some(grid_engine::mcp::LogLevel::Info)
        );
        assert_eq!(
            parse_level_filter(Some("WARN")),
            Some(grid_engine::mcp::LogLevel::Warn)
        );
        assert_eq!(
            parse_level_filter(Some("Error")),
            Some(grid_engine::mcp::LogLevel::Error)
        );
        assert_eq!(parse_level_filter(None), None);
    }
}
