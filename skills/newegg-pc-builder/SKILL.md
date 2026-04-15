---
name: newegg-pc-builder
description: >
  Connect to Newegg PC Builder MCP service to retrieve PC build configurations,
  component compatibility, and build recommendations. Use this skill whenever
  the user asks about PC builds, custom PC configurations, component compatibility
  checks, budget builds, gaming rigs, workstation setups, or anything related to
  selecting or validating PC components on Newegg — even if they don't mention
  "PC Builder" by name. Also use when the user says things like "help me build a
  PC", "is this GPU compatible with my motherboard", "what parts do I need for
  a $1500 gaming build", or "show me Newegg build configs".
---
 
# Newegg PC Builder MCP Skill
 
This skill connects to the Newegg PC Builder MCP service to answer questions
about PC configurations, component compatibility, and build recommendations.
 
**MCP Endpoint**: `https://apis.newegg.com/ex-mcp/endpoint/pcbuilder`
 
---
 
## How to Connect: Two Modes
 
### Mode 1 — MCP Tools Already Configured (preferred)
 
If the agent's host (Cursor, Claude Desktop, Claude Code, etc.) has the Newegg
PC Builder MCP server pre-configured, MCP tools will appear directly in the
available tool list. Use them natively — no script needed.
 
To check: look for tool names like `get_builds`, `check_compatibility`,
`get_components`, etc. in the available tools. If they exist, call them directly.
 
To configure the MCP server, see the **Client Setup** section below.
 
---
 
### Mode 2 — MCP Not Configured (script fallback)
 
When the MCP server is not configured, use the bundled script to call the
service directly over HTTP. The script implements the MCP JSON-RPC protocol
(Streamable HTTP transport) so you get the same data without any client setup.
 
**Step 1: Discover available tools**
```bash
python scripts/mcp_client.py list_tools
```
This prints all tools the service exposes, with parameter names, types, and descriptions.
 
**Step 2: Call a tool**
```bash
python scripts/mcp_client.py call <tool_name> '<json_arguments>'
```
 
**Common examples:**
 
```bash
# List all available PC builds
python scripts/mcp_client.py call get_builds '{}'
 
# Find builds within a budget
python scripts/mcp_client.py call get_builds '{"budget": 1500, "use_case": "gaming"}'
 
# Check GPU + motherboard compatibility
python scripts/mcp_client.py call check_compatibility \
  '{"gpu": "NVIDIA RTX 4070", "motherboard": "ASUS ROG STRIX B650-A"}'
 
# Get component details
python scripts/mcp_client.py call get_components \
  '{"category": "GPU", "budget_max": 400}'
 
# Get a specific build configuration
python scripts/mcp_client.py call get_build_detail '{"build_id": "BUILD-12345"}'
```
 
**Always run `list_tools` first** if you're unsure what tools are available — the
service may expose more tools than shown above and their parameters may differ.
 
---
 
## Decision Flow
 
```
User asks about PC builds / compatibility
        │
        ▼
Is the MCP server configured in this agent client?
        │
   YES  │  NO
        │   └──► python scripts/mcp_client.py list_tools
        │         then call the relevant tool via the script
        ▼
Use MCP tools directly (e.g., call `get_builds`)
        │
        ▼
Present results to the user in a clear, readable format
```
 
---
 
## Presenting Results
 
After getting data from the service (either mode), present it clearly:
 
- **Build list**: Show name, total price, key components, and a brief description
- **Compatibility check**: State clearly whether compatible, and explain why/why not
- **Component details**: List specs, price, and compatibility notes
- **Recommendations**: Rank by value and explain trade-offs
 
---
 
## Client Setup (one-time, optional)
 
Configure the MCP server in your client so MCP tools are available natively.
 
### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "newegg-pc-builder": {
      "url": "https://apis.newegg.com/ex-mcp/endpoint/pcbuilder",
      "transport": "http"
    }
  }
}
```
 
### Claude Code / Cowork (`.claude/mcp.json` or via CLI)
```bash
claude mcp add newegg-pc-builder \
  --transport http \
  --url https://apis.newegg.com/ex-mcp/endpoint/pcbuilder
```
Or add to your project's `.mcp.json`:
```json
{
  "mcpServers": {
    "newegg-pc-builder": {
      "url": "https://apis.newegg.com/ex-mcp/endpoint/pcbuilder",
      "transport": "http"
    }
  }
}
```
 
### Cursor (`~/.cursor/mcp.json` or project `.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "newegg-pc-builder": {
      "url": "https://apis.newegg.com/ex-mcp/endpoint/pcbuilder",
      "transport": "http"
    }
  }
}
```
 
### Windsurf / Codeium (`~/.codeium/windsurf/mcp_config.json`)
```json
{
  "mcpServers": {
    "newegg-pc-builder": {
      "url": "https://apis.newegg.com/ex-mcp/endpoint/pcbuilder",
      "transport": "http"
    }
  }
}
```
 
### Other MCP-compatible clients
Add a server entry pointing to:
- **URL**: `https://apis.newegg.com/ex-mcp/endpoint/pcbuilder`
- **Transport**: `http` (Streamable HTTP / MCP 2024-11-05 protocol)
- **Authentication**: Not required for basic access
 
---
 
## Script Requirements
 
The fallback script (`scripts/mcp_client.py`) requires only Python 3.6+ with
no external dependencies — it uses only the standard library (`urllib`, `json`,
`uuid`). It works in any environment where Python is available.