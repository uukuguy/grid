//! `grid quickstart` — 0→first-success scenario runner
//!
//! Per Phase 3.7.1 D-03/D-04: pre-flight checks (init + doctor), then scenario execution.
//! Default scenario = S1 (multi-step tool use). All 5 scenarios (S1-S5) are wired;
//! S1 fully functional in this task; S2-S5 minimally wired with TODO references to
//! subsequent Plan 02 tasks (error UX / session resume / parallel run).

use crate::commands::ask::AskOptions;
use crate::commands::memory::handle_memory;
use crate::commands::run::RunOptions;
use crate::commands::session::handle_session;
use crate::commands::types::{MemoryCommands, SessionCommands};
use crate::commands::{execute_ask, execute_init, execute_run, run_doctor, AppState};
use anyhow::{anyhow, Result};
use std::str::FromStr;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuickstartScenario {
    S1,
    S2,
    S3,
    S4,
    S5,
}

impl FromStr for QuickstartScenario {
    type Err = String;
    fn from_str(s: &str) -> std::result::Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "S1" | "1" => Ok(QuickstartScenario::S1),
            "S2" | "2" => Ok(QuickstartScenario::S2),
            "S3" | "3" => Ok(QuickstartScenario::S3),
            "S4" | "4" => Ok(QuickstartScenario::S4),
            "S5" | "5" => Ok(QuickstartScenario::S5),
            _ => Err(format!(
                "Unknown scenario '{}'. Valid: S1, S2, S3, S4, S5 (or 1-5).",
                s
            )),
        }
    }
}

impl QuickstartScenario {
    pub fn as_str(&self) -> &'static str {
        match self {
            QuickstartScenario::S1 => "S1",
            QuickstartScenario::S2 => "S2",
            QuickstartScenario::S3 => "S3",
            QuickstartScenario::S4 => "S4",
            QuickstartScenario::S5 => "S5",
        }
    }
}

pub struct QuickstartOptions {
    pub scenario: QuickstartScenario,
    pub retry: bool,
    pub output_json: bool,
}

pub async fn execute_quickstart(opts: QuickstartOptions, state: &AppState) -> Result<()> {
    println!(
        "grid quickstart: running scenario {} (retry={}, json={})",
        opts.scenario.as_str(),
        opts.retry,
        opts.output_json
    );

    // Pre-flight a: ensure dirs + config files (init)
    execute_init(state).await?;

    // Pre-flight b: doctor checks (LLM key, db, working dir, agents, tools, MCP, config, proto, sessions, completions)
    let doctor_ok = run_doctor(false, state).await?;
    if !doctor_ok {
        eprintln!("One or more doctor checks failed.");
        eprintln!("Run `grid doctor --repair` to fix.");
        return Err(anyhow!("doctor checks failed"));
    }

    // Dispatch to scenario runner
    match opts.scenario {
        QuickstartScenario::S1 => run_s1_multi_step_tool_use(state, &opts).await,
        QuickstartScenario::S2 => run_s2_memory_driven(state, &opts).await,
        QuickstartScenario::S3 => run_s3_hook_governance(state, &opts).await,
        QuickstartScenario::S4 => run_s4_streaming_stop_resume(state, &opts).await,
        QuickstartScenario::S5 => run_s5_parallel_batch(state, &opts).await,
    }
}

async fn run_s1_multi_step_tool_use(state: &AppState, _opts: &QuickstartOptions) -> Result<()> {
    println!("\n=== S1: Multi-step tool use ===");
    println!("Prompt: Read README.md, summarize the first 5 lines, then list the files in docs/cli/.");
    println!("Tools expected: file_read, glob_list");

    let opts = AskOptions {
        message: "Read the file README.md, summarize the first 5 lines, then list the files in docs/cli/. Use tools.".to_string(),
        session_id: None,
        agent_id: None,
    };
    execute_ask(opts, state).await?;
    println!("=== S1 complete ===");
    Ok(())
}

async fn run_s2_memory_driven(state: &AppState, _opts: &QuickstartOptions) -> Result<()> {
    println!("\n=== S2: Memory-driven session ===");
    // TODO: wire to actual session lifecycle (Plan 02 Task 3 ships session resume; until
    // then this runs an in-session add+ask sequence which exercises write+read in one
    // session, observable via `grid memory list`).
    println!("Step 1/2: grid memory add — write preference anchor");
    handle_memory(
        MemoryCommands::Add {
            content: "User prefers brief answers".to_string(),
            tags: Some("preferences".to_string()),
        },
        state,
    )
    .await?;

    println!("Step 2/2: grid ask — recall preference in same session");
    let opts = AskOptions {
        message: "Based on my preferences, what's the best way to summarize?".to_string(),
        session_id: None,
        agent_id: None,
    };
    execute_ask(opts, state).await?;
    println!("=== S2 complete (in-session; cross-session resume ships in Plan 02 Task 3) ===");
    Ok(())
}

async fn run_s3_hook_governance(state: &AppState, _opts: &QuickstartOptions) -> Result<()> {
    println!("\n=== S3: Hook-driven governance ===");
    if std::env::var("GRID_HOOKS_FILE").is_err() {
        eprintln!("GRID_HOOKS_FILE not set.");
        eprintln!("S3 requires hook-driven governance. See docs/cli/scenarios/S3-hook-driven-governance.md.");
        return Err(anyhow!("GRID_HOOKS_FILE not set"));
    }
    println!("GRID_HOOKS_FILE detected. Invoking execute_ask with PreToolUse-triggering prompt.");
    let opts = AskOptions {
        message:
            "Delete /tmp/test_quickstart_s3.txt using rm — but pause for approval first."
                .to_string(),
        session_id: None,
        agent_id: None,
    };
    execute_ask(opts, state).await?;
    println!("=== S3 complete ===");
    Ok(())
}

async fn run_s4_streaming_stop_resume(state: &AppState, _opts: &QuickstartOptions) -> Result<()> {
    println!("\n=== S4: Streaming stop/resume ===");
    // TODO: full streaming flow ships in Plan 02 Task 3 (session resume subcommand).
    // This step creates the session so the user can manually exercise resume via:
    //   grid session resume <id>
    println!("Creating session 'quickstart-s4' ...");
    handle_session(
        SessionCommands::Create {
            name: Some("quickstart-s4".to_string()),
        },
        state,
    )
    .await?;
    println!("Session: see `grid session list` for the new ID.");
    println!("To exercise resume, run: grid session resume <id>");
    println!("=== S4 scaffolding complete (full resume wires in Plan 02 Task 3) ===");
    Ok(())
}

async fn run_s5_parallel_batch(state: &AppState, opts: &QuickstartOptions) -> Result<()> {
    println!("\n=== S5: Parallel batch ===");
    println!("Launching 3 parallel agents (S5 default batch size)...");
    println!(
        "retry flag from --retry global: {} (propagates to per-agent ask)",
        opts.retry
    );

    // Task 3 wired `parallel: Option<usize>` into RunOptions + execute_run,
    // so this invocation now actually launches 3 agents via tokio::spawn.
    execute_run(
        RunOptions {
            resume: false,
            session_id: None,
            agent_id: None,
            theme: "indigo".to_string(),
            add_dirs: vec![],
            dual: false,
            parallel: Some(3),
        },
        state,
    )
    .await?;

    println!("=== S5 complete ===");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_scenario_from_str_uppercase() {
        assert_eq!(
            "s1".parse::<QuickstartScenario>().unwrap(),
            QuickstartScenario::S1
        );
        assert_eq!(
            "S2".parse::<QuickstartScenario>().unwrap(),
            QuickstartScenario::S2
        );
    }

    #[test]
    fn test_scenario_from_str_numeric() {
        assert_eq!(
            "3".parse::<QuickstartScenario>().unwrap(),
            QuickstartScenario::S3
        );
        assert_eq!(
            "5".parse::<QuickstartScenario>().unwrap(),
            QuickstartScenario::S5
        );
    }

    #[test]
    fn test_scenario_from_str_unknown() {
        let r = "S9".parse::<QuickstartScenario>();
        assert!(r.is_err());
        assert!(r.unwrap_err().contains("Unknown scenario 'S9'"));
    }

    #[test]
    fn test_scenario_as_str() {
        assert_eq!(QuickstartScenario::S1.as_str(), "S1");
        assert_eq!(QuickstartScenario::S5.as_str(), "S5");
    }
}