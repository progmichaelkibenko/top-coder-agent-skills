# debugger-mcp

MCP server that exposes **debugger tools** to AI clients (Cursor, Claude Code, etc.): launch, breakpoints, continue, step, evaluate, stack, variables, probe, stop. Supports **Node.js** (CDP) and **Python** (DAP). The debugger runtime ([top-coder-ai-skills-debugger](https://pypi.org/project/top-coder-ai-skills-debugger/)) is included as a dependency — **no separate installation**.

## Install

One install is enough (the debugger library is pulled in automatically):

```bash
pip install debugger-mcp
# or
uv add debugger-mcp
# or
poetry add debugger-mcp
```

**Requires:** Python ≥3.11. Nothing else to install.

### Global

Use without adding the package to a project:

- **pipx** (install once, run from anywhere):
  ```bash
  pipx install debugger-mcp
  debugger-mcp
  ```
  Then in MCP config use `"command": "debugger-mcp"` (pipx puts it on PATH).

- **uvx** (run on demand, no install — like `npx`):
  ```bash
  uvx debugger-mcp
  ```
  In MCP config: `"command": "uvx", "args": ["debugger-mcp"]`.

## Run

Stdio transport (e.g. for Cursor MCP). Configure in your MCP client (e.g. Cursor) using **one** of these:

**Option A — pipx** (after `pipx install debugger-mcp`; use if `debugger-mcp` is on your PATH):

```json
{
  "mcpServers": {
    "debugger": {
      "command": "debugger-mcp"
    }
  }
}
```

**Option B — uvx** (no install; runs on demand, like npx):

```json
{
  "mcpServers": {
    "debugger": {
      "command": "uvx",
      "args": ["debugger-mcp"]
    }
  }
}
```

**Option C — in-project** (if you added the package to the project with `uv add` / `poetry add` / `pip install`):

```json
{
  "mcpServers": {
    "debugger": {
      "command": "python3",
      "args": ["-m", "debugger_mcp"]
    }
  }
}
```

If using Option A and the app doesn’t see `debugger-mcp` on PATH, use the full path (e.g. `~/.local/bin/debugger-mcp` on Linux/macOS) or use Option B (uvx) instead.

## Tools

| Tool | Description |
|------|-------------|
| `debug_launch` | Start debugging a program (program, language) |
| `debug_breakpoint` | Set breakpoint (file, line) |
| `debug_continue` | Resume until next breakpoint or exit |
| `debug_step` | Step over or step in |
| `debug_evaluate` | Evaluate expression in current frame |
| `debug_stack` | Get call stack |
| `debug_variables` | Get local variables |
| `debug_probe` | One-shot: run to line, dump state, stop |
| `debug_stop` | End the debug session |

See the repo and [ARCHITECTURE.md](ARCHITECTURE.md) for protocol and usage details.
