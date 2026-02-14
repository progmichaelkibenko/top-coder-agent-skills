# Debugger Skills -- Architecture

This document describes the internal architecture of the **debugger-nodejs** and **debugger-python** agent skills. Both skills share a common design built on top of the `debugger-core` library and differ only in which debug protocol they use.

---

## High-level overview

```
 AI Agent (Cursor / Claude Code)
       |
       |  invokes skill script
       v
 skills/debugger-{lang}/scripts/debug.py      <-- thin CLI router
       |
       |  creates DebugSession.from_file_or_new()
       v
 debugger_core.session.DebugSession            <-- orchestration layer
       |
       |--- probe (one-shot) --> direct in-memory connection
       |
       |--- interactive (multi-step) --> spawns SessionDaemon
       |                                    |
       |                                    |  TCP on 127.0.0.1
       |                                    v
       |                              daemon.py (background)
       |                                    |
       |                                    |  holds connection alive
       |                                    v
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

1. **Shared core, thin skill scripts.** Each skill's `scripts/debug.py` is ~100 lines -- a CLI argument router that sets `LANGUAGE = "node"` or `LANGUAGE = "python"` and delegates to `DebugSession`. All protocol handling, formatting, and state management lives in `debugger-core`.

2. **Two modes in one session class.** `DebugSession` operates in either:
   - **Probe mode** (one-shot): creates a temporary in-memory session, runs to a breakpoint, dumps state, and stops. Single process, no daemon.
   - **Interactive mode** (multi-step): spawns a background daemon that holds the debugger connection alive across separate CLI invocations.

3. **Daemon for connection persistence.** Each skill script invocation is a new Python process. Without the daemon, the debugger connection would die when the process exits. The `SessionDaemon` solves this by running as a detached background process that accepts commands over TCP.

---

## Node.js architecture (CDP)

Node.js debugging uses the **Chrome DevTools Protocol (CDP)** -- the same protocol Chrome DevTools uses. No npm packages are required.

```
debug.py start app.js
    |
    v
DebugSession.start("app.js", "node")
    |
    |-- (file-backed) --> _start_daemon()
    |                        |
    |                        v
    |                   subprocess.Popen (detached)
    |                        |
    |                        v
    |                   daemon.py --port PORT --language node --program app.js
    |                        |
    |                        v
    |                   DebugSession() [in-memory, inside daemon]
    |                        |
    |                        v
    |                   CDPClient()
    |                        |
    |                        v
    |                   node --inspect-brk=0 app.js
    |                        |  (random port, reads WS URL from stderr)
    |                        v
    |                   websockets.connect(ws://127.0.0.1:PORT/GUID)
    |                        |
    |                        v
    |                   Debugger.enable + Runtime.enable
    |                   Runtime.runIfWaitingForDebugger
    |                   wait for Debugger.paused (initial break)
    |                        |
    |                        v
    |                   TCP server listening on 127.0.0.1:PORT
    |                   prints {"ready": true, "port": PORT} to stdout
    |
    v
Parent reads readiness signal, saves port + PID to .debug_session.json
```

### CDP message flow

```
Skill script                  Daemon                    Node.js (V8)
    |                            |                          |
    |-- TCP: {"action":          |                          |
    |    "breakpoint",           |                          |
    |    "file": "app.js",       |                          |
    |    "line": 10}             |                          |
    |  ========================> |                          |
    |                            |-- WS: Debugger.          |
    |                            |   setBreakpointByUrl --> |
    |                            |                          |
    |                            | <-- breakpointId -----   |
    |                            |                          |
    | <== {"result": "Breakpoint |                          |
    |      at app.js:10          |                          |
    |      (verified)"}          |                          |
    |                            |                          |
    |-- TCP: {"action":          |                          |
    |    "resume"}               |                          |
    |  ========================> |                          |
    |                            |-- WS: Debugger.resume -> |
    |                            |                          |
    |                            |    ... app runs ...      |
    |                            |                          |
    |                            | <-- Debugger.paused ---  |
    |                            |     (reason: breakpoint) |
    |                            |                          |
    | <== {"result": "Stopped    |                          |
    |      (breakpoint) at       |                          |
    |      app.js:10\n ..."}     |                          |
```

### CDP-specific details

| Aspect | Detail |
|--------|--------|
| **Transport** | WebSocket (`ws://127.0.0.1:<port>/<guid>`) |
| **Launch flag** | `node --inspect-brk=0` (port 0 = OS-assigned) |
| **Line numbers** | CDP uses 0-based; `CDPClient` converts to/from 1-based |
| **Breakpoints** | `Debugger.setBreakpointByUrl` with `file://` URL and 0-based line |
| **Stepping** | `Debugger.stepOver`, `Debugger.stepInto`, `Debugger.resume` |
| **Evaluation** | `Debugger.evaluateOnCallFrame` for frame-scoped evaluation |
| **Variables** | `Runtime.getProperties` on scope chain object IDs |
| **Stack frames** | Cached from each `Debugger.paused` event's `callFrames` |
| **Ping/pong** | Disabled (`ping_interval=None`) -- V8 inspector doesn't respond to WS pings |
| **Dependencies** | Only `node` on PATH + `websockets` Python package |

---

## Python architecture (DAP)

Python debugging uses the **Debug Adapter Protocol (DAP)** via **debugpy** (Microsoft's official Python debugger). Communication happens over stdin/stdout of the `debugpy.adapter` subprocess.

```
debug.py start app.py
    |
    v
DebugSession.start("app.py", "python")
    |
    |-- (file-backed) --> _start_daemon()
    |                        |
    |                        v
    |                   daemon.py --port PORT --language python --program app.py
    |                        |
    |                        v
    |                   DebugSession() [in-memory, inside daemon]
    |                        |
    |                        v
    |                   PythonAdapter() -> locates debugpy.adapter
    |                        |
    |                        v
    |                   DAPClient(adapter)
    |                        |
    |                        v
    |                   subprocess: python -m debugpy.adapter
    |                        |  (stdin/stdout pipes)
    |                        v
    |                   DAP initialize -> launch -> configurationDone
    |                        |
    |                        v
    |                   TCP server listening on 127.0.0.1:PORT
    |                   prints {"ready": true, "port": PORT} to stdout
```

### DAP message flow

```
Skill script                  Daemon                    debugpy.adapter
    |                            |                          |
    |-- TCP: {"action":          |                          |
    |    "breakpoint",           |                          |
    |    "file": "app.py",       |                          |
    |    "line": 22}             |                          |
    |  ========================> |                          |
    |                            |-- stdin: setBreakpoints  |
    |                            |   {"source": {"path":    |
    |                            |    "app.py"},            |
    |                            |    "breakpoints":        |
    |                            |    [{"line": 22}]}  -->  |
    |                            |                          |
    |                            | <-- stdout: response --- |
    |                            |     breakpoints[0].      |
    |                            |     verified = true      |
    |                            |                          |
    | <== {"result": "Breakpoint |                          |
    |      at app.py:22          |                          |
    |      (verified)"}          |                          |
    |                            |                          |
    |-- TCP: {"action":          |                          |
    |    "resume"}               |                          |
    |  ========================> |                          |
    |                            |-- stdin: continue -->    |
    |                            |                          |
    |                            |    ... app runs ...      |
    |                            |                          |
    |                            | <-- stdout: stopped ---  |
    |                            |     event (breakpoint)   |
    |                            |                          |
    | <== {"result": "Stopped    |                          |
    |      (breakpoint) at       |                          |
    |      app.py:22\n ..."}     |                          |
```

### DAP-specific details

| Aspect | Detail |
|--------|--------|
| **Transport** | stdin/stdout of `debugpy.adapter` subprocess |
| **Message framing** | `Content-Length: N\r\n\r\n{...JSON...}` |
| **Adapter** | `python -m debugpy.adapter` (auto-detected by `PythonAdapter`) |
| **Initialization** | `initialize` -> `initialized` event -> `launch` + `configurationDone` (concurrent via `asyncio.gather`) |
| **Breakpoints** | `setBreakpoints` with `source.path` and line array |
| **Stepping** | `next` (step over), `stepIn`, `continue` |
| **Evaluation** | `evaluate` with `frameId` for scoped evaluation |
| **Variables** | `scopes` -> find "Locals" -> `variables` with `variablesReference` |
| **DAP deadlock fix** | `launch` and `configurationDone` sent concurrently to avoid debugpy deadlock |
| **First resume** | `configurationDone` sent on first `resume()` so breakpoints are registered before execution starts |
| **Dependencies** | `debugpy` Python package |

---

## State management

### Probe mode (one-shot)

No persistent state. A temporary `DebugSession()` is created, does everything in a single call, and is discarded.

```
probe("app.js:10")
    |
    v
tmp = DebugSession()        <-- in-memory, no file, no daemon
tmp.start() -> tmp.add_breakpoint() -> tmp.resume()
    -> tmp._client.stack_trace() + tmp._fetch_locals()
    -> tmp.stop()
    |
    v
formatted probe report (text)
```

### Interactive mode (multi-step)

State is persisted across invocations via two mechanisms:

1. **Session file** (`.debug_session.json`): stores language, program path, breakpoints, daemon port, and daemon PID. Written by the parent process, read by subsequent invocations.

2. **Daemon process**: holds the live debugger connection (WebSocket or stdin/stdout pipe). Accepts JSON-line commands over TCP on `127.0.0.1`.

```
.debug_session.json
{
  "language": "node",
  "program": "/abs/path/to/app.js",
  "breakpoints": {"/abs/path/to/app.js": [5, 10]},
  "daemon_port": 50862,
  "daemon_pid": 71237
}
```

On each invocation, `DebugSession.from_file_or_new()`:
1. Reads the session file
2. Validates the daemon PID is alive (`os.kill(pid, 0)`)
3. Routes commands to the daemon via TCP
4. On `stop`, sends stop command + `SIGTERM` to daemon, deletes session file

---

## File map

```
skills/
  debugger-nodejs/
    SKILL.md                     # Agent-facing docs: when to use, workflows, examples
    scripts/
      debug.py                   # CLI router (LANGUAGE = "node")
  debugger-python/
    SKILL.md                     # Agent-facing docs: when to use, workflows, examples
    scripts/
      debug.py                   # CLI router (LANGUAGE = "python")

packages/
  debugger-core/
    debugger_core/
      __init__.py
      session.py                 # DebugSession: orchestration + daemon spawning
      daemon.py                  # SessionDaemon: background TCP server
      cdp_client.py              # CDPClient: Node.js via Chrome DevTools Protocol
      dap_client.py              # DAPClient: generic DAP over stdin/stdout
      formatters.py              # LLM-friendly text formatting
      adapters/
        __init__.py
        base.py                  # DebugAdapter ABC
        python.py                # PythonAdapter (debugpy)
```

---

## Adding a new language

To add support for a new language (e.g. Go, Ruby):

1. **Choose protocol:**
   - If the runtime has a built-in inspector (like Node.js), create a new client class modeled on `CDPClient`.
   - If a DAP adapter exists (like debugpy, delve), create a new `DebugAdapter` subclass in `adapters/`.

2. **Register the language** in `session.py`:
   - Add to `_CDP_LANGUAGES` or `_DAP_LANGUAGES`.
   - Add the client/adapter instantiation to `start()`.

3. **Create a skill** under `skills/debugger-<lang>/`:
   - `SKILL.md` with agent-facing documentation.
   - `scripts/debug.py` with `LANGUAGE = "<lang>"`.

No changes needed in the daemon, formatters, or MCP server -- they work with any language the session supports.
