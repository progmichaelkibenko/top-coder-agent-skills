#!/usr/bin/env python3
"""Python debugger CLI for agent skills.

Thin router that delegates all work to ``debugger_core.session.DebugSession``.
Each invocation is a separate process; session state is persisted to
``.debug_session.json`` between calls.

Usage::

    python debug.py start app.py
    python debug.py breakpoint app.py 22
    python debug.py continue
    python debug.py step
    python debug.py evaluate "my_var"
    python debug.py variables
    python debug.py stack
    python debug.py probe app.py:22
    python debug.py stop
"""

from __future__ import annotations

import asyncio
import os
import sys

# Require top-coder-ai-skills-debugger (provides debugger_core). Install globally or in env:
#   pip install top-coder-ai-skills-debugger
#   uv add top-coder-ai-skills-debugger   (if using uv in this project)
try:
    from debugger_core.session import DebugSession
except ModuleNotFoundError as e:
    if "debugger_core" in str(e) or e.name == "debugger_core":
        print(
            "Error: top-coder-ai-skills-debugger is not installed. Install it first:\n"
            "  pip install top-coder-ai-skills-debugger\n"
            "  or (in a project with uv): uv add top-coder-ai-skills-debugger",
            file=sys.stderr,
        )
        sys.exit(1)
    raise

LANGUAGE = "python"


def _usage() -> str:
    return (
        "Usage: python debug.py <action> [args]\n"
        "Actions: start <file>, breakpoint <file> <line>, continue, step,\n"
        "         evaluate <expr>, variables, stack, probe <file>:<line>, stop"
    )


async def _run(argv: list[str]) -> str:
    if len(argv) < 2:
        return _usage()

    action = argv[1]
    session = DebugSession.from_file_or_new(language=LANGUAGE)

    if action == "start":
        if len(argv) < 3:
            return "Error: start requires a file path.  Usage: start <file.py>"
        return await session.start(program=argv[2], language=LANGUAGE)

    if action == "breakpoint":
        if len(argv) < 4:
            return "Error: breakpoint requires file and line.  Usage: breakpoint <file> <line>"
        return await session.add_breakpoint(file=argv[2], line=int(argv[3]))

    if action == "continue":
        return await session.resume()

    if action == "step":
        step_action = argv[2] if len(argv) > 2 else "next"
        return await session.step(action=step_action)

    if action == "evaluate":
        if len(argv) < 3:
            return "Error: evaluate requires an expression.  Usage: evaluate <expr>"
        return await session.inspect(expression=argv[2])

    if action == "variables":
        return await session.get_local_variables()

    if action == "stack":
        return await session.get_stack()

    if action == "probe":
        if len(argv) < 3:
            return "Error: probe requires file:line.  Usage: probe <file>:<line>"
        target = argv[2]
        file_path, line_str = target.rsplit(":", 1)
        file_path = os.path.abspath(file_path)
        return await session.probe(
            program=file_path, file=file_path, line=int(line_str), language=LANGUAGE
        )

    if action == "stop":
        return await session.stop()

    return f"Unknown action: {action}\n{_usage()}"


def main() -> None:
    result = asyncio.run(_run(sys.argv))
    print(result)


if __name__ == "__main__":
    main()
