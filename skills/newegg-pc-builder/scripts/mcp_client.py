#!/usr/bin/env python3
"""
Newegg PC Builder – MCP HTTP Client (fallback script)

When the MCP server is NOT pre-configured in the agent's client settings,
this script lets Claude call the Newegg PC Builder MCP service directly
over HTTP using the MCP JSON-RPC protocol (Streamable HTTP transport).

Usage (called by Claude via Bash tool):
    python mcp_client.py list_tools
    python mcp_client.py call <tool_name> '<json_arguments>'

Examples:
    python mcp_client.py list_tools
    python mcp_client.py call get_builds '{"budget": 1500, "use_case": "gaming"}'
    python mcp_client.py call check_compatibility '{"gpu": "RTX 4070", "motherboard": "B650"}'
"""

import sys
import json
import urllib.request
import urllib.error
import uuid

MCP_ENDPOINT = "https://apis.newegg.com/ex-mcp/endpoint/pcbuilder"
TIMEOUT = 30  # seconds


def _post(payload: dict) -> dict:
    """Send a JSON-RPC request to the MCP endpoint and return the response."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MCP_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8")

            # Handle SSE (text/event-stream) – extract the last "data:" line
            if "text/event-stream" in content_type:
                result_data = None
                for line in raw.splitlines():
                    if line.startswith("data:"):
                        try:
                            result_data = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            pass
                if result_data is None:
                    raise ValueError(f"No valid JSON found in SSE stream:\n{raw[:500]}")
                return result_data

            # Standard JSON response
            return json.loads(raw)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {e.code} from MCP endpoint: {error_body[:300]}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach MCP endpoint ({MCP_ENDPOINT}): {e.reason}"
        ) from e


def _initialize() -> dict:
    """MCP initialize handshake."""
    resp = _post({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "newegg-skill-client", "version": "1.0"},
        },
    })
    if "error" in resp:
        raise RuntimeError(f"MCP initialize error: {resp['error']}")
    return resp.get("result", {})


def list_tools() -> None:
    """Print all tools exposed by the MCP service."""
    _initialize()
    resp = _post({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    })
    if "error" in resp:
        raise RuntimeError(f"tools/list error: {resp['error']}")

    tools = resp.get("result", {}).get("tools", [])
    if not tools:
        print("(no tools returned)")
        return

    print(f"Available tools ({len(tools)}):\n")
    for t in tools:
        name = t.get("name", "?")
        desc = t.get("description", "")
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])
        params = []
        for k, v in props.items():
            marker = "*" if k in required else ""
            ptype = v.get("type", "any")
            pdesc = v.get("description", "")
            params.append(f"    {marker}{k} ({ptype}): {pdesc}")
        print(f"  [{name}]")
        print(f"  {desc}")
        if params:
            print("  Parameters (* = required):")
            print("\n".join(params))
        print()


def call_tool(tool_name: str, arguments: dict) -> None:
    """Call a specific MCP tool and print the result."""
    _initialize()
    resp = _post({
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    })
    if "error" in resp:
        raise RuntimeError(f"tools/call error for '{tool_name}': {resp['error']}")

    result = resp.get("result", {})
    content = result.get("content", result)  # some servers wrap in "content"

    # Pretty-print if it's structured data
    if isinstance(content, (dict, list)):
        print(json.dumps(content, indent=2, ensure_ascii=False))
    else:
        print(content)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "list_tools":
        list_tools()

    elif command == "call":
        if len(sys.argv) < 3:
            print("Usage: mcp_client.py call <tool_name> [json_arguments]")
            sys.exit(1)
        tool_name = sys.argv[2]
        raw_args = sys.argv[3] if len(sys.argv) > 3 else "{}"
        try:
            arguments = json.loads(raw_args)
        except json.JSONDecodeError as e:
            print(f"Error: arguments must be valid JSON.\n  Got: {raw_args}\n  {e}")
            sys.exit(1)
        call_tool(tool_name, arguments)

    else:
        print(f"Unknown command: {command!r}\nUse: list_tools | call")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
