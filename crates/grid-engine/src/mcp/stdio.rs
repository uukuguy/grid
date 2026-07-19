use std::collections::HashMap;

use anyhow::{Context, Result};
use async_trait::async_trait;
use tokio::io::{AsyncBufReadExt, BufReader};
use tracing::{debug, info, warn};

use rmcp::model::{
    CallToolRequestParams, GetPromptRequestParams, RawContent, ReadResourceRequestParams,
};
use rmcp::service::RunningService;
use rmcp::transport::{ConfigureCommandExt, TokioChildProcess};
use rmcp::{RoleClient, ServiceExt};

use super::convert;
use super::log_entry::LogEntry;
use super::manager::McpManager;
use super::traits::{
    validate_resource_uri, McpClient, McpPromptInfo, McpPromptResult, McpResourceContent,
    McpResourceInfo, McpServerConfig, McpToolInfo,
};

pub struct StdioMcpClient {
    config: McpServerConfig,
    service: Option<RunningService<RoleClient, ()>>,
    /// Phase 3.7.1 Plan 03: optional manager for stderr capture.
    /// Set via `with_log_manager`; when None, stderr is still captured
    /// (D-12) but entries are dropped on the floor.
    /// NOTE: not wired in McpManager::add_server to avoid Arc<Self> cycle.
    /// Callers that want log capture (e.g. S6 integration test, future
    /// CLI refactor) construct the client with `.with_log_manager(arc)`.
    log_manager: Option<std::sync::Arc<tokio::sync::Mutex<McpManager>>>,
}

impl StdioMcpClient {
    pub fn new(config: McpServerConfig) -> Self {
        Self {
            config,
            service: None,
            log_manager: None,
        }
    }

    /// Phase 3.7.1 Plan 03: attach the manager so captured stderr
    /// lines are pushed into the per-server log buffer + broadcast.
    pub fn with_log_manager(
        mut self,
        mgr: std::sync::Arc<tokio::sync::Mutex<McpManager>>,
    ) -> Self {
        self.log_manager = Some(mgr);
        self
    }
}

#[async_trait]
impl McpClient for StdioMcpClient {
    fn name(&self) -> &str {
        &self.config.name
    }

    async fn connect(&mut self) -> Result<()> {
        let config = &self.config;
        info!(
            name = %config.name,
            command = %config.command,
            "Connecting to MCP server"
        );

        let env = config.env.clone();
        let args = config.args.clone();

        // Use builder API to set stderr AFTER TokioChildProcessBuilder construction.
        // IMPORTANT: TokioChildProcessBuilder::new() defaults stderr to Stdio::inherit(),
        // and its spawn() overwrites any stderr set via configure(). We must use the
        // builder's .stderr() method so it takes effect.
        let (transport, stderr_opt) = TokioChildProcess::builder(
            tokio::process::Command::new(&config.command).configure(move |c| {
                for arg in &args {
                    c.arg(arg);
                }
                for (k, v) in &env {
                    c.env(k, v);
                }
            }),
        )
        .stderr(std::process::Stdio::piped())
        .spawn()
        .context("Failed to spawn MCP server process")?;

        // Phase 3.7.1 Plan 03 (D-12): spawn a tokio task to capture stderr
        // lines and push them into the manager's log buffer.
        if let Some(stderr) = stderr_opt {
            let server_name = config.name.clone();
            let log_manager = self.log_manager.clone();
            tokio::spawn(async move {
                let mut reader = BufReader::new(stderr).lines();
                loop {
                    match reader.next_line().await {
                        Ok(Some(line)) => {
                            if let Some(mgr) = log_manager.as_ref() {
                                let mut guard = mgr.lock().await;
                                guard.push_log_entry(&server_name, LogEntry::now(line));
                            }
                            // If no manager attached, drop the line (D-12 fallback).
                        }
                        Ok(None) => break, // EOF: child closed stderr
                        Err(e) => {
                            warn!(
                                server = %server_name,
                                error = %e,
                                "stderr reader failed; stopping log capture"
                            );
                            break;
                        }
                    }
                }
            });
        }

        let service = ()
            .serve(transport)
            .await
            .map_err(|e| anyhow::anyhow!("Failed to initialize MCP connection: {e}"))?;

        let peer_info = service.peer_info();
        info!(
            name = %config.name,
            server = ?peer_info,
            "MCP server connected"
        );

        self.service = Some(service);
        Ok(())
    }

    async fn list_tools(&self) -> Result<Vec<McpToolInfo>> {
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let tools = service
            .list_all_tools()
            .await
            .map_err(|e| anyhow::anyhow!("Failed to list MCP tools: {e}"))?;

        let result: Vec<McpToolInfo> = tools
            .into_iter()
            .map(|t| McpToolInfo {
                name: t.name.to_string(),
                description: t.description.map(|d| d.to_string()),
                input_schema: serde_json::Value::Object(t.input_schema.as_ref().clone()),
                annotations: None,
            })
            .collect();

        debug!(count = result.len(), "Listed MCP tools");
        Ok(result)
    }

    async fn call_tool(&self, name: &str, args: serde_json::Value) -> Result<serde_json::Value> {
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let arguments = args.as_object().cloned();

        let mut params = CallToolRequestParams::new(name.to_string());
        if let Some(args_map) = arguments {
            params = params.with_arguments(args_map);
        }

        let result = service
            .call_tool(params)
            .await
            .map_err(|e| anyhow::anyhow!("Failed to call MCP tool '{name}': {e}"))?;

        // Convert result content to JSON
        let content_strs: Vec<String> = result
            .content
            .into_iter()
            .filter_map(|c| match &c.raw {
                RawContent::Text(text) => Some(text.text.clone()),
                _ => None,
            })
            .collect();

        Ok(serde_json::json!({
            "content": content_strs.join("\n"),
            "isError": result.is_error.unwrap_or(false),
        }))
    }

    fn is_connected(&self) -> bool {
        self.service.is_some()
    }

    async fn shutdown(&mut self) -> Result<()> {
        if let Some(service) = self.service.take() {
            info!(name = %self.config.name, "Shutting down MCP server");
            service
                .cancel()
                .await
                .map_err(|e| anyhow::anyhow!("Failed to cancel MCP service: {e}"))?;
        }
        Ok(())
    }

    async fn list_resources(&self) -> Result<Vec<McpResourceInfo>> {
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let resources = match service.list_all_resources().await {
            Ok(r) => r,
            Err(e) => {
                warn!(name = %self.config.name, error = %e, "Server does not support resources or list failed");
                return Ok(vec![]);
            }
        };

        let result = convert::map_resources(resources);
        debug!(count = result.len(), "Listed MCP resources");
        Ok(result)
    }

    async fn read_resource(&self, uri: &str) -> Result<McpResourceContent> {
        validate_resource_uri(uri)?;
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let result = service
            .read_resource(ReadResourceRequestParams::new(uri.to_string()))
            .await
            .map_err(|e| anyhow::anyhow!("Failed to read MCP resource '{uri}': {e}"))?;

        Ok(convert::map_resource_content(result.contents, uri))
    }

    async fn list_prompts(&self) -> Result<Vec<McpPromptInfo>> {
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let prompts = match service.list_all_prompts().await {
            Ok(p) => p,
            Err(e) => {
                warn!(name = %self.config.name, error = %e, "Server does not support prompts or list failed");
                return Ok(vec![]);
            }
        };

        let result = convert::map_prompts(prompts);
        debug!(count = result.len(), "Listed MCP prompts");
        Ok(result)
    }

    async fn get_prompt(
        &self,
        name: &str,
        args: HashMap<String, String>,
    ) -> Result<McpPromptResult> {
        let service = self
            .service
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("MCP client not connected"))?;

        let arguments: Option<serde_json::Map<String, serde_json::Value>> = if args.is_empty() {
            None
        } else {
            Some(
                args.into_iter()
                    .map(|(k, v)| (k, serde_json::Value::String(v)))
                    .collect(),
            )
        };

        let mut params = GetPromptRequestParams::new(name.to_string());
        if let Some(args_map) = arguments {
            params = params.with_arguments(args_map);
        }

        let result = service
            .get_prompt(params)
            .await
            .map_err(|e| anyhow::anyhow!("Failed to get MCP prompt '{name}': {e}"))?;

        Ok(convert::map_prompt_result(result))
    }
}
