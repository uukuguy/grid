//! ChunkType-native WS envelope mapper (Phase 5.4 D-03/D-04).
//!
//! Maps `grid_engine::AgentEvent` to either:
//! - a ChunkType wire envelope `{type:"chunk", session_id, chunk_type:<1-9>, payload:{...}}`
//!   (model output — wire values per `proto/eaasp/runtime/v2/common.proto:131-142`,
//!   contract-v1.2.0 locked in Phase 5.3)
//! - or a server-protocol control message `{type:"<control_name>", session_id, ...}`
//!   (lifecycle / meta — not part of ChunkType per D-04)
//!
//! Wire matrix per PATTERNS.md §B2 + RESEARCH §4 Q2:
//!
//! | AgentEvent variant                  | Wire shape                                   |
//! |-------------------------------------|----------------------------------------------|
//! | TextDelta { text }                  | chunk wire 1 (TEXT_DELTA)                    |
//! | TextComplete { text }               | chunk wire 5 (DONE — per-turn text close)    |
//! | ThinkingDelta { text }              | chunk wire 2 (THINKING)                      |
//! | ThinkingComplete { text }           | chunk wire 8 (THINKING_TRACE — end-of-turn)  |
//! | ToolStart { tool_id, name, input }  | chunk wire 3 (TOOL_START)                    |
//! | ToolResult { tool_id, output, ok }  | chunk wire 4 (TOOL_RESULT)                   |
//! | Error { message } (mid-turn)        | chunk wire 6 (ERROR)                         |
//! | WorkflowContinuation { attempt }    | chunk wire 7 (WORKFLOW_CONTINUATION)         |
//! | Done | Completed(_)                 | control type="done"                          |
//! | ApprovalRequired { tool_*, risk }   | control type="approval_required"             |
//! | InteractionRequested { req_id, .. } | control type="interaction_requested"         |
//! | MemoryFlushed { facts_count }       | control type="memory_flushed"                |
//! | ContextDegraded { level, pct }      | control type="context_degraded"              |
//! | SecurityBlocked { reason }          | control type="security_blocked"              |
//! | RetryingMalformedToolCall { .. }    | control type="retrying_malformed_tool_call"  |
//! | TokenBudgetUpdate { budget }        | control type="token_budget_update"           |
//! | Typing { state }                    | control type="typing"                        |
//! | Autonomous* (5 variants)            | control type="autonomous_*"                  |
//! | ToolExecution { execution }         | control type="tool_execution" (legacy)       |
//! | IterationStart / IterationEnd /     | None (internal — handle_socket continues)    |
//! | PlanUpdate / SubAgentEvent / etc.   |                                              |
//!
//! WORKFLOW_CONTINUATION (wire 7), THINKING_TRACE (wire 8), ATTACHMENT_REF (wire 9)
//! are wired forward-compatibly per RESEARCH §6 R8 — even when current AgentEvent
//! emitters do not yet produce them, the mapper is ready.

use serde::Serialize;
use serde_json::json;

use grid_engine::AgentEvent;

#[derive(Serialize, Debug)]
#[serde(untagged)]
pub enum WsServerMessage {
    Chunk(ChunkEnvelope),
    Control(ControlMessage),
}

#[derive(Serialize, Debug)]
pub struct ChunkEnvelope {
    #[serde(rename = "type")]
    pub kind: &'static str, // always "chunk"
    pub session_id: String,
    /// ChunkType wire integer 1-9, per `proto/eaasp/runtime/v2/common.proto:131-142`
    /// (contract-v1.2.0 locked in Phase 5.3).
    pub chunk_type: u32,
    pub payload: serde_json::Value,
}

#[derive(Serialize, Debug)]
#[serde(tag = "type")]
#[serde(rename_all = "snake_case")]
pub enum ControlMessage {
    SessionCreated {
        session_id: String,
    },
    Done {
        session_id: String,
    },
    /// Session-level error (not model error mid-stream — that goes to chunk wire 6).
    Error {
        session_id: String,
        message: String,
    },
    ApprovalRequired {
        session_id: String,
        tool_name: String,
        tool_id: String,
        risk_level: String,
    },
    InteractionRequested {
        session_id: String,
        request_id: String,
        request: serde_json::Value,
    },
    MemoryFlushed {
        session_id: String,
        facts_count: u32,
    },
    ContextDegraded {
        session_id: String,
        level: String,
        usage_pct: f32,
    },
    SecurityBlocked {
        session_id: String,
        reason: String,
    },
    RetryingMalformedToolCall {
        session_id: String,
        attempt: u32,
        max_attempts: u32,
        reason: String,
    },
    SessionUpdate {
        session_id: String,
        event_type: String,
    },
    TokenBudgetUpdate {
        session_id: String,
        budget: serde_json::Value,
    },
    Typing {
        session_id: String,
        state: bool,
    },
    ToolExecution {
        session_id: String,
        execution: serde_json::Value,
    },
    AutonomousSleeping {
        session_id: String,
        duration_secs: u64,
    },
    AutonomousTick {
        session_id: String,
        round: u32,
    },
    AutonomousPaused {
        session_id: String,
    },
    AutonomousResumed {
        session_id: String,
    },
    AutonomousExhausted {
        session_id: String,
        reason: String,
    },
}

/// Build a chunk envelope (helper).
fn chunk(sid: &str, ct: u32, payload: serde_json::Value) -> WsServerMessage {
    WsServerMessage::Chunk(ChunkEnvelope {
        kind: "chunk",
        session_id: sid.to_string(),
        chunk_type: ct,
        payload,
    })
}

/// Map an `AgentEvent` to a `WsServerMessage`. Returns `None` for internal
/// events (IterationStart/End, PlanUpdate, SubAgentEvent, CostUpdate, etc.)
/// that the WS loop should skip — preserves the original `_ => continue`
/// semantics from `ws.rs:467`.
pub fn map_event(sid: &str, ev: AgentEvent) -> Option<WsServerMessage> {
    let sid_owned = sid.to_string();
    let msg = match ev {
        // === Model output: ChunkType wire 1-9 (chunk envelope) ===
        AgentEvent::TextDelta { text } => chunk(sid, 1, json!({ "text": text })),
        AgentEvent::ThinkingDelta { text } => chunk(sid, 2, json!({ "text": text })),
        AgentEvent::ToolStart {
            tool_id,
            tool_name,
            input,
        } => chunk(
            sid,
            3,
            json!({"tool_id": tool_id, "tool_name": tool_name, "input": input}),
        ),
        AgentEvent::ToolResult {
            tool_id,
            tool_name,
            output,
            success,
        } => chunk(
            sid,
            4,
            json!({"tool_id": tool_id, "tool_name": tool_name, "output": output, "success": success}),
        ),
        AgentEvent::TextComplete { text } => chunk(sid, 5, json!({ "text": text })),
        AgentEvent::Error { message } => chunk(sid, 6, json!({ "message": message })),
        AgentEvent::WorkflowContinuation {
            attempt,
            max_attempts,
        } => chunk(
            sid,
            7,
            json!({"attempt": attempt, "max_attempts": max_attempts}),
        ),
        AgentEvent::ThinkingComplete { text } => chunk(sid, 8, json!({ "text": text })),
        // wire 9 (ATTACHMENT_REF) — mapper stub for forward compatibility per R8.
        // No current AgentEvent variant emits it; left absent here so the
        // exhaustive match below stays correct. When an emitter lands,
        // add a match arm chunk(sid, 9, ...).

        // === Server-protocol control messages ===
        AgentEvent::Done | AgentEvent::Completed(_) => {
            WsServerMessage::Control(ControlMessage::Done {
                session_id: sid_owned,
            })
        }
        AgentEvent::ApprovalRequired {
            tool_name,
            tool_id,
            risk_level,
        } => WsServerMessage::Control(ControlMessage::ApprovalRequired {
            session_id: sid_owned,
            tool_name,
            tool_id,
            risk_level: format!("{:?}", risk_level).to_lowercase(),
        }),
        AgentEvent::InteractionRequested {
            request_id,
            request,
        } => WsServerMessage::Control(ControlMessage::InteractionRequested {
            session_id: sid_owned,
            request_id,
            request: serde_json::to_value(request).unwrap_or(serde_json::Value::Null),
        }),
        AgentEvent::MemoryFlushed { facts_count } => {
            WsServerMessage::Control(ControlMessage::MemoryFlushed {
                session_id: sid_owned,
                facts_count: facts_count as u32,
            })
        }
        AgentEvent::ContextDegraded { level, usage_pct } => {
            WsServerMessage::Control(ControlMessage::ContextDegraded {
                session_id: sid_owned,
                level,
                usage_pct,
            })
        }
        AgentEvent::SecurityBlocked { reason } => {
            WsServerMessage::Control(ControlMessage::SecurityBlocked {
                session_id: sid_owned,
                reason,
            })
        }
        AgentEvent::RetryingMalformedToolCall {
            attempt,
            max_attempts,
            reason,
        } => WsServerMessage::Control(ControlMessage::RetryingMalformedToolCall {
            session_id: sid_owned,
            attempt,
            max_attempts,
            reason,
        }),
        AgentEvent::TokenBudgetUpdate { budget } => {
            WsServerMessage::Control(ControlMessage::TokenBudgetUpdate {
                session_id: sid_owned,
                budget: serde_json::to_value(budget).unwrap_or(serde_json::Value::Null),
            })
        }
        AgentEvent::Typing { state } => WsServerMessage::Control(ControlMessage::Typing {
            session_id: sid_owned,
            state,
        }),
        AgentEvent::ToolExecution { execution } => {
            WsServerMessage::Control(ControlMessage::ToolExecution {
                session_id: sid_owned,
                execution: serde_json::to_value(execution).unwrap_or(serde_json::Value::Null),
            })
        }
        AgentEvent::AutonomousSleeping { duration_secs } => {
            WsServerMessage::Control(ControlMessage::AutonomousSleeping {
                session_id: sid_owned,
                duration_secs,
            })
        }
        AgentEvent::AutonomousTick { round } => {
            WsServerMessage::Control(ControlMessage::AutonomousTick {
                session_id: sid_owned,
                round,
            })
        }
        AgentEvent::AutonomousPaused => {
            WsServerMessage::Control(ControlMessage::AutonomousPaused {
                session_id: sid_owned,
            })
        }
        AgentEvent::AutonomousResumed => {
            WsServerMessage::Control(ControlMessage::AutonomousResumed {
                session_id: sid_owned,
            })
        }
        AgentEvent::AutonomousExhausted { reason } => {
            WsServerMessage::Control(ControlMessage::AutonomousExhausted {
                session_id: sid_owned,
                reason,
            })
        }

        // Internal / not-for-WS — preserve existing `_ => continue` semantics.
        _ => return None,
    };
    Some(msg)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_text_delta_to_chunk_1() {
        let m = map_event("sid-1", AgentEvent::TextDelta { text: "hi".into() }).expect("Some");
        match m {
            WsServerMessage::Chunk(env) => {
                assert_eq!(env.kind, "chunk");
                assert_eq!(env.session_id, "sid-1");
                assert_eq!(env.chunk_type, 1);
                assert_eq!(env.payload["text"], "hi");
            }
            _ => panic!("Expected Chunk variant"),
        }
    }

    #[test]
    fn test_tool_lifecycle_to_chunks_3_then_4() {
        let start = map_event(
            "sid-2",
            AgentEvent::ToolStart {
                tool_id: "t1".into(),
                tool_name: "bash".into(),
                input: json!({"cmd": "echo hi"}),
            },
        )
        .expect("Some");
        let result = map_event(
            "sid-2",
            AgentEvent::ToolResult {
                tool_id: "t1".into(),
                tool_name: "bash".into(),
                output: "hi\n".into(),
                success: true,
            },
        )
        .expect("Some");

        let start_v = serde_json::to_value(&start).unwrap();
        let result_v = serde_json::to_value(&result).unwrap();
        assert_eq!(start_v["chunk_type"], 3);
        assert_eq!(start_v["payload"]["tool_name"], "bash");
        assert_eq!(result_v["chunk_type"], 4);
        assert_eq!(result_v["payload"]["success"], true);
    }

    #[test]
    fn test_done_to_control_done() {
        let m = map_event("sid-3", AgentEvent::Done).expect("Some");
        let v = serde_json::to_value(&m).unwrap();
        assert_eq!(v["type"], "done");
        assert_eq!(v["session_id"], "sid-3");
    }

    #[test]
    fn test_approval_to_control_approval() {
        let m = map_event(
            "sid-4",
            AgentEvent::ApprovalRequired {
                tool_name: "bash".into(),
                tool_id: "t99".into(),
                risk_level: grid_types::RiskLevel::HighRisk,
            },
        )
        .expect("Some");
        let v = serde_json::to_value(&m).unwrap();
        assert_eq!(v["type"], "approval_required");
        assert_eq!(v["session_id"], "sid-4");
        assert_eq!(v["tool_name"], "bash");
        assert_eq!(v["tool_id"], "t99");
        assert_eq!(v["risk_level"], "highrisk");
    }

    #[test]
    fn test_serialization_envelope_shape() {
        let m = map_event("sid-X", AgentEvent::TextDelta { text: "x".into() }).expect("Some");
        let v = serde_json::to_value(&m).unwrap();
        assert_eq!(v["type"], "chunk");
        assert_eq!(v["session_id"], "sid-X");
        assert_eq!(v["chunk_type"], 1);
        assert_eq!(v["payload"]["text"], "x");
    }

    #[test]
    fn test_thinking_delta_to_chunk_2() {
        let m = map_event(
            "sid-2",
            AgentEvent::ThinkingDelta {
                text: "thinking".into(),
            },
        )
        .expect("Some");
        match m {
            WsServerMessage::Chunk(e) => {
                assert_eq!(e.chunk_type, 2);
                assert_eq!(e.payload["text"], "thinking");
            }
            _ => panic!("Expected Chunk"),
        }
    }

    #[test]
    fn test_text_complete_to_chunk_5() {
        let m = map_event(
            "s",
            AgentEvent::TextComplete {
                text: "final".into(),
            },
        )
        .expect("Some");
        match m {
            WsServerMessage::Chunk(e) => assert_eq!(e.chunk_type, 5),
            _ => panic!(),
        }
    }

    #[test]
    fn test_error_mid_turn_to_chunk_6() {
        let m = map_event(
            "s",
            AgentEvent::Error {
                message: "boom".into(),
            },
        )
        .expect("Some");
        match m {
            WsServerMessage::Chunk(e) => {
                assert_eq!(e.chunk_type, 6);
                assert_eq!(e.payload["message"], "boom");
            }
            _ => panic!(),
        }
    }

    #[test]
    fn test_workflow_continuation_to_chunk_7() {
        let m = map_event(
            "s",
            AgentEvent::WorkflowContinuation {
                attempt: 1,
                max_attempts: 3,
            },
        )
        .expect("Some");
        match m {
            WsServerMessage::Chunk(e) => {
                assert_eq!(e.chunk_type, 7);
                assert_eq!(e.payload["attempt"], 1);
            }
            _ => panic!(),
        }
    }

    #[test]
    fn test_thinking_complete_to_chunk_8() {
        let m = map_event(
            "s",
            AgentEvent::ThinkingComplete {
                text: "trace".into(),
            },
        )
        .expect("Some");
        match m {
            WsServerMessage::Chunk(e) => assert_eq!(e.chunk_type, 8),
            _ => panic!(),
        }
    }

    #[test]
    fn test_iteration_start_returns_none() {
        let m = map_event("s", AgentEvent::IterationStart { round: 1 });
        assert!(m.is_none(), "IterationStart should be skipped");
    }
}
