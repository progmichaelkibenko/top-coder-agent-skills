"""LLM-friendly formatting for DAP debug data.

All functions return plain text optimised for consumption by large
language models: no ANSI codes, no excessive nesting, token-efficient.
"""

from __future__ import annotations

import os
from typing import Any


# ---------------------------------------------------------------------------
# Stack traces
# ---------------------------------------------------------------------------


def format_stack_trace(frames: list[dict[str, Any]]) -> str:
    """Format DAP ``stackTrace`` frames into a concise string.

    Example output::

        #0  calculateTotal  (app.js:8)
        #1  main            (app.js:22)
        #2  Module._compile (internal/modules/cjs/loader.js:1085)
    """
    if not frames:
        return "(empty stack)"

    lines: list[str] = []
    for i, frame in enumerate(frames):
        name = frame.get("name", "<unknown>")
        source = frame.get("source", {})
        file_name = source.get("name") or source.get("path") or "?"
        line = frame.get("line", "?")
        lines.append(f"#{i:<3} {name:<30} ({file_name}:{line})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

_MAX_VALUE_LENGTH = 200
_MAX_VARIABLES = 30


def format_variables(variables: list[dict[str, Any]]) -> str:
    """Format DAP variables into a concise key=value list.

    Large values are truncated.  More than ``_MAX_VARIABLES`` entries
    are elided with a count.
    """
    if not variables:
        return "(no variables)"

    lines: list[str] = []
    shown = variables[:_MAX_VARIABLES]
    for var in shown:
        name = var.get("name", "?")
        value = var.get("value", "")
        var_type = var.get("type", "")

        # Truncate very long values (big JSON blobs, etc.).
        if len(value) > _MAX_VALUE_LENGTH:
            value = value[:_MAX_VALUE_LENGTH] + "..."

        if var_type:
            lines.append(f"  {name}: {var_type} = {value}")
        else:
            lines.append(f"  {name} = {value}")

    remaining = len(variables) - len(shown)
    if remaining > 0:
        lines.append(f"  ... and {remaining} more variables")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stopped-at location
# ---------------------------------------------------------------------------


def format_stopped_at(
    file_path: str,
    line: int,
    reason: str = "breakpoint",
    source_lines: list[str] | None = None,
    context_radius: int = 3,
) -> str:
    """Format a "stopped at" message with optional source context.

    If *source_lines* is ``None``, the function tries to read the
    file from disk.  The current line is marked with ``>>>``.
    """
    header = f"Stopped ({reason}) at {os.path.basename(file_path)}:{line}"

    code_lines = source_lines
    if code_lines is None:
        code_lines = _read_source_lines(file_path)

    if not code_lines:
        return header

    start = max(0, line - 1 - context_radius)
    end = min(len(code_lines), line + context_radius)
    snippet: list[str] = []
    for i in range(start, end):
        lineno = i + 1
        marker = ">>>" if lineno == line else "   "
        snippet.append(f"  {marker} {lineno:>4} | {code_lines[i]}")

    return f"{header}\n" + "\n".join(snippet)


# ---------------------------------------------------------------------------
# Probe summary (one-shot dump)
# ---------------------------------------------------------------------------


def format_probe_result(
    file_path: str,
    line: int,
    frames: list[dict[str, Any]],
    local_vars: list[dict[str, Any]],
    reason: str = "breakpoint",
) -> str:
    """Combine location, stack, and variables into a single probe report."""
    parts = [
        format_stopped_at(file_path, line, reason),
        "",
        "--- Stack Trace ---",
        format_stack_trace(frames),
        "",
        "--- Local Variables ---",
        format_variables(local_vars),
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_source_lines(file_path: str) -> list[str]:
    """Best-effort read of source file; returns [] on failure."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return [ln.rstrip("\n") for ln in f.readlines()]
    except OSError:
        return []
