"""Minimal OpenAI-compatible mock used by contract tests.

The contract suite drives runtimes against deterministic LLM output so
that protocol-level assertions (event ordering, envelope shape) are not
coupled to live model behaviour. This FastAPI app implements just enough
of the OpenAI ``/v1/chat/completions`` surface for an L1 runtime to
complete a turn: it accepts the request and returns a fixed assistant
message, optionally scripted to call a single tool once before stopping.

The app is instantiated by :func:`build_app` and hosted by tests via
``uvicorn`` on a loopback port. The runtime subprocess is pointed at the
mock via ``OPENAI_BASE_URL=http://127.0.0.1:<port>/v1``.

S0.T4 extension: a per-server scripted-turn counter lets tests request
"first call emits tool_use for <tool_name>, subsequent calls emit plain
text" so PreToolUse/PostToolUse/Stop hooks actually fire end-to-end
inside the real grid-runtime agent loop.
"""

from __future__ import annotations

import json
import threading
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class _ChatRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]] | None = None
    stream: bool = False
    tool_choice: Any = None


async def _sse_delta_response(
    model: str,
    idx: int,
    shape: dict[str, Any],
) -> AsyncIterator[bytes]:
    """Emit one OpenAI-compatible SSE-delta chat completion.

    D136 fix (Phase 5.3 WATCH-03): grid-engine's OpenAIProvider.stream()
    parses ``delta["tool_calls"][N]`` expecting ``index`` (uint),
    ``id`` (str), and ``function.{name, arguments}`` (str, str) per
    openai.rs around line 866. The synchronous chat-completion shape
    we kept for compatibility uses ``message.tool_calls[N]`` (no
    ``index``), which fails the SSE-delta parser silently.

    This emitter mirrors the real OpenAI SSE shape: one role+id chunk,
    one tool_call delta with name + arguments string, one finish chunk,
    and the ``data: [DONE]`` sentinel.
    """
    if shape["kind"] == "tool_calls":
        # 1. role chunk
        chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")

        # 2. tool_call delta with index + nested function.{name,arguments}
        tool_chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": shape["tool_id"],
                                "type": "function",
                                "function": {
                                    "name": shape["tool_name"],
                                    "arguments": json.dumps(shape["arguments"]),
                                },
                            }
                        ]
                    },
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(tool_chunk)}\n\n".encode("utf-8")

        # 3. finish chunk (tool_calls)
        finish_chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls",
                }
            ],
        }
        yield f"data: {json.dumps(finish_chunk)}\n\n".encode("utf-8")
    else:
        # Terminal stop path — a small text delta + stop finish_reason.
        role_chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(role_chunk)}\n\n".encode("utf-8")

        content_chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": shape.get("content", "mock response")},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(content_chunk)}\n\n".encode("utf-8")

        finish_chunk = {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        yield f"data: {json.dumps(finish_chunk)}\n\n".encode("utf-8")

    # Terminator — closes the SSE stream per OpenAI spec.
    yield b"data: [DONE]\n\n"


def build_app(
    tool_script: list[dict[str, Any]] | None = None,
) -> FastAPI:
    """Return a FastAPI app implementing the minimum OpenAI surface.

    Args:
        tool_script: Optional ordered list of tool-call descriptors. Each
            entry dict must carry ``"tool_name"`` and ``"arguments"`` (a
            JSON-serializable dict). The Nth chat-completion request is
            answered with ``tool_calls=[{tool_script[N]}]`` and
            ``finish_reason="tool_calls"``. When the script is exhausted,
            subsequent requests fall back to the plain "mock response"
            terminal-stop reply. Pass ``None`` to disable scripting
            entirely (matches pre-S0.T4 behaviour).

    Endpoints:

    * ``POST /v1/chat/completions`` — scripted behaviour described above.
      Supports both synchronous JSON (``stream=false``) and SSE-delta
      (``stream=true``) response shapes. The SSE path was added in
      Phase 5.3 WATCH-03 / D136: grid-engine's OpenAIProvider only ever
      issues ``stream=true``, so without the SSE branch the runtime's
      delta parser saw zero events and the agent loop exited without
      firing PreToolUse / PostToolUse / Stop hooks.
    * ``GET  /health`` — liveness probe (always 200 ``{"status": "ok"}``).

    Returns:
        A :class:`fastapi.FastAPI` app ready to be served by uvicorn.
    """
    app = FastAPI(title="contract-harness-mock-openai")
    # Thread-safe per-app turn counter; uvicorn may dispatch concurrent
    # requests on its own workers. We rely on this counter to walk the
    # scripted tool-call sequence deterministically.
    counter_lock = threading.Lock()
    counter = {"n": 0}
    script = list(tool_script or [])

    @app.post("/v1/chat/completions")
    async def chat_completions(req: _ChatRequest):
        with counter_lock:
            idx = counter["n"]
            counter["n"] += 1

        # Resolve the response shape (scripted tool_use OR terminal stop)
        # from the same script counter for both synchronous and SSE paths.
        if idx < len(script):
            entry = script[idx]
            shape = {
                "kind": "tool_calls",
                "tool_name": entry["tool_name"],
                "arguments": entry.get("arguments", {}),
                "tool_id": entry.get("id", f"call_{idx}"),
            }
        else:
            shape = {
                "kind": "stop",
                "content": "mock response",
            }

        if req.stream:
            # D136 fix (Phase 5.3 WATCH-03): real OpenAI clients (including
            # grid-engine OpenAIProvider) issue `stream=true` and expect
            # SSE-delta chunks. The synchronous JSON path below answered
            # 200 OK but with Content-Type: application/json, so the
            # runtime's stream parser saw zero events → agent_loop exited
            # without ever firing PreToolUse / PostToolUse / Stop hooks.
            return StreamingResponse(
                _sse_delta_response(req.model, idx, shape),
                media_type="text/event-stream",
            )

        # Synchronous path (pre-5.3 baseline — kept for any caller that
        # explicitly sets stream=false).
        if shape["kind"] == "tool_calls":
            return {
                "id": f"chatcmpl-mock-{idx}",
                "object": "chat.completion",
                "created": 0,
                "model": req.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": shape["tool_id"],
                                    "type": "function",
                                    "function": {
                                        "name": shape["tool_name"],
                                        "arguments": json.dumps(shape["arguments"]),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 2,
                    "total_tokens": 2,
                },
            }

        return {
            "id": f"chatcmpl-mock-{idx}",
            "object": "chat.completion",
            "created": 0,
            "model": req.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": shape["content"],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 2,
                "total_tokens": 2,
            },
        }

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
