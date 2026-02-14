# top-coder-ai-skills-debugger

Shared debugger library for **Top Coder AI Skills**. Python library for **AI-driven debugging** of **Node.js** (CDP) and **Python** (DAP) programs — breakpoints, stepping, and variable inspection without a GUI.

## Features

- **Node.js** — CDP over WebSocket (built-in inspector, no extra npm deps).
- **Python** — DAP via `debugpy` (launch and attach).
- **Single API** — `DebugSession`: start, breakpoints, continue, step, evaluate, stack, variables.
- **Two modes** — In-memory (e.g. MCP server) or file-backed with a daemon (e.g. CLI scripts that run as separate processes).
- **LLM-friendly** — All methods return plain text suitable for agent consumption.

## Install

```bash
pip install top-coder-ai-skills-debugger
# or
uv add top-coder-ai-skills-debugger
# or
poetry add top-coder-ai-skills-debugger
```

**Requirements:** Python ≥3.11.

## Quick start (in-memory)

```python
import asyncio
from debugger_core.session import DebugSession

async def main():
    session = DebugSession()
    print(await session.start("app.js", "node"))
    print(await session.add_breakpoint("app.js", 10))
    print(await session.resume())       # run until breakpoint
    print(await session.inspect("x"))    # evaluate expression
    print(await session.get_stack())
    print(await session.stop())

asyncio.run(main())
```

All methods return strings (status messages, stack traces, variable dumps, or error text).

## Session modes

| Mode | Use case | How |
|------|----------|-----|
| **In-memory** | MCP server, scripts in one process | `session = DebugSession()` then `start`, `resume`, etc. |
| **File-backed** | CLI scripts (each command is a new process) | `session = DebugSession.from_file_or_new(language="node")`. First call runs `start()` and spawns a daemon; later calls reuse it via the saved session file. |

For file-backed usage, always call `stop()` when done so the daemon and debuggee are torn down.

## API overview

| Method | Description |
|--------|-------------|
| `start(program, language)` | Launch the debugger (`language`: `"node"` or `"python"`). |
| `add_breakpoint(file, line)` | Set a breakpoint; returns verification status. |
| `resume()` | Continue until next breakpoint or program exit. |
| `step(action="next")` | Step over (`next`) or step in (`step_in`). |
| `inspect(expression)` | Evaluate an expression in the current frame. |
| `get_stack()` | Current call stack as formatted text. |
| `get_local_variables()` | Local variables of the top frame. |
| `probe(program, file, line, language)` | One-shot: start, run to line, return stack + variables, then stop. |
| `stop()` | Disconnect and clean up. |

## Development

From the package directory:

```bash
# Build wheel + sdist
make build

# Publish to PyPI (after configuring auth)
make publish

# Clean and reinstall from dist (sanity check)
make clean && make test-install
```

See the repo root and `docs/PUBLISHING.md` for workspace setup and publishing from the monorepo.

## License

MIT. See the top-level repo for full license and source links.
