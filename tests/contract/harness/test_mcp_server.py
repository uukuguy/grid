"""Minimal stdio MCP server for D137 part 3 bridge contract tests.

Implements just enough of the Model Context Protocol stdio transport
to expose a single ``echo`` tool. Used by the
:mod:`tests.contract.harness.mcp_subprocess` fixture to validate that
L1 runtimes can:

  1. Accept ``ConnectMCPRequest`` with a stdio ``McpServerConfig``.
  2. Round-trip a tool invocation.
  3. Detect disconnect.
  4. Recover via reconnect.
  5. Surface errors when the tool call references an unknown name.

The transport is line-delimited JSON over stdio per the MCP spec. This
is NOT a full MCP server — it does NOT implement resources, prompts,
completions, or the long-running session model. ONLY:

  * ``initialize`` request → fixed capabilities response
  * ``tools/list`` → ``[{"name": "echo", "description": "echoes args"}]``
  * ``tools/call`` with ``name="echo"`` → returns ``{"content": [args]}``
  * any other request → JSON-RPC error ``-32601 method not found``

Lifecycle: started as a subprocess by the ``mcp_subprocess`` pytest
fixture; reads stdin lines, writes stdout lines; exits when stdin
closes. No HTTP, no sockets.

The filename starts with ``test_`` only because pytest discovers it
under tests/contract/. It is NOT a pytest test module — it is a
standalone CLI invoked via ``python -m`` / direct ``python <path>``.
The ``if __name__ == "__main__"`` guard at the bottom is the only
entry point that matters; pytest collects nothing from this file
because the top-level function is ``main()``.
"""

from __future__ import annotations

import json
import sys


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method", "")
        rid = req.get("id")
        if method == "initialize":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "contract-echo",
                            "version": "0.1.0",
                        },
                    },
                }
            )
        elif method == "tools/list":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "tools": [
                            {
                                "name": "echo",
                                "description": (
                                    "echoes arguments back as a text block"
                                ),
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {"type": "string"},
                                    },
                                },
                            }
                        ],
                    },
                }
            )
        elif method == "tools/call":
            params = req.get("params", {})
            if params.get("name") != "echo":
                _send(
                    {
                        "jsonrpc": "2.0",
                        "id": rid,
                        "error": {
                            "code": -32601,
                            "message": (
                                f"method not found: tool "
                                f"{params.get('name')!r}"
                            ),
                        },
                    }
                )
                continue
            args = params.get("arguments", {})
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(args),
                            }
                        ],
                    },
                }
            )
        else:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "error": {
                        "code": -32601,
                        "message": f"method not found: {method}",
                    },
                }
            )


if __name__ == "__main__":
    main()
