//! Run command — start interactive REPL session

use anyhow::Result;

use crate::commands::AppState;

/// Options for the run command
pub struct RunOptions {
    pub resume: bool,
    pub session_id: Option<String>,
    pub agent_id: Option<String>,
    pub theme: String,
    /// Additional directories to include as context
    pub add_dirs: Vec<String>,
    /// Enable dual agent mode (Plan + Build)
    pub dual: bool,
    /// Parallel mode: launch N agents concurrently (S5 batch scenario, REQ-AUDIT-02)
    pub parallel: Option<usize>,
}

/// Execute the run command: start an interactive REPL session, OR launch N parallel
/// agents if `opts.parallel` is set (per Phase 3.7.1 D-01 S5 acceptance).
pub async fn execute_run(opts: RunOptions, state: &AppState) -> Result<()> {
    if let Some(n) = opts.parallel {
        run_parallel(n, &opts, state).await
    } else {
        crate::repl::run_repl(state, &opts).await
    }
}

/// Launch N parallel agents, each running a single ask with a prompt derived from
/// the agent_id or a default "Summarize the README.md" template.
async fn run_parallel(n: usize, opts: &RunOptions, state: &AppState) -> Result<()> {
    use crate::commands::ask::AskOptions;
    use crate::commands::execute_ask;
    println!("Launching {} parallel agents...", n);
    let state = state.clone(); // Clone AppState so it can move into each spawn
    let mut handles = Vec::new();
    for i in 0..n {
        let prompt = format!(
            "Summarize the README.md file (parallel agent #{}/{})",
            i + 1,
            n
        );
        let agent_id = opts.agent_id.clone();
        let session_id = opts.session_id.clone();
        let state = state.clone();
        handles.push(tokio::spawn(async move {
            execute_ask(
                AskOptions {
                    message: prompt,
                    session_id,
                    agent_id,
                },
                &state,
            )
            .await
        }));
    }
    let mut success = 0;
    let mut failed = 0;
    for h in handles {
        match h.await {
            Ok(Ok(())) => success += 1,
            _ => failed += 1,
        }
    }
    println!(
        "\nParallel summary: {} succeeded, {} failed (total {})",
        success, failed, n
    );
    if failed > 0 {
        anyhow::bail!("{} of {} parallel agents failed", failed, n);
    }
    Ok(())
}
