# Debugger MCP Server -- Architecture

This document describes the internal architecture of the **debugger-mcp** server -- an MCP (Model Context Protocol) server that exposes runtime debugging tools for Node.js and Python to any MCP-compatible AI client.

---

## High-level overview

```
 AI Client (Cursor / Claude Desktop / Claude Code)
       |
       |  MCP protocol (JSON-RPC over stdio)
       v
 debugger_mcp/server.py                        <-- MCP server
       |
       |  Strategy pattern dispatch
       v
 debugger_core.session.DebugSession            <-- shared orchestration
       |
       +---> CDPClient  (Node.js)    or    DAPClient  (Python)
                |                              |
                | WebSocket                    | stdin/stdout
                v                              v
            node --inspect-brk             debugpy.adapter
                |                              |
                v                              v
            V8 Inspector                   CPython debugger
```

### Key design decisions

1. **MCP as the transport.** The server uses the MCP low-level SDK (`mcp.server.lowlevel.Server`) with stdio transport. The AI client sends JSON-RPC requests, and the server responds with plain-text results optimized for LLM consumption.

2. **Single long-lived session.** The MCP server runs as a persistent process. A single `DebugSession` is kept in memory (and backed to `.debug_session.mcp.json` for crash recovery). No daemon is needed -- the server itself holds the debugger connection.

3. **Strategy pattern for tool dispatch.** Each MCP tool is a `(schema, handler, resets_session)` tuple in a registry. Adding a new tool is one dict entry -- no branching logic to modify.

4. **Zero code duplication.** The MCP server is a thin layer (~300 lines) on top of `debugger-core`. All protocol handling, state management, and formatting is in the shared library.

---

## MCP tool catalog

The server exposes 9 tools:

| Tool | Description | Resets session |
|------|-------------|:--------------:|
| `debug_launch` | Start debugging a program (Node.js or Python) | No |
| `debug_breakpoint` | Set a breakpoint at file:line | No |
| `debug_continue` | Resume execution until next breakpoint/termination | No |
| `debug_step` | Step over or step into the current line | No |
| `debug_evaluate` | Evaluate an expression in the current frame | No |
| `debug_stack` | Get the current call stack trace | No |
| `debug_variables` | Get local variables in the current frame | No |
| `debug_probe` | One-shot: launch, breakpoint, run, dump state, stop | No |
| `debug_stop` | End the debug session and clean up | Yes |

Tools that "reset session" create a fresh `DebugSession` after execution, clearing the in-memory state for the next debug run.

---

## Node.js architecture (CDP)

When the AI client calls `debug_launch` with `language: "node"`:

```
AI Client                     MCP Server                    Node.js
    |                            |                             |
    |-- call_tool:               |                             |
    |   debug_launch             |                             |
    |   {program: "app.js",      |                             |
    |    language: "node"}       |                             |
    |  ========================> |                             |
    |                            |                             |
    |                            |  DebugSession.start()       |
    |                            |  CDPClient()                |
    |                            |                             |
    |                            |-- subprocess.exec:          |
    |                            |   node --inspect-brk=0      |
    |                            |   app.js                    |
    |                            |                        ---> |
    |                            |                             |
    |                            | <-- stderr: Debugger        |
    |                            |     listening on             |
    |                            |     ws://127.0.0.1:PORT/ID  |
    |                            |                             |
    |                            |-- websockets.connect() ---> |
    |                            |-- Debugger.enable --------> |
    |                            |-- Runtime.enable ---------->|
    |                            |-- runIfWaitingForDebugger -> |
    |                            |                             |
    |                            | <-- Debugger.paused ------  |
    |                            |     (initial break)         |
    |                            |                             |
    | <== "Debugger started      |                             |
    |      for app.js (node).    |                             |
    |      Ready for             |                             |
    |      breakpoints."         |                             |
```

### Subsequent tool calls (Node.js)

```
AI Client                     MCP Server                    Node.js
    |                            |                             |
    |-- debug_breakpoint         |                             |
    |   {file, line: 10}         |                             |
    |  ========================> |                             |
    |                            |-- Debugger.                 |
    |                            |   setBreakpointByUrl -----> |
    |                            | <-- breakpointId ---------  |
    | <== "Breakpoint at         |                             |
    |      app.js:10 (verified)" |                             |
    |                            |                             |
    |-- debug_continue           |                             |
    |  ========================> |                             |
    |                            |-- Debugger.resume --------> |
    |                            |         ... runs ...        |
    |                            | <-- Debugger.paused ------  |
    |                            |-- stack_trace() (cached)    |
    |                            |-- format_stopped_at()       |
    | <== "Stopped (breakpoint)  |                             |
    |      at app.js:10          |                             |
    |      >>> 10 | code..."     |                             |
    |                            |                             |
    |-- debug_evaluate           |                             |
    |   {expression: "item"}     |                             |
    |  ========================> |                             |
    |                            |-- evaluateOnCallFrame ----> |
    |                            | <-- result ---------------  |
    | <== "(object) Object"      |                             |
    |                            |                             |
    |-- debug_variables          |                             |
    |  ========================> |                             |
    |                            |-- scopes(frame0) ---------> |
    |                            |-- Runtime.getProperties --> |
    |                            | <-- properties -----------  |
    | <== "  total: number = 0   |                             |
    |        i: number = 0       |                             |
    |        item: object = ..." |                             |
    |                            |                             |
    |-- debug_stop               |                             |
    |  ========================> |                             |
    |                            |-- ws.close() -------------> |
    |                            |-- process.terminate() ----> |
    |                            |  session = new DebugSession()|
    | <== "Debug session ended." |                             |
```

### CDP-specific details

| Aspect | Detail |
|--------|--------|
| **Transport** | WebSocket (`ws://127.0.0.1:<port>/<guid>`) |
| **Launch** | `node --inspect-brk=0` (random port, WS URL from stderr) |
| **Lines** | CDP is 0-based; `CDPClient` converts to/from 1-based |
| **Evaluation** | `Debugger.evaluateOnCallFrame` for frame-scoped expressions |
| **Variables** | `Runtime.getProperties` on scope chain object IDs |
| **Stack** | Cached from each `Debugger.paused` event |
| **Pings** | Disabled (`ping_interval=None`) -- V8 doesn't respond to WS pings |
| **Dependencies** | Only `node` on PATH |

---

## Python architecture (DAP)

When the AI client calls `debug_launch` with `language: "python"`:

```
AI Client                     MCP Server                    debugpy
    |                            |                             |
    |-- call_tool:               |                             |
    |   debug_launch             |                             |
    |   {program: "app.py",      |                             |
    |    language: "python"}     |                             |
    |  ========================> |                             |
    |                            |                             |
    |                            |  DebugSession.start()       |
    |                            |  PythonAdapter()            |
    |                            |  DAPClient(adapter)         |
    |                            |                             |
    |                            |-- subprocess.exec:          |
    |                            |   python -m debugpy.adapter |
    |                            |                        ---> |
    |                            |                             |
    |                            |-- stdin: initialize ------> |
    |                            | <-- stdout: initialized --  |
    |                            |                             |
    |                            |-- stdin: launch ----------> |  (concurrent
    |                            |-- stdin: configurationDone >|   via asyncio.
    |                            |                             |   gather)
    |                            | <-- stdout: launch resp --  |
    |                            |                             |
    | <== "Debugger started      |                             |
    |      for app.py (python).  |                             |
    |      Ready for             |                             |
    |      breakpoints."         |                             |
```

### Subsequent tool calls (Python)

```
AI Client                     MCP Server                    debugpy
    |                            |                             |
    |-- debug_breakpoint         |                             |
    |   {file, line: 22}         |                             |
    |  ========================> |                             |
    |                            |-- stdin: setBreakpoints     |
    |                            |   {source: {path},          |
    |                            |    breakpoints:             |
    |                            |    [{line: 22}]} ---------> |
    |                            | <-- breakpoints[0].         |
    |                            |     verified = true ------  |
    | <== "Breakpoint at         |                             |
    |      app.py:22 (verified)" |                             |
    |                            |                             |
    |-- debug_continue           |                             |
    |  ========================> |                             |
    |                            |-- stdin: continue --------> |
    |                            |         ... runs ...        |
    |                            | <-- stdout: stopped event - |
    |                            |     {reason: "breakpoint"}  |
    |                            |-- stdin: stackTrace ------> |
    |                            | <-- stackFrames -----------|
    |                            |-- format_stopped_at()       |
    | <== "Stopped (breakpoint)  |                             |
    |      at app.py:22          |                             |
    |      >>> 22 | code..."     |                             |
    |                            |                             |
    |-- debug_evaluate           |                             |
    |   {expression: "my_var"}   |                             |
    |  ========================> |                             |
    |                            |-- stdin: evaluate           |
    |                            |   {expression: "my_var",    |
    |                            |    frameId: 0} -----------> |
    |                            | <-- result, type ---------- |
    | <== "(str) hello world"    |                             |
    |                            |                             |
    |-- debug_stop               |                             |
    |  ========================> |                             |
    |                            |-- stdin: disconnect ------> |
    |                            |-- process.terminate()       |
    |                            |  session = new DebugSession()|
    | <== "Debug session ended." |                             |
```

### DAP-specific details

| Aspect | Detail |
|--------|--------|
| **Transport** | stdin/stdout of `debugpy.adapter` subprocess |
| **Framing** | `Content-Length: N\r\n\r\n{...JSON...}` |
| **Adapter** | `python -m debugpy.adapter` (auto-located by `PythonAdapter`) |
| **Init sequence** | `initialize` -> `initialized` event -> `launch` + `configurationDone` (concurrent) |
| **Breakpoints** | `setBreakpoints` with `source.path` and line array |
| **Stepping** | `next` (step over), `stepIn` |
| **Evaluation** | `evaluate` with `frameId` for scoped evaluation |
| **Variables** | `scopes` -> find "Locals" -> `variables` with `variablesReference` |
| **Dependencies** | `debugpy` Python package |

---

## Server architecture

### Strategy pattern dispatch

The MCP server uses a **strategy pattern** instead of `if/elif` chains. Each tool is a registry entry:

```python
_TOOL_REGISTRY: dict[str, tuple[Tool, ToolStrategy, bool]] = {
    "debug_launch": (tool_schema, _launch, False),
    "debug_breakpoint": (tool_schema, _breakpoint, False),
    ...
    "debug_stop": (tool_schema, _stop, True),  # resets session
}
```

The dispatcher is just:

```python
@server.call_tool()
async def handle_call_tool(name, arguments):
    schema, strategy, resets = _TOOL_REGISTRY[name]
    text = await strategy(_session, arguments)
    if resets:
        _session = DebugSession.from_file_or_new(session_file=_MCP_SESSION_FILE)
    return [TextContent(type="text", text=text)]
```

Adding a new tool = one function + one dict entry. No branching logic to touch.

### Session lifecycle

```
Server starts
    |
    v
_session = DebugSession.from_file_or_new(".debug_session.mcp.json")
    |
    |  (if crash recovery file exists, restores language/program/breakpoints)
    |
    v
Waiting for tool calls...
    |
    |-- debug_launch --> session.start() --> CDPClient or DAPClient
    |-- debug_breakpoint --> session.add_breakpoint()
    |-- debug_continue --> session.resume()
    |-- debug_evaluate --> session.inspect()
    |-- ...
    |-- debug_stop --> session.stop() --> _session = fresh DebugSession()
    |
    v
Waiting for next tool calls...
```

### MCP server vs. skill scripts

| Aspect | MCP Server | Skill Scripts |
|--------|-----------|---------------|
| **Process model** | Single long-lived process | New process per command |
| **Connection** | In-memory `CDPClient`/`DAPClient` | Daemon holds connection |
| **State** | In-memory + `.debug_session.mcp.json` | `.debug_session.json` + daemon |
| **Session file** | `.debug_session.mcp.json` | `.debug_session.json` |
| **Invoked by** | AI client via MCP protocol | AI agent via shell commands |
| **Daemon needed** | No (server IS the long-running process) | Yes (for interactive mode) |
| **Probe** | Same as interactive (server stays alive) | Direct in-memory (no daemon) |

---

## File map

```
packages/
  debugger-mcp/
    ARCHITECTURE.md              # This file
    pyproject.toml               # Package definition (depends on debugger-core, mcp)
    debugger_mcp/
      __init__.py
      __main__.py                # Entry: python -m debugger_mcp
      server.py                  # MCP server, tool registry, strategy dispatch

  debugger-core/                 # Shared library (see skills/ARCHITECTURE.md)
    debugger_core/
      session.py                 # DebugSession orchestration
      cdp_client.py              # Node.js via CDP/WebSocket
      dap_client.py              # Generic DAP over stdin/stdout
      daemon.py                  # Background TCP server (skill scripts only)
      formatters.py              # LLM-friendly text output
      adapters/
        base.py                  # DebugAdapter ABC
        python.py                # PythonAdapter (debugpy)
```

---

## Configuration

### Cursor / Claude Desktop

```json
{
  "mcpServers": {
    "debugger": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/top-coder-agent-skills", "python", "-m", "debugger_mcp"]
    }
  }
}
```

### Standalone (for testing)

```bash
# Run the MCP server on stdio (it will wait for JSON-RPC input)
uv run python -m debugger_mcp
```

---

## Adding a new tool

1. Write a strategy function:

```python
async def _my_tool(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.some_method(args["param"])
```

2. Add it to `_TOOL_REGISTRY`:

```python
"debug_my_tool": (
    types.Tool(
        name="debug_my_tool",
        description="What this tool does.",
        inputSchema={...},
    ),
    _my_tool,
    False,  # True if this resets the session
),
```

No other changes needed. The `list_tools` and `call_tool` handlers pick it up automatically.
