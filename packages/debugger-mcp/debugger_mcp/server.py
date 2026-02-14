"""
MCP server that exposes DAP-based debugging tools.

Thin layer on top of ``debugger_core.session.DebugSession``.
All heavy lifting (protocol, formatting, adapter spawning) lives in
the shared ``debugger-core`` package.

Run::

    python -m debugger_mcp.server          # stdio transport
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Awaitable

import mcp.server.stdio
from mcp import types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from debugger_core.session import DebugSession

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Each strategy is an async callable: (session, args) -> str
ToolStrategy = Callable[[DebugSession, dict[str, Any]], Awaitable[str]]

# ---------------------------------------------------------------------------
# Server + shared session (file-backed so state survives restarts)
# ---------------------------------------------------------------------------

_MCP_SESSION_FILE = ".debug_session.mcp.json"

server = Server("debugger-mcp")
_session = DebugSession.from_file_or_new(session_file=_MCP_SESSION_FILE)

# ---------------------------------------------------------------------------
# Tool strategies -- one per tool, maps name -> (schema, handler)
# ---------------------------------------------------------------------------


async def _launch(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.start(program=args["program"], language=args["language"])


async def _breakpoint(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.add_breakpoint(file=args["file"], line=args["line"])


async def _continue(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.resume()


async def _step(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.step(action=args.get("action", "next"))


async def _evaluate(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.inspect(expression=args["expression"])


async def _stack(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.get_stack()


async def _variables(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.get_local_variables()


async def _probe(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.probe(
        program=args["program"],
        file=args["file"],
        line=args["line"],
        language=args["language"],
    )


async def _stop(session: DebugSession, args: dict[str, Any]) -> str:
    return await session.stop()


# ---------------------------------------------------------------------------
# Registry: tool name -> (Tool schema, strategy, resets session after?)
# ---------------------------------------------------------------------------

_TOOL_REGISTRY: dict[str, tuple[types.Tool, ToolStrategy, bool]] = {
    "debug_launch": (
        types.Tool(
            name="debug_launch",
            description=(
                "Start debugging a program.  Spawns the appropriate debug "
                "adapter (Node.js or Python) and pauses at entry."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "program": {
                        "type": "string",
                        "description": "Absolute or relative path to the file to debug.",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["node", "python"],
                        "description": "Runtime language of the target program.",
                    },
                },
                "required": ["program", "language"],
            },
        ),
        _launch,
        False,
    ),
    "debug_breakpoint": (
        types.Tool(
            name="debug_breakpoint",
            description="Set a breakpoint at a specific file and line number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "Path to the source file.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number to break at.",
                    },
                },
                "required": ["file", "line"],
            },
        ),
        _breakpoint,
        False,
    ),
    "debug_continue": (
        types.Tool(
            name="debug_continue",
            description=(
                "Resume execution.  Blocks until the debugger hits a "
                "breakpoint, exception, or the program terminates."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        _continue,
        False,
    ),
    "debug_step": (
        types.Tool(
            name="debug_step",
            description="Step over (next) or step into the current line.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["next", "step_in"],
                        "description": "Step action.  Defaults to 'next' (step over).",
                    },
                },
            },
        ),
        _step,
        False,
    ),
    "debug_evaluate": (
        types.Tool(
            name="debug_evaluate",
            description="Evaluate an expression in the current stopped frame.",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expression to evaluate (e.g. variable name, function call).",
                    },
                },
                "required": ["expression"],
            },
        ),
        _evaluate,
        False,
    ),
    "debug_stack": (
        types.Tool(
            name="debug_stack",
            description="Get the current call stack trace.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _stack,
        False,
    ),
    "debug_variables": (
        types.Tool(
            name="debug_variables",
            description="Get local variables in the current stopped frame.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _variables,
        False,
    ),
    "debug_probe": (
        types.Tool(
            name="debug_probe",
            description=(
                "One-shot debugging: launch the program, set a breakpoint at "
                "the given line, run to it, dump all local variables and the "
                "stack trace, then stop.  Returns a comprehensive report."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "program": {
                        "type": "string",
                        "description": "Path to the file to debug.",
                    },
                    "file": {
                        "type": "string",
                        "description": "Path to the source file where the breakpoint should be set.",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number to probe.",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["node", "python"],
                        "description": "Runtime language.",
                    },
                },
                "required": ["program", "file", "line", "language"],
            },
        ),
        _probe,
        False,
    ),
    "debug_stop": (
        types.Tool(
            name="debug_stop",
            description="End the current debug session and clean up.",
            inputSchema={"type": "object", "properties": {}},
        ),
        _stop,
        True,  # reset session after stop
    ),
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [schema for schema, _, _ in _TOOL_REGISTRY.values()]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any]
) -> list[types.TextContent]:
    global _session  # noqa: PLW0603

    entry = _TOOL_REGISTRY.get(name)
    if entry is None:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    _schema, strategy, resets = entry
    text = await strategy(_session, arguments)

    if resets:
        _session = DebugSession.from_file_or_new(session_file=_MCP_SESSION_FILE)

    return [types.TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


async def run() -> None:
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="debugger-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
